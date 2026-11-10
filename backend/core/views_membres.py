"""API OmniChurch Connect — Phase 2.
Membres, matricules, effectif global déclaré, groupes, présences, documents de base.
Règle absolue : toute requête est filtrée sur l'Église de l'utilisateur authentifié.
L'identifiant fourni par le navigateur ne sert jamais à autoriser l'accès à une Église.
"""
import csv
import io
import json
import unicodedata
from datetime import date, datetime, timedelta

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone

from core.models import (Eglise, Membre, ParametreMatricule, EffectifDeclare,
                         Groupe, MembreGroupe, Evenement, Presence, JournalAudit)
from core.security import auth_requise, permission_requise, tracer
from core.views_api import ok, err, corps


# ─────────────────────────── utilitaires ───────────────────────────

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


def _membre_json(m, complet=True):
    d = {
        "id": m.id, "matricule": m.matricule, "nom": m.nom, "postnom": m.postnom,
        "prenom": m.prenom, "nom_complet": m.nom_complet, "sexe": m.sexe,
        "statut": m.statut, "etat_validation": m.etat_validation,
        "telephone": m.telephone, "email": m.email,
        "date_adhesion": m.date_adhesion.isoformat() if m.date_adhesion else None,
        "created_at": m.created_at.isoformat(),
    }
    if complet:
        d.update({
            "date_naissance": m.date_naissance.isoformat() if m.date_naissance else None,
            "lieu_naissance": m.lieu_naissance, "nationalite": m.nationalite,
            "profession": m.profession, "etat_civil": m.etat_civil, "adresse": m.adresse,
            "contact_urgence": m.contact_urgence,
            "date_ordination": m.date_ordination.isoformat() if m.date_ordination else None,
            "observation": m.observation, "motif_rejet": m.motif_rejet,
            "photo_url": m.photo_url,
            "valide_le": m.valide_le.isoformat() if m.valide_le else None,
            "groupes": [{"id": a.groupe_id, "nom": a.groupe.nom, "fonction": a.fonction}
                        for a in m.appartenances.select_related("groupe").all()],
        })
    return d


def _prefixe_ascii(nom, longueur=3):
    base = unicodedata.normalize("NFKD", (nom or "").upper())
    base = "".join(c for c in base if "A" <= c <= "Z")
    return (base[:longueur] or "EGL")


def _norm(txt):
    txt = unicodedata.normalize("NFD", (txt or "").lower())
    return "".join(c for c in txt if unicodedata.category(c) != "Mn").strip()


def _prochain_matricule(eglise):
    """Attribue le prochain matricule officiel. Unique par Église, jamais réutilisé."""
    with transaction.atomic():
        param, _cree = ParametreMatricule.objects.select_for_update().get_or_create(
            eglise=eglise,
            defaults={"prefixe": _prefixe_ascii(eglise.nom)})
        param.compteur += 1
        param.save(update_fields=["compteur"])
        parties = [param.prefixe.upper()]
        if param.inclure_annee:
            parties.append(str(timezone.now().year))
        parties.append(str(param.compteur).zfill(max(1, param.chiffres)))
        return param.separateur.join(parties)


# ─────────────────────────── membres ───────────────────────────

