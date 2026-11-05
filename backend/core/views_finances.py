"""API OmniChurch Connect — Phase 4 : module financier (section 10 du cahier des charges).

Comptes et caisses, recettes et dépenses avec workflow de validation, double validation
au-delà d'un seuil, devises USD/CDF avec taux historiques, budgets avec alertes et
blocage des dépassements, projets, transferts internes, clôtures mensuelles et
rapprochements. Tout est filtré sur l'Église de l'utilisateur authentifié.
"""
import csv
import io
import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone

from core.models import (Eglise, Membre, Groupe, CompteFinancier, CategorieOperation,
                         TauxChange, Projet, Budget, Mouvement, TransfertInterne,
                         CloturePeriode, Rapprochement, ParametreFinance, JournalAudit)
from core.security import auth_requise, permission_requise, tracer
from core.views_api import ok, err, corps


# ─────────────────────────── utilitaires ───────────────────────────

CATEGORIES_DEFAUT = {
    "recette": ["Dîmes", "Offrandes", "Dons", "Contributions spéciales", "Cotisations",
                "Événements", "Projets", "Construction", "Évangélisation", "Œuvres sociales"],
    "depense": ["Salaires et indemnités", "Loyer", "Électricité et eau", "Transport",
                "Entretien", "Évangélisation", "Œuvres sociales", "Achat de matériel",
                "Frais bancaires", "Remboursements"],
}


def _eglise(request):
    return request.utilisateur.eglise


def _date(v):
    if not v:
        return None
    if isinstance(v, date):
        return v
    for f in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(v)[:10], f).date()
        except ValueError:
            continue
    return None


