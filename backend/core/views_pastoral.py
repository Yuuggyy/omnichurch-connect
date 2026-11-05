"""Suivi pastoral et accompagnement (section 16) : dossiers, actions, prières, confidentialité."""
import csv
import io
from datetime import date, timedelta

from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone

from core.models import (ActionPastorale, DemandePriere, DossierPastoral, Membre, Utilisateur)
from core.security import auth_requise, permission_requise, a_permission, tracer
from core.views_api import ok, err, corps


def _eglise(request):
    return request.utilisateur.eglise


def _date(v):
    """Convertit 'AAAA-MM-JJ' en date, sinon renvoie None."""
    if not v:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


# ── confidentialité ───────────────────────────────────────────────────────────
def _peut_voir(user, dossier):
    """Un dossier confidentiel n'est lisible que par son responsable, son auteur
    et les détenteurs du droit de validation pastorale."""
    if dossier.confidentialite != "confidentiel":
        return True
    if user.is_super_admin or user.is_admin_principal:
        return True
    if dossier.responsable_id == user.id or dossier.cree_par_id == user.id:
        return True
    return a_permission(user, "pastoral", "valider")


def _numero(e):
    annee = timezone.now().year
    dernier = DossierPastoral.objects.filter(eglise=e, numero__startswith=f"DP-{annee}-").count()
    return f"DP-{annee}-{dernier + 1:05d}"


def _json_dossier(d, avec_actions=False):
    donnees = {
        "id": d.id, "numero": d.numero, "personne_nom": d.personne_nom,
        "membre_id": d.membre_id, "telephone": d.telephone, "type": d.type,
        "objet": d.objet, "nature_demande": d.nature_demande, "statut": d.statut,
        "confidentialite": d.confidentialite, "priorite": d.priorite,
        "responsable": d.responsable.nom_complet if d.responsable_id else None,
        "responsable_id": d.responsable_id,
        "prochaine_etape": d.prochaine_etape,
        "echeance": d.echeance.isoformat() if d.echeance else None,
        "en_retard": bool(d.echeance and d.echeance < date.today()
                          and d.statut not in ("clos", "abandonne")),
        "actions": d.actions.count(), "cree_le": d.created_at.isoformat()[:10],
    }
    if avec_actions:
        donnees["historique"] = [{
            "id": a.id, "type": a.type, "date": a.date.isoformat(), "lieu": a.lieu,
            "resume": a.resume, "confidentiel": a.confidentiel,
            "fait_par": a.fait_par.nom_complet if a.fait_par_id else None,
        } for a in d.actions.select_related("fait_par").all()]
    return donnees


# ── dossiers ──────────────────────────────────────────────────────────────────
@auth_requise()
@permission_requise("pastoral", "consulter")
def dossiers_liste(request):
    e = _eglise(request)
    d = corps(request)
    qs = DossierPastoral.objects.filter(eglise=e).select_related("responsable")
    if d.get("type"):
        qs = qs.filter(type=d["type"])
    if d.get("statut"):
        qs = qs.filter(statut=d["statut"])
    if d.get("confidentialite"):
        qs = qs.filter(confidentialite=d["confidentialite"])
    if d.get("responsable_id"):
        qs = qs.filter(responsable_id=d["responsable_id"])
    if d.get("retard"):
        qs = qs.filter(echeance__lt=date.today()).exclude(statut__in=["clos", "abandonne"])
    if d.get("q"):
        qs = qs.filter(Q(personne_nom__icontains=d["q"]) | Q(numero__icontains=d["q"]) |
                       Q(objet__icontains=d["q"]))
    total = qs.count()
    dossiers = [x for x in qs[:200] if _peut_voir(request.utilisateur, x)]
    return ok({"dossiers": [_json_dossier(x) for x in dossiers], "total": total,
               "masques": total - len(dossiers)})


@auth_requise()
@permission_requise("pastoral", "consulter")
def dossier_detail(request):
    e = _eglise(request)
    d = corps(request)
    dossier = DossierPastoral.objects.filter(eglise=e, id=d.get("id")).first()
    if not dossier:
        return err("Dossier introuvable.", 404)
    if not _peut_voir(request.utilisateur, dossier):
        return err("Dossier confidentiel : accès non autorisé.", 403)
    if dossier.confidentialite == "confidentiel":
        tracer(request.utilisateur, "pastoral", "consulter",
               f"Consultation du dossier confidentiel {dossier.numero}")
    return ok({"dossier": _json_dossier(dossier, avec_actions=True)})