@permission_requise("membres", "consulter")
def membres_liste(request):
    e = _eglise(request)
    qs = Membre.objects.filter(eglise=e).prefetch_related("appartenances__groupe")
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(nom__icontains=q) | Q(postnom__icontains=q) | Q(prenom__icontains=q)
                       | Q(matricule__icontains=q) | Q(telephone__icontains=q)
                       | Q(email__icontains=q))
    for champ in ("statut", "etat_validation", "sexe"):
        v = request.GET.get(champ)
        if v:
            qs = qs.filter(**{champ: v})
    gid = request.GET.get("groupe")
    if gid:
        qs = qs.filter(appartenances__groupe_id=gid, appartenances__date_fin__isnull=True)
    total = qs.count()
    try:
        page = max(1, int(request.GET.get("page", 1)))
        limite = min(100, max(5, int(request.GET.get("limit", 25))))
    except ValueError:
        page, limite = 1, 25
    debut = (page - 1) * limite
    items = [_membre_json(m, complet=False) for m in qs[debut:debut + limite]]
    return ok({"total": total, "page": page, "limite": limite,
               "pages": max(1, (total + limite - 1) // limite), "membres": items})


@permission_requise("membres", "consulter")
def membre_detail(request):
    e = _eglise(request)
    mid = request.GET.get("id")
    m = Membre.objects.filter(eglise=e, id=mid).prefetch_related("appartenances__groupe").first()
    if not m:
        return err("Membre introuvable dans cette Église.", 404)
    return ok({"membre": _membre_json(m)})


CHAMPS_MEMBRE = ["nom", "postnom", "prenom", "sexe", "lieu_naissance", "nationalite",
                 "profession", "etat_civil", "telephone", "email", "adresse",
                 "contact_urgence", "statut", "observation", "photo_url"]
CHAMPS_DATE = ["date_naissance", "date_adhesion", "date_ordination"]


def _appliquer(d, m):
    for c in CHAMPS_MEMBRE:
        if c in d and d[c] is not None:
            setattr(m, c, str(d[c])[:400])
    for c in CHAMPS_DATE:
        if c in d:
            setattr(m, c, _date(d[c]))


@permission_requise("membres", "creer")
def membre_creer(request):
    e = _eglise(request)
    if request.method != "POST":
        return err("Méthode non autorisée.", 405)
    d = corps(request)
    if not (d.get("nom") or "").strip():
        return err("Le nom est obligatoire.")
    m = Membre(eglise=e, cree_par=request.utilisateur, etat_validation="a_valider")
    _appliquer(d, m)
    if not m.statut:
        m.statut = "nouveau"
    m.save()
    tracer(request.utilisateur, "membres", "creation",
           f"Dossier créé : {m.nom_complet} (#{m.id})")
    return ok({"membre": _membre_json(m)})


@permission_requise("membres", "modifier")
def membre_modifier(request):
    e = _eglise(request)
    d = corps(request)
    m = Membre.objects.filter(eglise=e, id=d.get("id")).first()
    if not m:
        return err("Membre introuvable dans cette Église.", 404)
    avant = {"nom": m.nom_complet, "statut": m.statut, "etat": m.etat_validation}
    _appliquer(d, m)
    # un dossier validé qui change de fond repasse en validation
    if m.etat_validation == "valide" and any(k in d for k in ("nom", "postnom", "prenom")):
        m.etat_validation = "a_valider"
    m.save()
    tracer(request.utilisateur, "membres", "modification",
           f"Dossier modifié : {avant['nom']} → {m.nom_complet} (#{m.id})")
    return ok({"membre": _membre_json(m)})


@permission_requise("membres", "valider")
def membre_valider(request):
    """Approbation du dossier : c'est ici, et seulement ici, que le matricule est attribué."""
    e = _eglise(request)
    d = corps(request)
    m = Membre.objects.filter(eglise=e, id=d.get("id")).first()
    if not m:
        return err("Membre introuvable dans cette Église.", 404)
    if m.etat_validation == "valide" and m.matricule:
        return err(f"Ce dossier est déjà validé avec le matricule {m.matricule}.")
    nouveau = not m.matricule
    if nouveau:
        m.matricule = _prochain_matricule(e)
    m.etat_validation = "valide"
    m.motif_rejet = ""
    m.valide_le = timezone.now()
    m.valide_par = request.utilisateur
    if m.statut in ("nouveau", "visiteur"):
        m.statut = "actif"
    m.save()
    tracer(request.utilisateur, "membres", "validation",
           f"Dossier validé : {m.nom_complet} · matricule {m.matricule}")
    return ok({"membre": _membre_json(m), "matricule": m.matricule})


@permission_requise("membres", "valider")
def membre_retourner(request):
    e = _eglise(request)
    d = corps(request)
    m = Membre.objects.filter(eglise=e, id=d.get("id")).first()
    if not m:
        return err("Membre introuvable dans cette Église.", 404)
    m.etat_validation = "retourne"
    m.motif_rejet = (d.get("motif") or "Dossier à compléter.")[:400]
    m.save()
    tracer(request.utilisateur, "membres", "retour",
           f"Dossier retourné : {m.nom_complet} · motif : {m.motif_rejet}")
    return ok({"membre": _membre_json(m)})


@permission_requise("membres", "valider")
def membre_rejeter(request):
    e = _eglise(request)
    d = corps(request)
    m = Membre.objects.filter(eglise=e, id=d.get("id")).first()
    if not m:
        return err("Membre introuvable dans cette Église.", 404)
    motif = (d.get("motif") or "").strip()
    if not motif:
        return err("Un motif est obligatoire pour rejeter un dossier.")
    m.etat_validation = "rejete"
    m.motif_rejet = motif[:400]
    m.save()
    tracer(request.utilisateur, "membres", "rejet",
           f"Dossier rejeté : {m.nom_complet} · motif : {motif}")
    return ok({"membre": _membre_json(m)})


@permission_requise("membres", "supprimer")
def membre_archiver(request):
    """Un départ n'efface jamais le dossier ni ses documents (section 8)."""
    e = _eglise(request)
    d = corps(request)
    m = Membre.objects.filter(eglise=e, id=d.get("id")).first()
    if not m:
        return err("Membre introuvable dans cette Église.", 404)
    if m.etat_validation == "brouillon":
        tracer(request.utilisateur, "membres", "suppression",
               f"Brouillon supprimé : {m.nom_complet} (#{m.id})")
        m.delete()
        return ok({"supprime": True})
    m.statut = d.get("statut") or "transfere"
    m.observation = (m.observation + f"\n[{timezone.now():%d/%m/%Y}] "
                     f"Archivage : {d.get('motif', 'départ enregistré')}")[:2000]
    m.save()
    tracer(request.utilisateur, "membres", "archivage",
           f"Dossier archivé (statut {m.statut}) : {m.nom_complet} · matricule conservé {m.matricule}")
    return ok({"archived": True, "membre": _membre_json(m)})


@permission_requise("membres", "consulter")
def membres_doublons(request):
    """Signale les doublons potentiels. Ne fusionne jamais automatiquement."""
    e = _eglise(request)
    membres = list(Membre.objects.filter(eglise=e).only(
        "id", "nom", "postnom", "prenom", "telephone", "email", "date_naissance", "matricule"))
    groupes, index = [], {}

    def ajouter(cle, m, raison):
        if not cle:
            return
        index.setdefault(cle, {"raison": raison, "membres": []})
        if m not in index[cle]["membres"]:
            index[cle]["membres"].append(m)

    for m in membres:
        tel = "".join(c for c in (m.telephone or "") if c.isdigit())
        if len(tel) >= 8:
            ajouter("tel:" + tel, m, "Même numéro de téléphone")
        if m.email:
            ajouter("mail:" + m.email.lower().strip(), m, "Même adresse e-mail")
        ajouter("nom:" + _norm(m.nom) + "|" + _norm(m.prenom), m, "Même nom et prénom")
        if m.matricule:
            ajouter("mat:" + m.matricule, m, "Même matricule")
    for cle, v in index.items():
        if len(v["membres"]) > 1:
            groupes.append({"cle": cle, "raison": v["raison"],
                            "membres": [_membre_json(x, complet=False) for x in v["membres"]]})
    return ok({"doublons": groupes, "total": len(groupes),
               "note": "Aucune fusion n'est automatique : chaque fusion doit être décidée et est tracée."})


@permission_requise("membres", "exporter")
def membres_export(request):
    e = _eglise(request)
    qs = Membre.objects.filter(eglise=e)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(nom__icontains=q) | Q(prenom__icontains=q)
                       | Q(matricule__icontains=q) | Q(telephone__icontains=q))
    tampon = io.StringIO()
    tampon.write("\ufeff")
    w = csv.writer(tampon, delimiter=";")
    w.writerow(["Matricule", "Nom", "Postnom", "Prénom", "Sexe", "Naissance", "Téléphone",
                "E-mail", "Statut", "Validation", "Adhésion", "Profession"])
    for m in qs:
        w.writerow([m.matricule, m.nom, m.postnom, m.prenom, m.sexe,
                    m.date_naissance or "", m.telephone, m.email, m.statut,
                    m.etat_validation, m.date_adhesion or "", m.profession])
    tracer(request.utilisateur, "membres", "export", f"Export CSV de {qs.count()} membres")
    rep = HttpResponse(tampon.getvalue().encode("utf-8"), content_type="text/csv; charset=utf-8")
    rep["Content-Disposition"] = f'attachment; filename="membres-{e.slug}.csv"'
    return rep


# ─────────────────────── effectif global déclaré ───────────────────────

@permission_requise("membres", "consulter")
def effectifs_liste(request):
    e = _eglise(request)
    lignes = EffectifDeclare.objects.filter(eglise=e).select_related("auteur")[:60]
    enregistres = Membre.objects.filter(eglise=e).exclude(etat_validation="rejete").count()
    declares = EffectifDeclare.objects.filter(eglise=e).aggregate(s=Sum("valeur"))["s"] or 0
    return ok({
        "effectifs": [{"id": x.id, "categorie": x.categorie, "valeur": x.valeur,
                       "periode": x.periode, "observation": x.observation,
                       "auteur": x.auteur.nom_complet if x.auteur else "—",
                       "created_at": x.created_at.isoformat()} for x in lignes],
        "categories": [{"code": c, "label": l} for c, l in EffectifDeclare.CATEGORIES],
        "membres_enregistres": enregistres,
        "effectif_declare": declares,
        "total_general": enregistres + declares,
        "avertissement": ("Le total général additionne les dossiers individuels et les effectifs "
                          "déclarés. Risque de double comptage : vérifiez qu'aucune personne n'est "
                          "comptée à la fois dans un dossier et dans un effectif déclaré."),
    })


@permission_requise("membres", "creer")
def effectif_creer(request):
    e = _eglise(request)
    d = corps(request)
    try:
        valeur = int(d.get("valeur") or 0)
    except (TypeError, ValueError):
        return err("La valeur doit être un nombre entier.")
    if valeur < 0:
        return err("La valeur ne peut pas être négative.")
    x = EffectifDeclare.objects.create(
        eglise=e, categorie=d.get("categorie") or "adultes", valeur=valeur,
        periode=(d.get("periode") or f"{timezone.now():%m/%Y}")[:40],
        observation=(d.get("observation") or "")[:400], auteur=request.utilisateur)
    tracer(request.utilisateur, "membres", "effectif",
           f"Effectif déclaré : {x.get_categorie_display()} = {valeur} ({x.periode})")
    return ok({"effectif": {"id": x.id, "categorie": x.categorie, "valeur": x.valeur,
                            "periode": x.periode}})


# ─────────────────────── paramètres de matricule ───────────────────────

@permission_requise("parametres", "consulter")
def matricule_parametres(request):
    e = _eglise(request)
    p, _ = ParametreMatricule.objects.get_or_create(
        eglise=e, defaults={"prefixe": _prefixe_ascii(e.nom)})
    if request.method == "POST":
        d = corps(request)
        if (d.get("prefixe") or "").strip():
            p.prefixe = d["prefixe"].strip().upper()[:20]
        if "inclure_annee" in d:
            p.inclure_annee = bool(d["inclure_annee"])
        if d.get("chiffres"):
            p.chiffres = max(2, min(8, int(d["chiffres"])))
        if d.get("separateur") is not None:
            p.separateur = (d["separateur"] or "-")[:3]
        p.save()
        tracer(request.utilisateur, "parametres", "matricule",
               f"Format du matricule : {p.prefixe}, année {p.inclure_annee}, {p.chiffres} chiffres")
    exemple = p.separateur.join([p.prefixe.upper()] + ([str(timezone.now().year)] if p.inclure_annee else [])
                                + [str(p.compteur + 1).zfill(p.chiffres)])
    return ok({"prefixe": p.prefixe, "inclure_annee": p.inclure_annee,
               "chiffres": p.chiffres, "separateur": p.separateur,
               "compteur": p.compteur, "exemple": exemple})


# ─────────────────────────── groupes ───────────────────────────

def _groupe_json(g, avec_membres=False):
    d = {"id": g.id, "nom": g.nom, "type": g.type, "description": g.description,
         "actif": g.actif, "parent_id": g.parent_id,
         "parent_nom": g.parent.nom if g.parent_id else None,
         "responsable_id": g.responsable_id,
         "responsable": g.responsable.nom_complet if g.responsable_id else None,
         "effectif": g.membres.filter(date_fin__isnull=True).count()}
    if avec_membres:
        d["membres"] = [{"id": a.membre_id,
                         "nom_complet": a.membre.nom_complet,
                         "matricule": a.membre.matricule,
                         "fonction": a.fonction,
                         "date_debut": a.date_debut.isoformat() if a.date_debut else None}
                        for a in g.membres.select_related("membre").filter(date_fin__isnull=True)]
    return d


@permission_requise("groupes", "consulter")
def groupes_liste(request):
    e = _eglise(request)
    gs = Groupe.objects.filter(eglise=e).select_related("parent", "responsable")
    return ok({"groupes": [_groupe_json(g) for g in gs],
               "types": ["département", "ministère", "cellule", "chorale", "équipe",
                         "groupe de prière", "jeunesse", "autre"]})


@permission_requise("groupes", "creer")
def groupe_creer(request):
    e = _eglise(request)
    d = corps(request)
    if not (d.get("nom") or "").strip():
        return err("Le nom du groupe est obligatoire.")
    g = Groupe.objects.create(
        eglise=e, nom=d["nom"].strip()[:150], type=(d.get("type") or "département")[:60],
        description=(d.get("description") or "")[:400],
        parent_id=d.get("parent_id") or None,
        responsable_id=d.get("responsable_id") or None)
    tracer(request.utilisateur, "groupes", "creation", f"Groupe créé : {g.nom}")
    return ok({"groupe": _groupe_json(g)})


@permission_requise("groupes", "modifier")
def groupe_modifier(request):
    e = _eglise(request)
    d = corps(request)
    g = Groupe.objects.filter(eglise=e, id=d.get("id")).first()
    if not g:
        return err("Groupe introuvable dans cette Église.", 404)
    for champ in ("nom", "type", "description"):
        if d.get(champ) is not None:
            setattr(g, champ, str(d[champ])[:400])
    if "responsable_id" in d:
        g.responsable_id = d["responsable_id"] or None
    if "parent_id" in d:
        g.parent_id = d["parent_id"] or None
    if "actif" in d:
        g.actif = bool(d["actif"])
    g.save()
    tracer(request.utilisateur, "groupes", "modification", f"Groupe modifié : {g.nom}")
    return ok({"groupe": _groupe_json(g)})


@permission_requise("groupes", "supprimer")
def groupe_supprimer(request):
    e = _eglise(request)
    d = corps(request)
    g = Groupe.objects.filter(eglise=e, id=d.get("id")).first()
    if not g:
        return err("Groupe introuvable dans cette Église.", 404)
    nom = g.nom
    g.actif = False
    g.save(update_fields=["actif"])
    tracer(request.utilisateur, "groupes", "archivage", f"Groupe désactivé : {nom}")
    return ok({"desactive": True})


@permission_requise("groupes", "modifier")
def groupe_affecter(request):
    e = _eglise(request)
    d = corps(request)
    m = Membre.objects.filter(eglise=e, id=d.get("membre_id")).first()
    g = Groupe.objects.filter(eglise=e, id=d.get("groupe_id")).first()
    if not m or not g:
        return err("Membre ou groupe introuvable dans cette Église.", 404)
    a, cree = MembreGroupe.objects.get_or_create(
        membre=m, groupe=g,
        defaults={"fonction": (d.get("fonction") or "membre")[:80],
                  "date_debut": _date(d.get("date_debut")) or timezone.now().date()})
    if not cree:
        a.fonction = (d.get("fonction") or a.fonction)[:80]
        a.date_fin = None
        a.save()
    tracer(request.utilisateur, "groupes", "affectation",
           f"{m.nom_complet} → {g.nom} ({a.fonction})")
    return ok({"affectation": {"groupe": g.nom, "membre": m.nom_complet, "fonction": a.fonction}})


@permission_requise("groupes", "modifier")
def groupe_retirer(request):
    e = _eglise(request)
    d = corps(request)
    a = MembreGroupe.objects.filter(membre__eglise=e, groupe__eglise=e,
                                    membre_id=d.get("membre_id"),
                                    groupe_id=d.get("groupe_id")).first()
    if not a:
        return err("Appartenance introuvable.", 404)
    a.date_fin = timezone.now().date()
    a.save()
    tracer(request.utilisateur, "groupes", "retrait",
           f"{a.membre.nom_complet} retiré de {a.groupe.nom}")
    return ok({"retire": True})


# ─────────────────── événements pointés et présences ───────────────────

@permission_requise("presences", "consulter")
def evenements_liste(request):
    e = _eglise(request)
    qs = Evenement.objects.filter(eglise=e).select_related("groupe")[:80]
    return ok({"evenements": [{"id": x.id, "titre": x.titre, "type": x.type,
                               "date": x.date.isoformat(), "heure": x.heure,
                               "heure_fin": x.heure_fin, "statut": x.statut,
                               "description": x.description, "capacite": x.capacite,
                               "lieu": x.lieu, "groupe": x.groupe.nom if x.groupe_id else None,
                               "pointes": x.presences.count()} for x in qs],
               "types": [{"code": c, "label": l} for c, l in Evenement.TYPES]})


@permission_requise("presences", "creer")
def evenement_creer(request):
    e = _eglise(request)
    d = corps(request)
    if not (d.get("titre") or "").strip():
        return err("Le titre de l'activité est obligatoire.")
    date_ev = _date(d.get("date")) or timezone.now().date()
    ev = Evenement.objects.create(
        eglise=e, titre=d["titre"].strip()[:200], type=d.get("type") or "culte",
        date=date_ev, heure=(d.get("heure") or "")[:10], lieu=(d.get("lieu") or "")[:200],
        groupe_id=d.get("groupe_id") or None)
    tracer(request.utilisateur, "presences", "evenement",
           f"Activité créée : {ev.titre} du {ev.date}")
    return ok({"evenement": {"id": ev.id, "titre": ev.titre, "date": ev.date.isoformat()}})


@permission_requise("presences", "consulter")
def presences_liste(request):
    e = _eglise(request)
    ev = Evenement.objects.filter(eglise=e, id=request.GET.get("evenement")).first()
    if not ev:
        return err("Activité introuvable dans cette Église.", 404)
    lignes = Presence.objects.filter(eglise=e, evenement=ev).select_related("membre")
    identifiees = lignes.filter(membre__isnull=False)
    globales = lignes.filter(membre__isnull=True, effectif_global__isnull=False)
    return ok({
        "evenement": {"id": ev.id, "titre": ev.titre, "date": ev.date.isoformat(),
                      "type": ev.type, "lieu": ev.lieu},
        "presences": [{"id": p.id,
                       "membre": p.membre.nom_complet if p.membre_id else None,
                       "matricule": p.membre.matricule if p.membre_id else None,
                       "visiteur": p.visiteur_nom, "statut": p.statut,
                       "effectif_global": p.effectif_global,
                       "observation": p.observation} for p in lignes],
        "total_identifies": identifiees.count(),
        "retards": identifiees.filter(statut="retard").count(),
        "visiteurs": lignes.filter(membre__isnull=True).exclude(visiteur_nom="").count(),
        "effectif_global": globales.aggregate(s=Sum("effectif_global"))["s"] or 0,
    })


@permission_requise("presences", "creer")
def presence_pointer(request):
    """Pointage d'un membre, d'un visiteur, ou saisie d'un effectif global.
    Aucun doublon : un membre n'est pointé qu'une fois par activité."""
    e = _eglise(request)
    d = corps(request)
    ev = Evenement.objects.filter(eglise=e, id=d.get("evenement")).first()
    if not ev:
        return err("Activité introuvable dans cette Église.", 404)
    mid = d.get("membre_id")
    if mid:
        m = Membre.objects.filter(eglise=e, id=mid).first()
        if not m:
            return err("Membre introuvable dans cette Église.", 404)
        p, cree = Presence.objects.get_or_create(
            eglise=e, evenement=ev, membre=m,
            defaults={"statut": d.get("statut") or "present",
                      "pointe_par": request.utilisateur})
        if not cree:
            p.statut = d.get("statut") or p.statut
            p.save(update_fields=["statut"])
        return ok({"presence": {"id": p.id, "membre": m.nom_complet, "statut": p.statut},
                   "nouveau": cree})
    if d.get("visiteur_nom"):
        p = Presence.objects.create(eglise=e, evenement=ev,
                                    visiteur_nom=str(d["visiteur_nom"])[:200],
                                    statut="present", pointe_par=request.utilisateur)
        return ok({"presence": {"id": p.id, "visiteur": p.visiteur_nom}})
    if d.get("effectif_global") is not None:
        try:
            v = int(d["effectif_global"])
        except (TypeError, ValueError):
            return err("L'effectif doit être un nombre entier.")
        if v < 0:
            return err("L'effectif ne peut pas être négatif.")
        p = Presence.objects.create(eglise=e, evenement=ev, effectif_global=v,
                                    statut="present", pointe_par=request.utilisateur)
        tracer(request.utilisateur, "presences", "effectif",
               f"Effectif global pointé sur {ev.titre} : {v}")
        return ok({"presence": {"id": p.id, "effectif_global": v}})
    return err("Indiquez un membre, un nom de visiteur ou un effectif global.")


@permission_requise("presences", "supprimer")
def presence_supprimer(request):
    e = _eglise(request)
    p = Presence.objects.filter(eglise=e, id=corps(request).get("id")).first()
    if not p:
        return err("Pointage introuvable dans cette Église.", 404)
    p.delete()
    return ok({"supprime": True})


@permission_requise("presences", "consulter")
def presences_stats(request):
    e = _eglise(request)
    par_evenement = []
    for ev in Evenement.objects.filter(eglise=e)[:24]:
        lignes = Presence.objects.filter(eglise=e, evenement=ev)
        par_evenement.append({
            "id": ev.id, "titre": ev.titre, "date": ev.date.isoformat(),
            "identifies": lignes.filter(membre__isnull=False).count(),
            "effectif_global": lignes.filter(effectif_global__isnull=False).aggregate(
                s=Sum("effectif_global"))["s"] or 0})
    return ok({"par_evenement": par_evenement,
               "moyenne_identifies": round(
                   sum(x["identifies"] for x in par_evenement) / len(par_evenement), 1)
               if par_evenement else 0})


# ────────────────────── documents de base (PDF) ──────────────────────

def _pdf_entete(e):
    from reportlab.lib.colors import HexColor
    return HexColor(e.couleur_primaire or "#16233F"), HexColor(e.couleur_accent or "#C9A227")


@permission_requise("documents", "consulter")
def document_fiche(request):
    """Fiche administrative du membre en PDF, avec l'identité visuelle de l'Église."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm

    e = _eglise(request)
    m = Membre.objects.filter(eglise=e, id=request.GET.get("id")).first()
    if not m:
        return err("Membre introuvable dans cette Église.", 404)
    bleu, or_ = _pdf_entete(e)
    tampon = io.BytesIO()
    c = canvas.Canvas(tampon, pagesize=A4)
    L, H = A4
    c.setFillColor(bleu)
    c.rect(0, H - 34 * mm, L, 34 * mm, stroke=0, fill=1)
    c.setFillColor(or_)
    c.rect(0, H - 36 * mm, L, 2 * mm, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(20 * mm, H - 17 * mm, e.nom[:60])
    c.setFont("Helvetica", 9.5)
    c.drawString(20 * mm, H - 23 * mm, (e.denomination or "Église") + " · " + e.ville)
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(L - 20 * mm, H - 17 * mm, "FICHE ADMINISTRATIVE")
    c.drawRightString(L - 20 * mm, H - 22 * mm, m.matricule or "—")

    y = H - 52 * mm
    c.setFillColor(bleu)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, m.nom_complet)
    y -= 9 * mm
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(.35, .35, .35)
    c.drawString(20 * mm, y, f"Statut : {m.get_statut_display()} · Dossier {m.get_etat_validation_display()}")
    y -= 12 * mm

    def ligne(label, valeur):
        nonlocal y
        c.setFillColorRGB(.45, .45, .45); c.setFont("Helvetica", 8.5)
        c.drawString(20 * mm, y, label.upper())
        c.setFillColorRGB(.1, .1, .1); c.setFont("Helvetica", 10.5)
        c.drawString(62 * mm, y, str(valeur or "—")[:70])
        y -= 8 * mm

    c.setFillColor(bleu); c.setFont("Helvetica-Bold", 10.5)
    c.drawString(20 * mm, y, "IDENTITÉ"); y -= 7 * mm
    ligne("Sexe", m.get_sexe_display() if m.sexe else "")
    ligne("Date de naissance", f"{m.date_naissance:%d/%m/%Y}" if m.date_naissance else "")
    ligne("Lieu de naissance", m.lieu_naissance)
    ligne("Nationalité", m.nationalite)
    ligne("État civil", m.etat_civil)
    ligne("Profession", m.profession)
    y -= 3 * mm
    c.setFillColor(bleu); c.setFont("Helvetica-Bold", 10.5)
    c.drawString(20 * mm, y, "COORDONNÉES"); y -= 7 * mm
    ligne("Téléphone", m.telephone)
    ligne("E-mail", m.email)
    ligne("Adresse", m.adresse)
    ligne("Personne à contacter", m.contact_urgence)
    y -= 3 * mm
    c.setFillColor(bleu); c.setFont("Helvetica-Bold", 10.5)
    c.drawString(20 * mm, y, "VIE DANS L'ÉGLISE"); y -= 7 * mm
    ligne("Adhésion", f"{m.date_adhesion:%d/%m/%Y}" if m.date_adhesion else "")
    ligne("Ordination", f"{m.date_ordination:%d/%m/%Y}" if m.date_ordination else "")
    groupes = ", ".join(a.groupe.nom for a in m.appartenances.select_related("groupe").all())
    ligne("Groupes", groupes)

    c.setFillColorRGB(.55, .55, .55); c.setFont("Helvetica", 7.5)
    c.drawString(20 * mm, 16 * mm, f"Document généré le {timezone.now():%d/%m/%Y à %H:%M} · "
                                   f"{e.nom} · OmniChurch Connect")
    c.drawString(20 * mm, 12 * mm, "Cette fiche ne constitue pas une certification officielle.")
    c.showPage(); c.save()
    tracer(request.utilisateur, "documents", "fiche",
           f"Fiche PDF générée : {m.nom_complet} · {m.matricule}")
    rep = HttpResponse(tampon.getvalue(), content_type="application/pdf")
    rep["Content-Disposition"] = f'inline; filename="fiche-{m.matricule or m.id}.pdf"'
    return rep


@permission_requise("documents", "consulter")
def document_carte(request):
    """Carte de membre au format carte de visite, imprimable en série."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm

    e = _eglise(request)
    m = Membre.objects.filter(eglise=e, id=request.GET.get("id")).first()
    if not m:
        return err("Membre introuvable dans cette Église.", 404)
    if not m.matricule:
        return err("La carte n'est délivrée qu'après validation du dossier et attribution du matricule.")
    bleu, or_ = _pdf_entete(e)
    tampon = io.BytesIO()
    c = canvas.Canvas(tampon, pagesize=A4)
    x, y, w, h = 20 * mm, 240 * mm, 85 * mm, 54 * mm
    c.setFillColor(bleu); c.roundRect(x, y, w, h, 3 * mm, stroke=0, fill=1)
    c.setFillColor(or_); c.roundRect(x, y + h - 13 * mm, w, 13 * mm, 3 * mm, stroke=0, fill=1)
    c.setFillColor(bleu); c.setFont("Helvetica-Bold", 7.5)
    c.drawString(x + 4 * mm, y + h - 8 * mm, e.nom[:38].upper())
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x + 4 * mm, y + h - 22 * mm, m.nom_complet[:30])
    c.setFont("Helvetica", 7)
    c.drawString(x + 4 * mm, y + h - 27 * mm, f"{m.get_statut_display()}")
    c.setFillColor(or_)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 4 * mm, y + 6 * mm, m.matricule)
    c.setFont("Helvetica", 6)
    c.setFillColorRGB(.8, .8, .8)
    c.drawString(x + 4 * mm, y + 3 * mm, "CARTE DE MEMBRE")
    c.setFillColorRGB(.4, .4, .4); c.setFont("Helvetica", 7.5)
    c.drawString(20 * mm, 20 * mm, f"Carte délivrée le {timezone.now():%d/%m/%Y} · "
                                   f"{e.ville or e.pays} · OmniChurch Connect")
    c.showPage(); c.save()
    tracer(request.utilisateur, "documents", "carte",
           f"Carte de membre générée : {m.nom_complet} · {m.matricule}")
    rep = HttpResponse(tampon.getvalue(), content_type="application/pdf")
    rep["Content-Disposition"] = f'inline; filename="carte-{m.matricule}.pdf"'
    return rep