def _decimal(v, defaut=None):
    try:
        return Decimal(str(v).replace(" ", "").replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return defaut


def _n(valeur):
    """Montant arrondi à deux décimales, sans bruit de virgule flottante."""
    if valeur is None:
        return "0.00"
    return str(Decimal(str(valeur)).quantize(Decimal("0.01")))


def _parametres(e):
    p, _ = ParametreFinance.objects.get_or_create(eglise=e)
    return p


def _categories_par_defaut(e):
    """Crée les catégories standard au premier usage du module."""
    if CategorieOperation.objects.filter(eglise=e).exists():
        return
    for sens, noms in CATEGORIES_DEFAUT.items():
        for nom in noms:
            CategorieOperation.objects.get_or_create(eglise=e, nom=nom, sens=sens,
                                                     defaults={"systeme": True})


def _taux_courant(e):
    t = TauxChange.objects.filter(eglise=e, devise_source="USD", devise_cible="CDF").first()
    return t.taux if t else None


def _convertir(e, montant, devise):
    """Contre-valeur en devise de référence de l'Église, avec le taux historique du jour."""
    p = _parametres(e)
    if devise == p.devise_reference:
        return montant, None
    taux = _taux_courant(e)
    if not taux:
        return None, f"Aucun taux {devise}/{p.devise_reference} enregistré : saisissez le taux avant la conversion."
    if devise == "USD" and p.devise_reference == "CDF":
        return (montant * taux).quantize(Decimal("0.01")), taux
    if devise == "CDF" and p.devise_reference == "USD":
        return (montant / taux).quantize(Decimal("0.01")), taux
    return montant, taux


def _numero_recu(e):
    p = _parametres(e)
    p.compteur_recu += 1
    p.save(update_fields=["compteur_recu"])
    return f"{p.prefixe_recu}-{timezone.localdate().year}-{p.compteur_recu:05d}"


def _json_mouvement(m):
    return {
        "id": m.id, "sens": m.sens, "montant": _n(m.montant), "devise": m.devise,
        "montant_converti": _n(m.montant_converti) if m.montant_converti is not None else None,
        "date": m.date.isoformat(), "libelle": m.libelle, "statut": m.statut,
        "compte": m.compte.nom, "compte_id": m.compte_id,
        "categorie": m.categorie.nom if m.categorie_id else "",
        "membre": f"{m.membre.nom} {m.membre.prenom}".strip() if m.membre_id else "",
        "donateur": "Anonyme" if m.anonyme else m.donateur_nom,
        "reference_recu": m.reference_recu, "justificatif": bool(m.justificatif_url),
        "projet": m.projet.nom if m.projet_id else "", "budget": m.budget.nom if m.budget_id else "",
        "paye_le": m.paye_le.isoformat() if m.paye_le else None,
        "double_validation_requise": None, "approuve_par": m.approuve_par.nom_complet if m.approuve_par_id else "",
    }


# ─────────────────────────── comptes et catégories ───────────────────────────

@auth_requise()
@permission_requise("finances", "consulter")
def comptes_liste(request):
    e = _eglise(request)
    _categories_par_defaut(e)
    comptes = []
    for c in CompteFinancier.objects.filter(eglise=e).select_related("responsable"):
        comptes.append({"id": c.id, "nom": c.nom, "type": c.type, "devise": c.devise,
                        "solde": _n(c.solde()), "actif": c.actif,
                        "responsable": c.responsable.nom_complet if c.responsable_id else ""})
    p = _parametres(e)
    return ok({"comptes": comptes,
               "parametres": {"devise_reference": p.devise_reference,
                              "seuil_verification": str(p.seuil_verification),
                              "seuil_double_validation": str(p.seuil_double_validation),
                              "justificatif_obligatoire": p.justificatif_obligatoire},
               "taux_usd_cdf": str(_taux_courant(e)) if _taux_courant(e) else None,
               "categories": [{"id": c.id, "nom": c.nom, "sens": c.sens}
                              for c in CategorieOperation.objects.filter(eglise=e, actif=True)]})


@auth_requise()
@permission_requise("finances", "creer")
def compte_creer(request):
    e = _eglise(request)
    d = corps(request)
    nom = (d.get("nom") or "").strip()
    if not nom:
        return err("Le nom du compte est obligatoire.")
    devise = d.get("devise") or "CDF"
    if devise not in ("USD", "CDF"):
        return err("Devise inconnue : USD ou CDF.")
    compte = CompteFinancier.objects.create(
        eglise=e, nom=nom[:120], type=d.get("type") or "espece", devise=devise,
        solde_initial=_decimal(d.get("solde_initial"), Decimal("0")),
        responsable_id=d.get("responsable_id") or None,
        observation=(d.get("observation") or "")[:300])
    tracer(request.utilisateur, "finances", "creer", f"Compte créé : {compte.nom} ({compte.devise})")
    return ok({"compte": {"id": compte.id, "nom": compte.nom, "solde": _n(compte.solde())}})


@auth_requise()
@permission_requise("finances", "modifier")
def compte_modifier(request):
    e = _eglise(request)
    d = corps(request)
    compte = CompteFinancier.objects.filter(eglise=e, id=d.get("id")).first()
    if not compte:
        return err("Compte introuvable dans cette Église.", 404)
    if d.get("nom"):
        compte.nom = d["nom"].strip()[:120]
    if "actif" in d:
        compte.actif = bool(d["actif"])
    if d.get("observation") is not None:
        compte.observation = (d["observation"] or "")[:300]
    compte.save()
    tracer(request.utilisateur, "finances", "modifier", f"Compte modifié : {compte.nom}")
    return ok({"compte": {"id": compte.id, "nom": compte.nom, "solde": _n(compte.solde())}})


@auth_requise()
@permission_requise("finances", "creer")
def categorie_creer(request):
    e = _eglise(request)
    d = corps(request)
    nom = (d.get("nom") or "").strip()
    sens = d.get("sens") or "recette"
    if not nom:
        return err("Le nom de la catégorie est obligatoire.")
    if sens not in ("recette", "depense"):
        return err("Le sens doit être recette ou dépense.")
    cat, cree = CategorieOperation.objects.get_or_create(eglise=e, nom=nom[:120], sens=sens)
    tracer(request.utilisateur, "finances", "creer", f"Catégorie {sens} : {cat.nom}")
    return ok({"categorie": {"id": cat.id, "nom": cat.nom, "sens": cat.sens}, "creee": cree})


@auth_requise()
@permission_requise("finances", "modifier")
def parametres_finance(request):
    e = _eglise(request)
    d = corps(request)
    p = _parametres(e)
    if d.get("seuil_verification") is not None:
        v = _decimal(d["seuil_verification"])
        if v is None or v < 0:
            return err("Seuil de vérification invalide.")
        p.seuil_verification = v
    if d.get("seuil_double_validation") is not None:
        v = _decimal(d["seuil_double_validation"])
        if v is None or v < 0:
            return err("Seuil de double validation invalide.")
        p.seuil_double_validation = v
    if d.get("devise_reference") in ("USD", "CDF"):
        p.devise_reference = d["devise_reference"]
    if "justificatif_obligatoire" in d:
        p.justificatif_obligatoire = bool(d["justificatif_obligatoire"])
    p.save()
    tracer(request.utilisateur, "finances", "modifier", "Paramètres financiers mis à jour")
    return ok({"parametres": {"devise_reference": p.devise_reference,
                              "seuil_verification": str(p.seuil_verification),
                              "seuil_double_validation": str(p.seuil_double_validation)}})


# ─────────────────────────── taux de change ───────────────────────────

@auth_requise()
@permission_requise("finances", "consulter")
def taux_liste(request):
    e = _eglise(request)
    taux = [{"id": t.id, "taux": str(t.taux), "date": t.date.isoformat(), "source": t.source,
             "saisi_par": t.saisi_par.nom_complet if t.saisi_par_id else ""}
            for t in TauxChange.objects.filter(eglise=e)[:60]]
    return ok({"taux": taux})


@auth_requise()
@permission_requise("finances", "creer")
def taux_creer(request):
    e = _eglise(request)
    d = corps(request)
    valeur = _decimal(d.get("taux"))
    if not valeur or valeur <= 0:
        return err("Le taux doit être un nombre positif.")
    jour = _date(d.get("date")) or timezone.localdate()
    t = TauxChange.objects.create(eglise=e, devise_source=d.get("devise_source") or "USD",
                                  devise_cible=d.get("devise_cible") or "CDF", taux=valeur,
                                  date=jour, source=(d.get("source") or "saisie manuelle")[:120],
                                  saisi_par=request.utilisateur)
    tracer(request.utilisateur, "finances", "creer",
           f"Taux {t.devise_source}/{t.devise_cible} = {t.taux} au {t.date}")
    return ok({"taux": {"id": t.id, "taux": str(t.taux), "date": t.date.isoformat()}})


# ─────────────────────────── mouvements ───────────────────────────

@auth_requise()
@permission_requise("finances", "consulter")
def mouvements_liste(request):
    e = _eglise(request)
    qs = Mouvement.objects.filter(eglise=e).select_related(
        "compte", "categorie", "membre", "projet", "budget", "approuve_par")
    if request.GET.get("sens"):
        qs = qs.filter(sens=request.GET["sens"])
    if request.GET.get("statut"):
        qs = qs.filter(statut=request.GET["statut"])
    if request.GET.get("compte"):
        qs = qs.filter(compte_id=request.GET["compte"])
    if request.GET.get("projet"):
        qs = qs.filter(projet_id=request.GET["projet"])
    if request.GET.get("budget"):
        qs = qs.filter(budget_id=request.GET["budget"])
    if request.GET.get("mois"):
        debut = _date(request.GET["mois"] + "-01")
        if debut:
            fin = (debut.replace(day=28) + timedelta(days=4)).replace(day=1)
            qs = qs.filter(date__gte=debut, date__lt=fin)
    totaux = {}
    for sens in ("recette", "depense"):
        agg = qs.filter(sens=sens)
        totaux[sens] = {
            "total": _n(agg.aggregate(s=Sum("montant"))["s"] or 0),
            "paye": _n(agg.filter(statut__in=["paye", "cloture"]).aggregate(
                s=Sum("montant"))["s"] or 0),
            "en_attente": agg.filter(statut__in=["demande", "a_verifier", "approuve"]).count(),
        }
    return ok({"mouvements": [_json_mouvement(m) for m in qs[:300]], "totaux": totaux})


@auth_requise()
@permission_requise("finances", "creer")
def mouvement_creer(request):
    e = _eglise(request)
    d = corps(request)
    compte = CompteFinancier.objects.filter(eglise=e, id=d.get("compte_id"), actif=True).first()
    if not compte:
        return err("Compte introuvable ou inactif dans cette Église.", 404)
    sens = d.get("sens") or "recette"
    if sens not in ("recette", "depense"):
        return err("Le sens doit être recette ou dépense.")
    montant = _decimal(d.get("montant"))
    if not montant or montant <= 0:
        return err("Le montant doit être un nombre positif.")
    libelle = (d.get("libelle") or "").strip()
    if not libelle:
        return err("Le libellé est obligatoire.")
    devise = d.get("devise") or compte.devise
    montant_converti, taux = _convertir(e, montant, devise)
    if montant_converti is None:
        return err(taux or "Conversion impossible.")

    p = _parametres(e)
    if sens == "depense" and p.justificatif_obligatoire and not (d.get("justificatif_url") or "").strip():
        return err("Un justificatif est exigé par la politique de l'Église pour les dépenses.")

    budget = Budget.objects.filter(eglise=e, id=d.get("budget_id")).first() if d.get("budget_id") else None
    if budget and sens == "depense" and budget.bloquer_depassement:
        engage = budget.consomme()
        if engage + montant > budget.montant:
            return err(f"Budget « {budget.nom} » dépassé : "
                       f"{engage} déjà engagés sur {budget.montant} {budget.devise}.")

    projet = Projet.objects.filter(eglise=e, id=d.get("projet_id")).first() if d.get("projet_id") else None
    categorie = CategorieOperation.objects.filter(eglise=e, id=d.get("categorie_id")).first() \
        if d.get("categorie_id") else None

    # Une recette saisie par un utilisateur habilité à valider est confirmée d'emblée.
    statut = "demande"
    if sens == "recette" and request.utilisateur.is_admin_principal:
        statut = "paye"

    m = Mouvement.objects.create(
        eglise=e, compte=compte, categorie=categorie, sens=sens, montant=montant, devise=devise,
        montant_converti=montant_converti, taux=taux, date=_date(d.get("date")) or timezone.localdate(),
        libelle=libelle[:250], membre_id=d.get("membre_id") or None,
        donateur_nom=(d.get("donateur_nom") or "")[:150], anonyme=bool(d.get("anonyme")),
        collecte_globale=bool(d.get("collecte_globale")),
        justificatif_url=(d.get("justificatif_url") or "")[:500],
        justification=(d.get("justification") or "")[:400], statut=statut,
        projet=projet, budget=budget, cree_par=request.utilisateur,
        paye_le=timezone.now() if statut == "paye" else None)
    if statut == "paye" and sens == "recette":
        m.reference_recu = _numero_recu(e)
        m.save(update_fields=["reference_recu"])
    tracer(request.utilisateur, "finances", "creer",
           f"{sens.capitalize()} {montant} {devise} — {m.libelle} ({statut})")
    data = _json_mouvement(m)
    double = sens == "depense" and montant_converti >= p.seuil_double_validation
    data["double_validation_requise"] = bool(double)
    return ok({"mouvement": data})


def _double_requise(e, m):
    p = _parametres(e)
    reference = m.montant_converti if m.montant_converti is not None else m.montant
    return m.sens == "depense" and reference >= p.seuil_double_validation


@auth_requise()
@permission_requise("finances", "valider")
def mouvement_verifier(request):
    e = _eglise(request)
    d = corps(request)
    m = Mouvement.objects.filter(eglise=e, id=d.get("id")).first()
    if not m:
        return err("Opération introuvable dans cette Église.", 404)
    if m.statut not in ("demande", "a_verifier"):
        return err(f"Cette opération est déjà au statut « {m.get_statut_display()} ».")
    p = _parametres(e)
    reference = m.montant_converti if m.montant_converti is not None else m.montant
    m.verifie_par = request.utilisateur
    if reference < p.seuil_verification:
        m.statut = "approuve"
        m.approuve_par = request.utilisateur
    else:
        m.statut = "a_verifier"
    m.save()
    tracer(request.utilisateur, "finances", "valider",
           f"Vérification de {m.libelle} → {m.get_statut_display()}")
    return ok({"mouvement": _json_mouvement(m), "statut": m.statut})


@auth_requise()
@permission_requise("finances", "valider")
def mouvement_approuver(request):
    e = _eglise(request)
    d = corps(request)
    m = Mouvement.objects.filter(eglise=e, id=d.get("id")).first()
    if not m:
        return err("Opération introuvable dans cette Église.", 404)
    if m.statut not in ("demande", "a_verifier"):
        return err(f"Cette opération est déjà au statut « {m.get_statut_display()} ».")
    if m.cree_par_id == request.utilisateur.id and not request.utilisateur.is_admin_principal:
        return err("La personne qui a saisi l'opération ne peut pas l'approuver elle-même.")
    m.approuve_par = request.utilisateur
    m.statut = "approuve"
    m.save()
    tracer(request.utilisateur, "finances", "valider", f"Approbation de {m.libelle}")
    data = _json_mouvement(m)
    data["double_validation_requise"] = _double_requise(e, m)
    return ok({"mouvement": data})


@auth_requise()
@permission_requise("finances", "valider")
def mouvement_seconde_validation(request):
    e = _eglise(request)
    d = corps(request)
    m = Mouvement.objects.filter(eglise=e, id=d.get("id")).first()
    if not m:
        return err("Opération introuvable dans cette Église.", 404)
    if not _double_requise(e, m):
        return err("La double validation n'est pas requise pour cette opération.")
    if not m.approuve_par_id:
        return err("La première approbation doit être donnée avant la seconde validation.")
    if m.approuve_par_id == request.utilisateur.id:
        return err("La seconde validation doit venir d'une autre personne que le premier approbateur.")
    m.seconde_validation_par = request.utilisateur
    m.save(update_fields=["seconde_validation_par"])
    tracer(request.utilisateur, "finances", "valider", f"Seconde validation de {m.libelle}")
    return ok({"mouvement": _json_mouvement(m), "double_validation_requise": False})


@auth_requise()
@permission_requise("finances", "valider")
def mouvement_rejeter(request):
    e = _eglise(request)
    d = corps(request)
    m = Mouvement.objects.filter(eglise=e, id=d.get("id")).first()
    if not m:
        return err("Opération introuvable dans cette Église.", 404)
    if m.statut in ("paye", "cloture"):
        return err("Une opération payée ou clôturée ne peut plus être rejetée.")
    motif = (d.get("motif") or "").strip()
    if not motif:
        return err("Le motif du rejet est obligatoire.")
    m.statut = "rejete"
    m.justification = motif[:400]
    m.save()
    tracer(request.utilisateur, "finances", "valider", f"Rejet de {m.libelle} : {motif}")
    return ok({"mouvement": _json_mouvement(m)})


@auth_requise()
@permission_requise("finances", "valider")
def mouvement_payer(request):
    e = _eglise(request)
    d = corps(request)
    m = Mouvement.objects.filter(eglise=e, id=d.get("id")).first()
    if not m:
        return err("Opération introuvable dans cette Église.", 404)
    if m.statut != "approuve":
        return err("Seule une opération approuvée peut être payée.")
    if _double_requise(e, m) and not m.seconde_validation_par_id:
        return err("Double validation exigée avant le paiement de cette dépense.")
    m.statut = "paye"
    m.paye_le = timezone.now()
    if m.sens == "recette" and not m.reference_recu:
        m.reference_recu = _numero_recu(e)
    m.save()
    tracer(request.utilisateur, "finances", "valider", f"Paiement enregistré : {m.libelle}")
    return ok({"mouvement": _json_mouvement(m), "solde_compte": _n(m.compte.solde())})


@auth_requise()
@permission_requise("finances", "supprimer")
def mouvement_annuler(request):
    e = _eglise(request)
    d = corps(request)
    m = Mouvement.objects.filter(eglise=e, id=d.get("id")).first()
    if not m:
        return err("Opération introuvable dans cette Église.", 404)
    if m.statut in ("paye", "cloture"):
        return err("Une opération payée ou clôturée ne s'annule pas : passez par une opération inverse.")
    m.statut = "annule"
    m.save(update_fields=["statut", "updated_at"])
    tracer(request.utilisateur, "finances", "supprimer", f"Annulation de {m.libelle}")
    return ok({"mouvement": _json_mouvement(m)})


# ─────────────────────────── transferts internes ───────────────────────────

@auth_requise()
@permission_requise("finances", "creer")
def transfert_creer(request):
    e = _eglise(request)
    d = corps(request)
    src = CompteFinancier.objects.filter(eglise=e, id=d.get("compte_source")).first()
    dst = CompteFinancier.objects.filter(eglise=e, id=d.get("compte_destination")).first()
    if not src or not dst:
        return err("Comptes source et destination obligatoires.", 404)
    if src.id == dst.id:
        return err("Un transfert doit viser deux comptes différents.")
    montant = _decimal(d.get("montant"))
    if not montant or montant <= 0:
        return err("Montant de transfert invalide.")
    if src.devise == dst.devise:
        recu = montant
    else:
        recu, info = _convertir(e, montant, src.devise)
        if recu is None:
            return err(info)
    t = TransfertInterne.objects.create(
        eglise=e, compte_source=src, compte_destination=dst, montant=montant, devise=src.devise,
        montant_recu=recu, frais=_decimal(d.get("frais"), Decimal("0")),
        date=_date(d.get("date")) or timezone.localdate(),
        libelle=(d.get("libelle") or "")[:250], cree_par=request.utilisateur)
    tracer(request.utilisateur, "finances", "creer",
           f"Transfert {t.montant} {t.devise} de {src.nom} vers {dst.nom}")
    return ok({"transfert": {"id": t.id, "montant": _n(t.montant), "recu": _n(t.montant_recu)}})


@auth_requise()
@permission_requise("finances", "consulter")
def transferts_liste(request):
    e = _eglise(request)
    lignes = [{"id": t.id, "source": t.compte_source.nom, "destination": t.compte_destination.nom,
               "montant": _n(t.montant), "devise": t.devise, "recu": _n(t.montant_recu),
               "frais": _n(t.frais), "date": t.date.isoformat(), "libelle": t.libelle}
              for t in TransfertInterne.objects.filter(eglise=e).select_related(
                  "compte_source", "compte_destination")[:200]]
    return ok({"transferts": lignes})


# ─────────────────────────── budgets ───────────────────────────

@auth_requise()
@permission_requise("finances", "consulter")
def budgets_liste(request):
    e = _eglise(request)
    p = _parametres(e)
    seuils = [75, 90, 100]
    lignes = []
    for b in Budget.objects.filter(eglise=e, actif=True).select_related("groupe", "projet"):
        engage = b.consomme()
        paye = b.paye()
        taux = float((engage / b.montant) * 100) if b.montant else 0
        alertes = [s for s in seuils if taux >= s]
        lignes.append({
            "id": b.id, "nom": b.nom, "montant": _n(b.montant), "devise": b.devise,
            "engage": _n(engage), "paye": _n(paye),
            "restant": _n(b.montant - engage), "consommation": round(taux, 1),
            "alertes": alertes, "blocage": b.bloquer_depassement,
            "groupe": b.groupe.nom if b.groupe_id else "",
            "projet": b.projet.nom if b.projet_id else "",
            "periode": f"{b.date_debut} → {b.date_fin}"})
    return ok({"budgets": lignes, "seuils": seuils,
               "devise_reference": p.devise_reference})


@auth_requise()
@permission_requise("finances", "creer")
def budget_creer(request):
    e = _eglise(request)
    d = corps(request)
    nom = (d.get("nom") or "").strip()
    montant = _decimal(d.get("montant"))
    debut, fin = _date(d.get("date_debut")), _date(d.get("date_fin"))
    if not nom:
        return err("Le nom du budget est obligatoire.")
    if not montant or montant <= 0:
        return err("Le montant du budget doit être positif.")
    if not debut or not fin or fin < debut:
        return err("Les dates du budget sont invalides.")
    b = Budget.objects.create(
        eglise=e, nom=nom[:150], montant=montant, devise=d.get("devise") or "CDF",
        date_debut=debut, date_fin=fin,
        groupe_id=d.get("groupe_id") or None, projet_id=d.get("projet_id") or None,
        seuils=d.get("seuils") or [75, 90, 100],
        bloquer_depassement=bool(d.get("bloquer_depassement", True)))
    tracer(request.utilisateur, "finances", "creer", f"Budget créé : {b.nom} ({b.montant} {b.devise})")
    return ok({"budget": {"id": b.id, "nom": b.nom, "montant": _n(b.montant)}})


# ─────────────────────────── projets ───────────────────────────

@auth_requise()
@permission_requise("finances", "consulter")
def projets_liste(request):
    e = _eglise(request)
    lignes = []
    for pr in Projet.objects.filter(eglise=e):
        recettes = Mouvement.objects.filter(projet=pr, sens="recette", statut__in=[
            "paye", "cloture"]).aggregate(s=Sum("montant"))["s"] or 0
        depenses = Mouvement.objects.filter(projet=pr, sens="depense", statut__in=[
            "paye", "cloture"]).aggregate(s=Sum("montant"))["s"] or 0
        engage = Mouvement.objects.filter(projet=pr, sens="depense", statut__in=[
            "demande", "a_verifier", "approuve", "paye", "cloture"]).aggregate(
            s=Sum("montant"))["s"] or 0
        promis = pr.budget_montant
        lignes.append({"id": pr.id, "nom": pr.nom, "objectif": pr.objectif,
                       "budget": str(promis), "devise": pr.devise,
                       "recu": _n(recettes), "depense": _n(depenses),
                       "solde": _n(recettes - depenses), "engage": _n(engage),
                       "avancement": pr.avancement,
                       "statut": pr.statut,
                       "financement": round(float(recettes / promis) * 100, 1) if promis else 0})
    return ok({"projets": lignes})


@auth_requise()
@permission_requise("finances", "creer")
def projet_creer(request):
    e = _eglise(request)
    d = corps(request)
    nom = (d.get("nom") or "").strip()
    if not nom:
        return err("Le nom du projet est obligatoire.")
    pr = Projet.objects.create(
        eglise=e, nom=nom[:150], objectif=(d.get("objectif") or ""),
        budget_montant=_decimal(d.get("budget_montant"), Decimal("0")),
        devise=d.get("devise") or "USD", date_debut=_date(d.get("date_debut")),
        date_fin=_date(d.get("date_fin")), statut=d.get("statut") or "en_cours",
        avancement=int(d.get("avancement") or 0), cree_par=request.utilisateur)
    tracer(request.utilisateur, "finances", "creer", f"Projet créé : {pr.nom}")
    return ok({"projet": {"id": pr.id, "nom": pr.nom}})


@auth_requise()
@permission_requise("finances", "modifier")
def projet_modifier(request):
    e = _eglise(request)
    d = corps(request)
    pr = Projet.objects.filter(eglise=e, id=d.get("id")).first()
    if not pr:
        return err("Projet introuvable dans cette Église.", 404)
    if d.get("avancement") is not None:
        pr.avancement = max(0, min(int(d["avancement"]), 100))
    if d.get("statut") in dict(Projet.STATUTS):
        pr.statut = d["statut"]
    if d.get("objectif") is not None:
        pr.objectif = d["objectif"]
    pr.save()
    tracer(request.utilisateur, "finances", "modifier", f"Projet modifié : {pr.nom}")
    return ok({"projet": {"id": pr.id, "avancement": pr.avancement, "statut": pr.statut}})


# ─────────────────────────── clôtures et rapprochements ───────────────────────────

@auth_requise()
@permission_requise("finances", "valider")
def cloture_preparer(request):
    e = _eglise(request)
    d = corps(request)
    periode = (d.get("periode") or timezone.localdate().strftime("%Y-%m"))[:7]
    debut = _date(periode + "-01")
    if not debut:
        return err("Période invalide (format AAAA-MM).")
    fin = (debut.replace(day=28) + timedelta(days=4)).replace(day=1)
    if CloturePeriode.objects.filter(eglise=e, periode=periode, verrouille=True).exists():
        return err("Cette période est déjà clôturée et verrouillée.")
    recettes = Mouvement.objects.filter(eglise=e, sens="recette", date__gte=debut, date__lt=fin,
                                        statut__in=["paye", "cloture"]).aggregate(
        s=Sum("montant_converti"))["s"] or 0
    depenses = Mouvement.objects.filter(eglise=e, sens="depense", date__gte=debut, date__lt=fin,
                                        statut__in=["paye", "cloture"]).aggregate(
        s=Sum("montant_converti"))["s"] or 0
    rapprochements = Rapprochement.objects.filter(eglise=e, date__gte=debut, date__lt=fin)
    ecart = sum((r.ecart for r in rapprochements), Decimal("0"))
    cl, _ = CloturePeriode.objects.update_or_create(
        eglise=e, periode=periode,
        defaults={"statut": "prepare", "total_recettes": recettes, "total_depenses": depenses,
                  "ecart": ecart, "justification": (d.get("justification") or "")[:500],
                  "prepare_par": request.utilisateur, "verrouille": False})
    tracer(request.utilisateur, "finances", "valider", f"Clôture préparée : {periode}")
    return ok({"cloture": {"id": cl.id, "periode": cl.periode, "recettes": _n(cl.total_recettes),
                           "depenses": _n(cl.total_depenses), "ecart": _n(cl.ecart),
                           "statut": cl.statut}})


@auth_requise()
@permission_requise("finances", "valider")
def cloture_approuver(request):
    e = _eglise(request)
    d = corps(request)
    cl = CloturePeriode.objects.filter(eglise=e, id=d.get("id")).first()
    if not cl:
        return err("Clôture introuvable dans cette Église.", 404)
    if cl.statut == "approuve":
        return err("Cette clôture est déjà approuvée.")
    if cl.prepare_par_id == request.utilisateur.id and not request.utilisateur.is_admin_principal:
        return err("La personne qui prépare une clôture ne peut pas l'approuver elle-même.")
    debut = _date(cl.periode + "-01")
    fin = (debut.replace(day=28) + timedelta(days=4)).replace(day=1)
    if cl.ecart != 0:
        non_justifies = Rapprochement.objects.filter(
            eglise=e, date__gte=debut, date__lt=fin).exclude(ecart=0).filter(justification="")
        if non_justifies.exists():
            return err("Un écart non justifié subsiste sur : " +
                       ", ".join(r.compte.nom for r in non_justifies) + ".")
        if not cl.justification.strip():
            cl.justification = "; ".join(
                f"{r.compte.nom} : {r.justification}" for r in Rapprochement.objects.filter(
                    eglise=e, date__gte=debut, date__lt=fin).exclude(ecart=0))[:480] or "Écart de rapprochement"
    with transaction.atomic():
        Mouvement.objects.filter(eglise=e, date__gte=debut, date__lt=fin, statut="paye").update(
            statut="cloture")
        cl.statut = "approuve"
        cl.approuve_par = request.utilisateur
        cl.verrouille = True
        cl.save()
    tracer(request.utilisateur, "finances", "valider", f"Clôture approuvée et verrouillée : {cl.periode}")
    return ok({"cloture": {"id": cl.id, "periode": cl.periode, "statut": cl.statut,
                           "verrouille": cl.verrouille}})


@auth_requise()
@permission_requise("finances", "consulter")
def clotures_liste(request):
    e = _eglise(request)
    return ok({"clotures": [{"id": c.id, "periode": c.periode, "statut": c.statut,
                             "recettes": _n(c.total_recettes), "depenses": _n(c.total_depenses),
                             "ecart": _n(c.ecart), "verrouille": c.verrouille,
                             "prepare_par": c.prepare_par.nom_complet if c.prepare_par_id else "",
                             "approuve_par": c.approuve_par.nom_complet if c.approuve_par_id else ""}
                            for c in CloturePeriode.objects.filter(eglise=e)]})


@auth_requise()
@permission_requise("finances", "valider")
def rapprochement_creer(request):
    e = _eglise(request)
    d = corps(request)
    compte = CompteFinancier.objects.filter(eglise=e, id=d.get("compte_id")).first()
    if not compte:
        return err("Compte introuvable dans cette Église.", 404)
    releve = _decimal(d.get("solde_releve"))
    if releve is None:
        return err("Solde du relevé obligatoire.")
    calcule = compte.solde()
    ecart = releve - calcule
    if ecart != 0 and not (d.get("justification") or "").strip():
        return err(f"Écart de {ecart} constaté : une justification est exigée.")
    r = Rapprochement.objects.create(
        eglise=e, compte=compte, date=_date(d.get("date")) or timezone.localdate(),
        solde_releve=releve, solde_calcule=calcule, ecart=ecart,
        justification=(d.get("justification") or "")[:500], cree_par=request.utilisateur)
    tracer(request.utilisateur, "finances", "valider",
           f"Rapprochement {compte.nom} : écart {ecart}")
    return ok({"rapprochement": {"id": r.id, "ecart": _n(r.ecart), "calcule": _n(calcule)}})


@auth_requise()
@permission_requise("finances", "consulter")
def rapprochements_liste(request):
    e = _eglise(request)
    return ok({"rapprochements": [{"id": r.id, "compte": r.compte.nom, "date": r.date.isoformat(),
                                   "releve": _n(r.solde_releve), "calcule": _n(r.solde_calcule),
                                   "ecart": _n(r.ecart), "justification": r.justification}
                                  for r in Rapprochement.objects.filter(eglise=e).select_related(
                                      "compte")[:100]]})


# ─────────────────────────── tableau de bord et rapports ───────────────────────────

@auth_requise()
@permission_requise("finances", "consulter")
def finances_bord(request):
    e = _eglise(request)
    _categories_par_defaut(e)
    aujourdhui = timezone.localdate()
    debut_mois = aujourdhui.replace(day=1)
    p = _parametres(e)

    def total(sens, depuis, jusqu=None):
        qs = Mouvement.objects.filter(eglise=e, sens=sens, date__gte=depuis,
                                      statut__in=["paye", "cloture"])
        if jusqu:
            qs = qs.filter(date__lt=jusqu)
        return qs.aggregate(s=Sum("montant_converti"))["s"] or 0

    soldes = [{"compte": c.nom, "devise": c.devise, "solde": _n(c.solde())}
              for c in CompteFinancier.objects.filter(eglise=e, actif=True)]
    par_categorie = []
    for cat in CategorieOperation.objects.filter(eglise=e, actif=True):
        s = Mouvement.objects.filter(eglise=e, categorie=cat, date__gte=debut_mois,
                                     statut__in=["paye", "cloture"]).aggregate(
            s=Sum("montant_converti"))["s"] or 0
        if s:
            par_categorie.append({"categorie": cat.nom, "sens": cat.sens, "total": _n(s)})
    return ok({
        "mois": aujourdhui.strftime("%Y-%m"),
        "recettes_mois": _n(total("recette", debut_mois)),
        "depenses_mois": _n(total("depense", debut_mois)),
        "recettes_annee": _n(total("recette", date(aujourdhui.year, 1, 1))),
        "depenses_annee": _n(total("depense", date(aujourdhui.year, 1, 1))),
        "a_valider": Mouvement.objects.filter(eglise=e, statut__in=[
            "demande", "a_verifier"], sens="depense").count(),
        "sans_justificatif": Mouvement.objects.filter(eglise=e, sens="depense",
                                                      justificatif_url="").exclude(
            statut__in=["annule", "rejete"]).count(),
        "soldes": soldes, "par_categorie": par_categorie,
        "dernieres": [_json_mouvement(m) for m in Mouvement.objects.filter(eglise=e).select_related(
            "compte", "categorie", "membre", "projet", "budget", "approuve_par")[:8]],
        "devise_reference": p.devise_reference,
    })


@auth_requise()
@permission_requise("finances", "exporter")
def finances_export(request):
    e = _eglise(request)
    qs = Mouvement.objects.filter(eglise=e).select_related("compte", "categorie", "membre").order_by("date")
    if request.GET.get("annee"):
        qs = qs.filter(date__year=int(request.GET["annee"]))
    if request.GET.get("mois"):
        qs = qs.filter(date__startswith=request.GET["mois"])
    sortie = io.StringIO()
    w = csv.writer(sortie, delimiter=";")
    w.writerow(["Date", "Sens", "Libellé", "Compte", "Catégorie", "Montant", "Devise",
                "Contre-valeur", "Statut", "Membre / Donateur", "Reçu", "Justificatif",
                "Projet", "Budget"])
    for m in qs:
        w.writerow([m.date.isoformat(), m.get_sens_display(), m.libelle, m.compte.nom,
                    m.categorie.nom if m.categorie_id else "", m.montant, m.devise,
                    m.montant_converti if m.montant_converti is not None else "",
                    m.get_statut_display(),
                    "Anonyme" if m.anonyme else (f"{m.membre.nom} {m.membre.prenom}".strip()
                                                 if m.membre_id else m.donateur_nom),
                    m.reference_recu, "oui" if m.justificatif_url else "non",
                    m.projet.nom if m.projet_id else "", m.budget.nom if m.budget_id else ""])
    reponse = HttpResponse("\ufeff" + sortie.getvalue(), content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = 'attachment; filename="finances.csv"'
    tracer(request.utilisateur, "finances", "exporter", "Export CSV des opérations financières")
    return reponse


@auth_requise()
@permission_requise("finances", "consulter")
def finances_rapport_annuel(request):
    """Rapport annuel : soldes d'ouverture et de clôture, recettes, dépenses, budgets, écarts."""
    e = _eglise(request)
    annee = int(request.GET.get("annee") or timezone.localdate().year)
    mois = []
    cumul_r = cumul_d = Decimal("0")
    for n in range(1, 13):
        debut = date(annee, n, 1)
        fin = date(annee + (1 if n == 12 else 0), 1 if n == 12 else n + 1, 1)
        r = Mouvement.objects.filter(eglise=e, sens="recette", date__gte=debut, date__lt=fin,
                                     statut__in=["paye", "cloture"]).aggregate(
            s=Sum("montant_converti"))["s"] or 0
        d_ = Mouvement.objects.filter(eglise=e, sens="depense", date__gte=debut, date__lt=fin,
                                      statut__in=["paye", "cloture"]).aggregate(
            s=Sum("montant_converti"))["s"] or 0
        cumul_r += r
        cumul_d += d_
        mois.append({"mois": f"{annee}-{n:02d}", "recettes": _n(r), "depenses": _n(d_),
                     "solde": _n(r - d_)})
    budgets = [{"nom": b.nom, "montant": _n(b.montant), "engage": _n(b.consomme()),
                "paye": _n(b.paye()), "restant": _n(b.montant - b.consomme())}
               for b in Budget.objects.filter(eglise=e, date_debut__year=annee)]
    return ok({"annee": annee, "mois": mois,
               "total_recettes": _n(cumul_r), "total_depenses": _n(cumul_d),
               "solde_annuel": _n(cumul_r - cumul_d), "budgets": budgets,
               "devise_reference": _parametres(e).devise_reference,
               "justificatifs_manquants": Mouvement.objects.filter(
                   eglise=e, sens="depense", justificatif_url="", date__year=annee).exclude(
                   statut__in=["annule", "rejete"]).count(),
               "validations_en_cours": Mouvement.objects.filter(
                   eglise=e, statut__in=["demande", "a_verifier"], date__year=annee).count()})