@auth_requise()
@permission_requise("pastoral", "creer")
def dossier_creer(request):
    e = _eglise(request)
    d = corps(request)
    nom = (d.get("personne_nom") or "").strip()
    if not nom and d.get("membre_id"):
        m = Membre.objects.filter(eglise=e, id=d.get("membre_id")).first()
        nom = f"{m.nom} {m.prenom}".strip() if m else ""
    if not nom:
        return err("Le nom de la personne concernée est obligatoire.")
    membre = None
    if d.get("membre_id"):
        membre = Membre.objects.filter(eglise=e, id=d.get("membre_id")).first()
        if not membre:
            return err("Ce membre n'appartient pas à votre Église.")
    responsable = None
    if d.get("responsable_id"):
        responsable = Utilisateur.objects.filter(eglise=e, id=d.get("responsable_id")).first()
        if not responsable:
            return err("Ce responsable n'appartient pas à votre Église.")
    dossier = DossierPastoral.objects.create(
        eglise=e, numero=_numero(e), personne_nom=nom, membre=membre,
        telephone=d.get("telephone", ""), type=d.get("type", "visite"),
        objet=d.get("objet", ""), nature_demande=d.get("nature_demande", ""),
        responsable=responsable or request.utilisateur,
        statut=d.get("statut", "ouvert"),
        confidentialite=d.get("confidentialite", "normal"),
        priorite=d.get("priorite", "normale"),
        prochaine_etape=d.get("prochaine_etape", ""),
        echeance=_date(d.get("echeance")), ouvert_le=date.today(),
        document_url=d.get("document_url", ""), cree_par=request.utilisateur)
    tracer(request.utilisateur, "pastoral", "creer",
           f"Dossier pastoral {dossier.numero} ouvert pour {dossier.personne_nom}")
    return ok({"dossier": _json_dossier(dossier)})


@auth_requise()
@permission_requise("pastoral", "modifier")
def dossier_modifier(request):
    e = _eglise(request)
    d = corps(request)
    dossier = DossierPastoral.objects.filter(eglise=e, id=d.get("id")).first()
    if not dossier:
        return err("Dossier introuvable.", 404)
    if not _peut_voir(request.utilisateur, dossier):
        return err("Dossier confidentiel : accès non autorisé.", 403)
    for champ in ("telephone", "objet", "nature_demande", "prochaine_etape", "priorite",
                  "document_url"):
        if champ in d:
            setattr(dossier, champ, d[champ])
    if "confidentialite" in d:
        if d["confidentialite"] not in dict(DossierPastoral.NIVEAUX):
            return err("Niveau de confidentialité inconnu.")
        dossier.confidentialite = d["confidentialite"]
    if "echeance" in d:
        dossier.echeance = _date(d["echeance"])
    if "responsable_id" in d:
        r = Utilisateur.objects.filter(eglise=e, id=d["responsable_id"]).first()
        if not r:
            return err("Ce responsable n'appartient pas à votre Église.")
        dossier.responsable = r
    dossier.save()
    tracer(request.utilisateur, "pastoral", "modifier",
           f"Dossier {dossier.numero} modifié")
    return ok({"dossier": _json_dossier(dossier)})


@auth_requise()
@permission_requise("pastoral", "modifier")
def dossier_statut(request):
    e = _eglise(request)
    d = corps(request)
    dossier = DossierPastoral.objects.filter(eglise=e, id=d.get("id")).first()
    if not dossier:
        return err("Dossier introuvable.", 404)
    if not _peut_voir(request.utilisateur, dossier):
        return err("Dossier confidentiel : accès non autorisé.", 403)
    statut = d.get("statut")
    if statut not in dict(DossierPastoral.STATUTS):
        return err("Statut inconnu.")
    dossier.statut = statut
    dossier.clos_le = date.today() if statut in ("clos", "abandonne") else None
    dossier.save(update_fields=["statut", "clos_le", "updated_at"])
    tracer(request.utilisateur, "pastoral", "modifier",
           f"Dossier {dossier.numero} passé à {statut}")
    return ok({"dossier": _json_dossier(dossier)})


# ── actions ──────────────────────────────────────────────────────────────────
@auth_requise()
@permission_requise("pastoral", "modifier")
def action_ajouter(request):
    e = _eglise(request)
    d = corps(request)
    dossier = DossierPastoral.objects.filter(eglise=e, id=d.get("dossier_id")).first()
    if not dossier:
        return err("Dossier introuvable.", 404)
    if not _peut_voir(request.utilisateur, dossier):
        return err("Dossier confidentiel : accès non autorisé.", 403)
    type_action = d.get("type", "visite")
    if type_action not in dict(ActionPastorale.TYPES):
        return err("Type d'action inconnu.")
    action = ActionPastorale.objects.create(
        eglise=e, dossier=dossier, type=type_action,
        date=d.get("date") or date.today(), lieu=d.get("lieu", ""),
        resume=d.get("resume", ""), confidentiel=bool(d.get("confidentiel")),
        fait_par=request.utilisateur, rappel_le=_date(d.get("rappel_le")))
    if dossier.statut == "ouvert":
        dossier.statut = "en_cours"
    if d.get("prochaine_etape"):
        dossier.prochaine_etape = d["prochaine_etape"]
    if "echeance" in d:
        dossier.echeance = _date(d["echeance"])
    dossier.save()
    tracer(request.utilisateur, "pastoral", "creer",
           f"Action {type_action} enregistrée sur le dossier {dossier.numero}")
    return ok({"action": {"id": action.id, "type": action.type, "date": action.date.isoformat()},
               "dossier": _json_dossier(dossier)})