# ───────────────────────── tableau de bord ─────────────────────────

@auth_requise()
def bord_stats(request):
    """Chiffres réels du tableau de bord : membres, validation, effectifs, présences, groupes."""
    u = request.utilisateur
    if not u.eglise:
        return ok({"super": True})
    e = u.eglise
    membres = Membre.objects.filter(eglise=e)
    total_identifies = Presence.objects.filter(eglise=e, membre__isnull=False).count()
    globales = Presence.objects.filter(eglise=e, effectif_global__isnull=False).aggregate(
        s=Sum("effectif_global"))["s"] or 0
    return ok({
        "super": False,
        "membres_total": membres.count(),
        "membres_valides": membres.filter(etat_validation="valide").count(),
        "membres_a_valider": membres.filter(etat_validation="a_valider").count(),
        "membres_retournes": membres.filter(etat_validation="retourne").count(),
        "nouveaux_30j": membres.filter(created_at__gte=timezone.now() - timedelta(days=30)).count(),
        "effectif_declare": EffectifDeclare.objects.filter(eglise=e).aggregate(s=Sum("valeur"))["s"] or 0,
        "groupes": Groupe.objects.filter(eglise=e, actif=True).count(),
        "evenements": Evenement.objects.filter(eglise=e).count(),
        "presences_identifiees": total_identifies,
        "presences_globales": globales,
        "hommes": membres.filter(sexe="M").count(),
        "femmes": membres.filter(sexe="F").count(),
    })
