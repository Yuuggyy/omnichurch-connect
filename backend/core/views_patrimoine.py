"""API OmniChurch Connect — Phase 5 : patrimoine et équipements (section 18).

Inventaire des biens durables, affectations, prêts, entretiens, réparations, réformes,
alertes sur les biens à réparer ou hors service, export d'inventaire.
Tout est filtré sur l'Église de l'utilisateur authentifié.
"""
import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q, Sum
from django.utils import timezone

from core.models import (Membre, Groupe, BienPatrimoine, MouvementBien, JournalAudit,
                         ETATS_BIEN, CATEGORIES_BIEN, TYPES_MOUVEMENT_BIEN)
from core.security import auth_requise, permission_requise, tracer
from core.views_api import ok, err, corps
from django.http import HttpResponse


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


def _decimal(v, defaut=Decimal("0")):
    try:
        return Decimal(str(v).replace(" ", "").replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return defaut


def _n(valeur):
    if valeur is None:
        return "0.00"
    return str(Decimal(str(valeur)).quantize(Decimal("0.01")))


def _json_bien(b):
    return {
        "id": b.id, "code": b.code, "nom": b.nom, "categorie": b.categorie,
        "categorie_libelle": b.get_categorie_display(), "description": b.description,
        "quantite": b.quantite, "etat": b.etat, "etat_libelle": b.get_etat_display(),
        "date_acquisition": b.date_acquisition.isoformat() if b.date_acquisition else None,
        "valeur_achat": _n(b.valeur_achat), "valeur_totale": _n(b.valeur_totale()),
        "devise": b.devise, "localisation": b.localisation,
        "responsable": f"{b.responsable.nom} {b.responsable.prenom}".strip() if b.responsable_id else "",
        "groupe": b.groupe.nom if b.groupe_id else "",
        "justificatif": bool(b.justificatif_url), "observation": b.observation,
        "dernier_mouvement": b.mouvements.first().date.isoformat() if b.mouvements.exists() else None,
    }


@auth_requise()
@permission_requise("patrimoine", "consulter")
def biens_liste(request):
    e = _eglise(request)
    qs = BienPatrimoine.objects.filter(eglise=e).select_related("responsable", "groupe")
    if request.GET.get("categorie"):
        qs = qs.filter(categorie=request.GET["categorie"])
    if request.GET.get("etat"):
        qs = qs.filter(etat=request.GET["etat"])
    if request.GET.get("q"):
        terme = request.GET["q"]
        qs = qs.filter(Q(nom__icontains=terme) | Q(code__icontains=terme) |
                       Q(localisation__icontains=terme))
    biens = [_json_bien(b) for b in qs[:400]]
    totaux = {}
    for devise in ("USD", "CDF"):
        totaux[devise] = _n(sum((b.valeur_totale() for b in qs if b.devise == devise),
                                Decimal("0")))
    return ok({
        "biens": biens,
        "totaux": totaux,
        "nombre": qs.count(),
        "par_categorie": [{"categorie": c, "libelle": lib, "nombre": n}
                          for c, lib, n in
                          [(x["categorie"], dict(CATEGORIES_BIEN)[x["categorie"]], x["n"])
                           for x in qs.values("categorie").annotate(n=Count("id"))]],
        "alertes": {
            "a_reparer": qs.filter(etat="a_reparer").count(),
            "hors_service": qs.filter(etat="hors_service").count(),
            "sans_justificatif": qs.filter(justificatif_url="").count(),
            "sans_responsable": qs.filter(responsable__isnull=True).count(),
        },
        "categories": [{"code": c, "libelle": l} for c, l in CATEGORIES_BIEN],
        "etats": [{"code": c, "libelle": l} for c, l in ETATS_BIEN],
    })


@auth_requise()
@permission_requise("patrimoine", "creer")
def bien_creer(request):
    e = _eglise(request)
    d = corps(request)
    nom = (d.get("nom") or "").strip()
    if not nom:
        return err("Le nom du bien est obligatoire.")
    categorie = d.get("categorie") or "mobilier"
    if categorie not in dict(CATEGORIES_BIEN):
        return err("Catégorie de bien inconnue.")
    code = (d.get("code") or "").strip()[:40]
    if code and BienPatrimoine.objects.filter(eglise=e, code=code).exists():
        return err("Ce code est déjà utilisé dans cette Église.")
    brut = d.get("quantite")
    try:
        quantite = 1 if brut in (None, "") else int(brut)
    except (TypeError, ValueError):
        return err("La quantité doit être un nombre entier.")
    if quantite < 1:
        return err("La quantité doit être au moins de 1.")
    b = BienPatrimoine.objects.create(
        eglise=e, nom=nom[:200], code=code, categorie=categorie,
        description=(d.get("description") or "").strip(),
        quantite=quantite, date_acquisition=_date(d.get("date_acquisition")),
        valeur_achat=_decimal(d.get("valeur_achat")),
        devise=d.get("devise") or "USD",
        localisation=(d.get("localisation") or "")[:200],
        responsable_id=d.get("responsable_id") or None,
        groupe_id=d.get("groupe_id") or None,
        etat=d.get("etat") or "bon",
        justificatif_url=(d.get("justificatif_url") or "")[:500],
        observation=(d.get("observation") or "")[:400],
        cree_par=request.utilisateur)
    tracer(request.utilisateur, "patrimoine", "creer", f"Bien enregistré : {b.nom} ({b.code or 'sans code'})")
    return ok({"bien": _json_bien(b)})


@auth_requise()
@permission_requise("patrimoine", "modifier")
def bien_modifier(request):
    e = _eglise(request)
    d = corps(request)
    b = BienPatrimoine.objects.filter(eglise=e, id=d.get("id")).first()
    if not b:
        return err("Bien introuvable dans cette Église.", 404)
    if d.get("nom"):
        b.nom = d["nom"].strip()[:200]
    if d.get("etat") in dict(ETATS_BIEN):
        b.etat = d["etat"]
    if d.get("localisation") is not None:
        b.localisation = (d["localisation"] or "")[:200]
    if d.get("description") is not None:
        b.description = d["description"]
    if d.get("observation") is not None:
        b.observation = (d["observation"] or "")[:400]
    if d.get("code") is not None:
        nouveau = (d["code"] or "").strip()[:40]
        if nouveau and BienPatrimoine.objects.filter(eglise=e, code=nouveau).exclude(id=b.id).exists():
            return err("Ce code est déjà utilisé dans cette Église.")
        b.code = nouveau
    if d.get("responsable_id") is not None:
        b.responsable_id = d["responsable_id"] or None
    if d.get("justificatif_url") is not None:
        b.justificatif_url = (d["justificatif_url"] or "")[:500]
    if d.get("valeur_achat") is not None:
        b.valeur_achat = _decimal(d["valeur_achat"])
    b.save()
    tracer(request.utilisateur, "patrimoine", "modifier", f"Bien modifié : {b.nom}")
    return ok({"bien": _json_bien(b)})


@auth_requise()
@permission_requise("patrimoine", "consulter")
def bien_detail(request):
    e = _eglise(request)
    b = BienPatrimoine.objects.filter(eglise=e, id=request.GET.get("id")).select_related(
        "responsable", "groupe").first()
    if not b:
        return err("Bien introuvable dans cette Église.", 404)
    data = _json_bien(b)
    data["mouvements"] = [{"id": m.id, "type": m.type, "type_libelle": m.get_type_display(),
                           "date": m.date.isoformat(), "personne": m.personne or (
                               f"{m.membre.nom} {m.membre.prenom}".strip() if m.membre_id else ""),
                           "lieu": m.lieu, "cout": _n(m.cout) if m.cout is not None else None,
                           "note": m.note}
                          for m in MouvementBien.objects.filter(bien=b).select_related("membre")]
    return ok({"bien": data})


@auth_requise()
@permission_requise("patrimoine", "modifier")
def bien_mouvement(request):
    """Affectation, prêt, retour, entretien, réparation, réforme, constat d'inventaire."""
    e = _eglise(request)
    d = corps(request)
    b = BienPatrimoine.objects.filter(eglise=e, id=d.get("bien_id")).first()
    if not b:
        return err("Bien introuvable dans cette Église.", 404)
    type_mvt = d.get("type") or "affectation"
    if type_mvt not in dict(TYPES_MOUVEMENT_BIEN):
        return err("Type de mouvement inconnu.")
    if b.etat == "reforme" and type_mvt not in ("inventaire",):
        return err("Ce bien est réformé : son état ne peut plus évoluer que par un constat d'inventaire.")
    m = MouvementBien.objects.create(
        eglise=e, bien=b, type=type_mvt, date=_date(d.get("date")) or timezone.localdate(),
        personne=(d.get("personne") or "")[:150], membre_id=d.get("membre_id") or None,
        lieu=(d.get("lieu") or "")[:200],
        cout=_decimal(d["cout"]) if d.get("cout") not in (None, "") else None,
        note=(d.get("note") or "")[:400], cree_par=request.utilisateur)
    # effets sur l'état du bien
    if type_mvt == "reparation":
        b.etat = "bon"
    elif type_mvt == "reforme":
        b.etat = "reforme"
    elif type_mvt == "reparation" or (type_mvt == "entretien" and b.etat == "a_reparer"):
        b.etat = "bon"
    if type_mvt == "affectation" and d.get("lieu"):
        b.localisation = (d["lieu"] or "")[:200]
    b.save(update_fields=["etat", "localisation", "updated_at"] if type_mvt == "affectation"
           else ["etat", "updated_at"])
    tracer(request.utilisateur, "patrimoine", "modifier",
           f"{m.get_type_display()} du bien {b.nom}" + (f" (coût {m.cout})" if m.cout else ""))
    return ok({"mouvement": {"id": m.id, "type": m.type, "etat_bien": b.etat}})


@auth_requise()
@permission_requise("patrimoine", "consulter")
def biens_alertes(request):
    e = _eglise(request)
    qs = BienPatrimoine.objects.filter(eglise=e)
    return ok({
        "a_reparer": [_json_bien(b) for b in qs.filter(etat="a_reparer")],
        "hors_service": [_json_bien(b) for b in qs.filter(etat="hors_service")],
        "sans_justificatif": [_json_bien(b) for b in qs.filter(justificatif_url="")],
        "sans_responsable": [_json_bien(b) for b in qs.filter(responsable__isnull=True)],
        "cout_entretien_annee": _n(MouvementBien.objects.filter(
            eglise=e, date__year=timezone.localdate().year).aggregate(
            s=Sum("cout"))["s"] or 0),
    })


@auth_requise()
@permission_requise("patrimoine", "exporter")
def biens_export(request):
    e = _eglise(request)
    qs = BienPatrimoine.objects.filter(eglise=e).select_related("responsable", "groupe")
    sortie = io.StringIO()
    w = csv.writer(sortie, delimiter=";")
    w.writerow(["Code", "Nom", "Catégorie", "Quantité", "État", "Date d'acquisition",
                "Valeur unitaire", "Valeur totale", "Devise", "Localisation", "Responsable",
                "Département", "Justificatif", "Observation"])
    for b in qs:
        w.writerow([b.code, b.nom, b.get_categorie_display(), b.quantite, b.get_etat_display(),
                    b.date_acquisition or "", b.valeur_achat, b.valeur_totale(), b.devise,
                    b.localisation,
                    f"{b.responsable.nom} {b.responsable.prenom}".strip() if b.responsable_id else "",
                    b.groupe.nom if b.groupe_id else "",
                    "oui" if b.justificatif_url else "non", b.observation])
    reponse = HttpResponse("\ufeff" + sortie.getvalue(), content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = 'attachment; filename="inventaire-patrimoine.csv"'
    tracer(request.utilisateur, "patrimoine", "exporter", "Export de l'inventaire du patrimoine")
    return reponse