# ── prières ──────────────────────────────────────────────────────────────────
@auth_requise()
@permission_requise("pastoral", "consulter")
def prieres_liste(request):
    e = _eglise(request)
    d = corps(request)
    qs = DemandePriere.objects.filter(eglise=e).select_related("membre")
    if d.get("statut"):
        qs = qs.filter(statut=d["statut"])
    if d.get("urgence"):
        qs = qs.filter(urgence=d["urgence"])
    prieres = qs[:200]
    return ok({"prieres": [{
        "id": p.id, "sujet": p.sujet, "detail": p.detail,
        "personne": p.personne_nom or (f"{p.membre.nom} {p.membre.prenom}".strip() if p.membre_id else ""),
        "urgence": p.urgence, "statut": p.statut, "confidentiel": p.confidentiel,
        "recue_le": p.recue_le.isoformat() if p.recue_le else p.created_at.isoformat()[:10],
    } for p in prieres], "total": qs.count(),
        "nouvelles": qs.filter(statut="nouvelle").count()})


@auth_requise()
@permission_requise("pastoral", "creer")
def priere_creer(request):
    e = _eglise(request)
    d = corps(request)
    sujet = (d.get("sujet") or "").strip()
    if not sujet:
        return err("Le sujet de la prière est obligatoire.")
    membre = None
    if d.get("membre_id"):
        membre = Membre.objects.filter(eglise=e, id=d.get("membre_id")).first()
    p = DemandePriere.objects.create(
        eglise=e, membre=membre, personne_nom=d.get("personne_nom", ""), sujet=sujet,
        detail=d.get("detail", ""), urgence=d.get("urgence", "normale"),
        confidentiel=bool(d.get("confidentiel")), recue_le=_date(d.get("recue_le")) or date.today(),
        cree_par=request.utilisateur)
    tracer(request.utilisateur, "pastoral", "creer", f"Demande de prière enregistrée : {sujet[:60]}")
    return ok({"priere": {"id": p.id, "sujet": p.sujet, "statut": p.statut}})


@auth_requise()
@permission_requise("pastoral", "modifier")
def priere_statut(request):
    e = _eglise(request)
    d = corps(request)
    p = DemandePriere.objects.filter(eglise=e, id=d.get("id")).first()
    if not p:
        return err("Demande introuvable.", 404)
    statut = d.get("statut")
    if statut not in dict(DemandePriere.STATUTS):
        return err("Statut inconnu.")
    p.statut = statut
    p.save(update_fields=["statut"])
    return ok({"priere": {"id": p.id, "statut": p.statut}})


# ── tableau de bord et export ────────────────────────────────────────────────
@auth_requise()
@permission_requise("pastoral", "consulter")
def pastoral_bord(request):
    e = _eglise(request)
    qs = DossierPastoral.objects.filter(eglise=e)
    visibles = qs.filter(confidentialite__in=["normal", "restreint"])
    aujourdhui = date.today()
    return ok({
        "ouverts": visibles.filter(statut__in=["ouvert", "en_cours", "en_attente"]).count(),
        "confidentiels": qs.filter(confidentialite="confidentiel").count(),
        "en_retard": visibles.filter(echeance__lt=aujourdhui)
                      .exclude(statut__in=["clos", "abandonne"]).count(),
        "nouveaux_convertis": visibles.filter(type="nouveau_converti")
                                     .exclude(statut__in=["clos", "abandonne"]).count(),
        "prieres_nouvelles": DemandePriere.objects.filter(eglise=e, statut="nouvelle").count(),
        "actions_30_jours": ActionPastorale.objects.filter(
            eglise=e, date__gte=aujourdhui - timedelta(days=30)).count(),
        "par_type": list(visibles.values("type").annotate(n=Count("id")).order_by("-n")[:6]),
    })


@auth_requise()
@permission_requise("pastoral", "exporter")
def pastoral_export(request):
    e = _eglise(request)
    sortie = io.StringIO()
    w = csv.writer(sortie, delimiter=";")
    w.writerow(["Numéro", "Personne", "Type", "Statut", "Confidentialité", "Responsable",
                "Échéance", "Prochaine étape", "Ouvert le"])
    for d in DossierPastoral.objects.filter(eglise=e).select_related("responsable"):
        if not _peut_voir(request.utilisateur, d):
            continue
        w.writerow([d.numero, d.personne_nom, d.get_type_display(), d.get_statut_display(),
                    d.get_confidentialite_display(),
                    d.responsable.nom_complet if d.responsable_id else "",
                    d.echeance or "", d.prochaine_etape, d.ouvert_le or ""])
    tracer(request.utilisateur, "pastoral", "exporter", "Export CSV des dossiers pastoraux")
    reponse = HttpResponse(sortie.getvalue(), content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = 'attachment; filename="suivi-pastoral.csv"'
    return reponse
