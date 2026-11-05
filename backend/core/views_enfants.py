"""Module enfants et école du dimanche (sections 15 et 19)."""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q

from core.models import (Eglise, Utilisateur, JournalAudit, Membre, Enfant, PersonneAutorisee,
                         ClasseEnfants, InscriptionEnfant, PresenceEnfant, IncidentEnfant,
                         LeconEnfants, ProgressionEnfant)
from core.security import auth_requise, permission_requise, a_permission, tracer
from core.views_api import ok, err, corps


def _eglise(request):
    return request.utilisateur.eglise


def _date(v):
    if not v:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _voit_sensible(user):
    """Santé, besoins particuliers : réservés au droit de validation du module enfants."""
    return a_permission(user, "enfants", "valider")


def _json_enfant(e, user):
    d = {"id": e.id, "code": e.code, "nom": e.nom, "postnom": e.postnom, "prenom": e.prenom,
         "sexe": e.sexe, "age": e.age(),
         "date_naissance": e.date_naissance.isoformat() if e.date_naissance else None,
         "tuteur_nom": e.tuteur_nom, "tuteur_lien": e.tuteur_lien,
         "tuteur_telephone": e.tuteur_telephone, "urgence_nom": e.urgence_nom,
         "urgence_telephone": e.urgence_telephone,
         "autorisation_photo": e.autorisation_photo, "autorisation_sortie": e.autorisation_sortie,
         "statut": e.statut,
         "autorises": e.autorises.filter(actif=True).count()}
    if _voit_sensible(user):
        d["sante"] = e.sante
        d["besoins"] = e.besoins
        d["tuteur_email"] = e.tuteur_email
    else:
        d["sensible_restreint"] = True
    return d


def _code_enfant(e):
    annee = date.today().year
    n = Enfant.objects.filter(eglise=e).count() + 1
    while Enfant.objects.filter(eglise=e, code=f"ENF-{annee}-{n:04d}").exists():
        n += 1
    return f"ENF-{annee}-{n:04d}"


@auth_requise()
@permission_requise("enfants", "consulter")
def enfants_liste(request):
    e = _eglise(request)
    d = corps(request)
    qs = Enfant.objects.filter(eglise=e)
    if d.get("statut"):
        qs = qs.filter(statut=d["statut"])
    if d.get("classe"):
        qs = qs.filter(inscriptions__classe_id=d["classe"], inscriptions__active=True)
    q = (d.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(code__icontains=q)
                       | Q(tuteur_nom__icontains=q) | Q(tuteur_telephone__icontains=q))
    total = qs.count()
    return ok({"total": total, "enfants": [_json_enfant(x, request.utilisateur) for x in qs.distinct()[:120]]})


@auth_requise()
@permission_requise("enfants", "creer")
def enfant_creer(request):
    e = _eglise(request)
    d = corps(request)
    if not (d.get("nom") or "").strip():
        return err("Le nom de l'enfant est obligatoire.")
    enf = Enfant.objects.create(
        eglise=e, code=_code_enfant(e), nom=d["nom"].strip(),
        postnom=d.get("postnom", ""), prenom=d.get("prenom", ""), sexe=d.get("sexe", ""),
        date_naissance=_date(d.get("date_naissance")), tuteur_nom=d.get("tuteur_nom", ""),
        tuteur_lien=d.get("tuteur_lien", ""), tuteur_telephone=d.get("tuteur_telephone", ""),
        tuteur_email=d.get("tuteur_email", ""), urgence_nom=d.get("urgence_nom", ""),
        urgence_telephone=d.get("urgence_telephone", ""), sante=d.get("sante", ""),
        besoins=d.get("besoins", ""), autorisation_photo=bool(d.get("autorisation_photo")),
        autorisation_sortie=bool(d.get("autorisation_sortie")))
    tracer(request.utilisateur, "enfants", "creer", f"Enfant enregistré : {enf.code}")
    return ok({"enfant": _json_enfant(enf, request.utilisateur)})


@auth_requise()
@permission_requise("enfants", "consulter")
def enfant_detail(request):
    e = _eglise(request)
    d = corps(request)
    enf = Enfant.objects.filter(eglise=e, id=d.get("id")).first()
    if not enf:
        return err("Enfant introuvable.", 404)
    if _voit_sensible(request.utilisateur):
        tracer(request.utilisateur, "enfants", "consulter_sensible", f"Fiche sensible consultée : {enf.code}")
    presences = enf.presences.all()[:30]
    incidents = enf.incidents.all()[:20]
    return ok({"enfant": _json_enfant(enf, request.utilisateur),
               "autorises": [{"id": a.id, "nom": a.nom, "lien": a.lien, "telephone": a.telephone,
                              "piece": a.piece} for a in enf.autorises.filter(actif=True)],
               "classes": [{"id": i.classe.id, "nom": i.classe.nom, "date": i.date.isoformat()}
                           for i in enf.inscriptions.filter(active=True).select_related("classe")],
               "presences": [{"date": p.date.isoformat(), "statut": p.statut, "depart": p.depart,
                              "recupere_par": p.recupere_par.nom if p.recupere_par_id else ""} for p in presences],
               "incidents": [{"date": i.date.isoformat(), "type": i.type, "gravite": i.gravite,
                              "parent_informe": i.parent_informe} for i in incidents]})


@auth_requise()
@permission_requise("enfants", "modifier")
def enfant_modifier(request):
    e = _eglise(request)
    d = corps(request)
    enf = Enfant.objects.filter(eglise=e, id=d.get("id")).first()
    if not enf:
        return err("Enfant introuvable.", 404)
    for champ in ("nom", "postnom", "prenom", "sexe", "tuteur_nom", "tuteur_lien",
                  "tuteur_telephone", "tuteur_email", "urgence_nom", "urgence_telephone"):
        if champ in d:
            setattr(enf, champ, d[champ])
    for champ in ("autorisation_photo", "autorisation_sortie"):
        if champ in d:
            setattr(enf, champ, bool(d[champ]))
    if "statut" in d and d["statut"] in ("actif", "sorti", "archive"):
        enf.statut = d["statut"]
    if "date_naissance" in d:
        enf.date_naissance = _date(d["date_naissance"])
    if _voit_sensible(request.utilisateur):
        for champ in ("sante", "besoins"):
            if champ in d:
                setattr(enf, champ, d[champ])
        tracer(request.utilisateur, "enfants", "modifier_sensible", f"Données sensibles modifiées : {enf.code}")
    enf.save()
    tracer(request.utilisateur, "enfants", "modifier", f"Fiche modifiée : {enf.code}")
    return ok({"enfant": _json_enfant(enf, request.utilisateur)})


@auth_requise()
@permission_requise("enfants", "modifier")
def autorise_ajouter(request):
    e = _eglise(request)
    d = corps(request)
    enf = Enfant.objects.filter(eglise=e, id=d.get("enfant_id")).first()
    if not enf:
        return err("Enfant introuvable.", 404)
    if not (d.get("nom") or "").strip():
        return err("Le nom de la personne autorisée est obligatoire.")
    a = PersonneAutorisee.objects.create(enfant=enf, nom=d["nom"].strip(), lien=d.get("lien", ""),
                                         telephone=d.get("telephone", ""), piece=d.get("piece", ""))
    tracer(request.utilisateur, "enfants", "autoriser",
           f"Personne autorisée ajoutée pour {enf.code} : {a.nom}")
    return ok({"autorise": {"id": a.id, "nom": a.nom, "lien": a.lien, "telephone": a.telephone}})


@auth_requise()
@permission_requise("enfants", "modifier")
def autorise_retirer(request):
    e = _eglise(request)
    d = corps(request)
    a = PersonneAutorisee.objects.filter(enfant__eglise=e, id=d.get("id")).first()
    if not a:
        return err("Personne autorisée introuvable.", 404)
    a.actif = False
    a.save(update_fields=["actif"])
    tracer(request.utilisateur, "enfants", "retirer_autorisation", f"Autorisation retirée : {a.nom}")
    return ok({"retire": a.id})


# ─────────────── classes ───────────────

@auth_requise()
@permission_requise("enfants", "consulter")
def classes_liste(request):
    e = _eglise(request)
    lignes = []
    for c in ClasseEnfants.objects.filter(eglise=e):
        lignes.append({"id": c.id, "nom": c.nom, "age_min": c.age_min, "age_max": c.age_max,
                       "salle": c.salle, "capacite": c.capacite, "active": c.active,
                       "moniteur": c.moniteur.nom_complet if c.moniteur_id else "",
                       "effectif": c.inscriptions.filter(active=True).count()})
    return ok({"classes": lignes})


@auth_requise()
@permission_requise("enfants", "creer")
def classe_creer(request):
    e = _eglise(request)
    d = corps(request)
    if not (d.get("nom") or "").strip():
        return err("Le nom de la classe est obligatoire.")
    c = ClasseEnfants.objects.create(eglise=e, nom=d["nom"].strip(),
                                     age_min=int(d.get("age_min") or 3), age_max=int(d.get("age_max") or 12),
                                     salle=d.get("salle", ""), capacite=d.get("capacite") or None,
                                     moniteur_id=d.get("moniteur_id") or None)
    tracer(request.utilisateur, "enfants", "creer_classe", f"Classe créée : {c.nom}")
    return ok({"classe": {"id": c.id, "nom": c.nom}})


@auth_requise()
@permission_requise("enfants", "modifier")
def classe_affecter(request):
    e = _eglise(request)
    d = corps(request)
    enf = Enfant.objects.filter(eglise=e, id=d.get("enfant_id")).first()
    classe = ClasseEnfants.objects.filter(eglise=e, id=d.get("classe_id")).first()
    if not enf or not classe:
        return err("Enfant ou classe introuvable.", 404)
    if classe.capacite and classe.inscriptions.filter(active=True).count() >= classe.capacite:
        return err("La classe est complète.")
    InscriptionEnfant.objects.filter(enfant=enf, active=True).update(active=False)
    i = InscriptionEnfant.objects.create(eglise=e, enfant=enf, classe=classe,
                                         annee_scolaire=d.get("annee_scolaire", ""))
    tracer(request.utilisateur, "enfants", "affecter", f"{enf.code} inscrit en {classe.nom}")
    return ok({"inscription": {"id": i.id, "classe": classe.nom}})


# ─────────────── présences, entrées et sorties ───────────────

@auth_requise()
@permission_requise("enfants", "consulter")
def presences_enfants(request):
    e = _eglise(request)
    d = corps(request)
    jour = _date(d.get("date")) or date.today()
    qs = PresenceEnfant.objects.filter(eglise=e, date=jour).select_related("enfant", "classe", "recupere_par")
    if d.get("classe"):
        qs = qs.filter(classe_id=d["classe"])
    return ok({"date": jour.isoformat(),
               "presences": [{"id": p.id, "enfant": f"{p.enfant.nom} {p.enfant.prenom}".strip(),
                              "code": p.enfant.code, "classe": p.classe.nom if p.classe_id else "",
                              "statut": p.statut, "arrivee": p.arrivee, "depart": p.depart,
                              "recupere_par": p.recupere_par.nom if p.recupere_par_id else ""} for p in qs],
               "total": qs.count()})


@auth_requise()
@permission_requise("enfants", "creer")
def presence_pointer(request):
    e = _eglise(request)
    d = corps(request)
    enf = Enfant.objects.filter(eglise=e, id=d.get("enfant_id")).first()
    if not enf:
        return err("Enfant introuvable.", 404)
    jour = _date(d.get("date")) or date.today()
    statut = d.get("statut") or "present"
    if statut not in ("present", "retard", "absent"):
        return err("Statut de présence inconnu.")
    p, _ = PresenceEnfant.objects.update_or_create(
        eglise=e, enfant=enf, date=jour,
        defaults={"statut": statut, "arrivee": d.get("arrivee", ""),
                  "classe_id": d.get("classe_id") or None})
    tracer(request.utilisateur, "enfants", "pointer", f"{enf.code} : {statut} le {jour}")
    return ok({"presence": {"id": p.id, "statut": p.statut}})


@auth_requise()
@permission_requise("enfants", "modifier")
def sortie_enregistrer(request):
    """Contrôle des départs : seule une personne autorisée peut récupérer l'enfant."""
    e = _eglise(request)
    d = corps(request)
    enf = Enfant.objects.filter(eglise=e, id=d.get("enfant_id")).first()
    if not enf:
        return err("Enfant introuvable.", 404)
    jour = _date(d.get("date")) or date.today()
    autorise = PersonneAutorisee.objects.filter(enfant=enf, actif=True, id=d.get("autorise_id")).first()
    if not autorise:
        tracer(request.utilisateur, "enfants", "sortie_refusee",
               f"Sortie refusée pour {enf.code} : personne non autorisée")
        return err("Cette personne n'est pas autorisée à récupérer l'enfant.", 403)
    p, _ = PresenceEnfant.objects.get_or_create(eglise=e, enfant=enf, date=jour)
    p.depart = d.get("heure", "")
    p.recupere_par = autorise
    p.sortie_note = d.get("note", "")
    p.save()
    tracer(request.utilisateur, "enfants", "sortie", f"{enf.code} récupéré par {autorise.nom}")
    return ok({"presence": {"id": p.id, "depart": p.depart, "recupere_par": autorise.nom}})


# ─────────────── incidents et progression ───────────────

@auth_requise()
@permission_requise("enfants", "creer")
def incident_creer(request):
    e = _eglise(request)
    d = corps(request)
    enf = Enfant.objects.filter(eglise=e, id=d.get("enfant_id")).first()
    if not enf:
        return err("Enfant introuvable.", 404)
    if not (d.get("description") or "").strip():
        return err("La description de l'incident est obligatoire.")
    i = IncidentEnfant.objects.create(eglise=e, enfant=enf, date=_date(d.get("date")) or date.today(),
                                      type=d.get("type") or "autre", gravite=d.get("gravite") or "legere",
                                      description=d["description"], action=d.get("action", ""),
                                      parent_informe=bool(d.get("parent_informe")),
                                      signale_par=request.utilisateur)
    tracer(request.utilisateur, "enfants", "incident", f"Incident {i.gravite} signalé : {enf.code}")
    return ok({"incident": {"id": i.id, "gravite": i.gravite}})


@auth_requise()
@permission_requise("enfants", "consulter")
def incidents_liste(request):
    e = _eglise(request)
    d = corps(request)
    qs = IncidentEnfant.objects.filter(eglise=e).select_related("enfant")
    if d.get("enfant_id"):
        qs = qs.filter(enfant_id=d["enfant_id"])
    if d.get("mois"):
        qs = qs.filter(date__startswith=d["mois"])
    return ok({"incidents": [{"id": i.id, "enfant": f"{i.enfant.nom} {i.enfant.prenom}".strip(),
                              "date": i.date.isoformat(), "type": i.type, "gravite": i.gravite,
                              "parent_informe": i.parent_informe} for i in qs[:80]],
               "total": qs.count(),
               "non_informes": qs.filter(parent_informe=False).count()})


@auth_requise()
@permission_requise("enfants", "creer")
def lecon_creer(request):
    e = _eglise(request)
    d = corps(request)
    if not (d.get("titre") or "").strip():
        return err("Le titre de la leçon est obligatoire.")
    l = LeconEnfants.objects.create(eglise=e, classe_id=d.get("classe_id") or None,
                                    titre=d["titre"].strip(), date=_date(d.get("date")) or date.today(),
                                    objectif=d.get("objectif", ""), activite=d.get("activite", ""))
    tracer(request.utilisateur, "enfants", "creer_lecon", f"Leçon : {l.titre}")
    return ok({"lecon": {"id": l.id, "titre": l.titre}})


@auth_requise()
@permission_requise("enfants", "consulter")
def lecons_liste(request):
    e = _eglise(request)
    qs = LeconEnfants.objects.filter(eglise=e).select_related("classe")
    return ok({"lecons": [{"id": l.id, "titre": l.titre, "date": l.date.isoformat(),
                           "classe": l.classe.nom if l.classe_id else "",
                           "acquis": l.progressions.filter(niveau="acquis").count(),
                           "suivis": l.progressions.count()} for l in qs[:60]]})


@auth_requise()
@permission_requise("enfants", "modifier")
def progression_enregistrer(request):
    e = _eglise(request)
    d = corps(request)
    enf = Enfant.objects.filter(eglise=e, id=d.get("enfant_id")).first()
    lecon = LeconEnfants.objects.filter(eglise=e, id=d.get("lecon_id")).first()
    if not enf or not lecon:
        return err("Enfant ou leçon introuvable.", 404)
    niveau = d.get("niveau") or "en_cours"
    if niveau not in ("non_acquis", "en_cours", "acquis"):
        return err("Niveau de progression inconnu.")
    p, _ = ProgressionEnfant.objects.update_or_create(
        eglise=e, enfant=enf, lecon=lecon, defaults={"niveau": niveau, "note": d.get("note", "")})
    return ok({"progression": {"id": p.id, "niveau": p.niveau}})


@auth_requise()
@permission_requise("enfants", "exporter")
def enfants_export(request):
    import csv
    from django.http import HttpResponse
    e = _eglise(request)
    reponse = HttpResponse(content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = 'attachment; filename="enfants.csv"'
    reponse.write("\ufeff")
    w = csv.writer(reponse, delimiter=";")
    w.writerow(["Code", "Nom", "Prénom", "Âge", "Tuteur", "Téléphone tuteur",
                "Autorisation photo", "Autorisation sortie", "Statut"])
    for enf in Enfant.objects.filter(eglise=e):
        w.writerow([enf.code, enf.nom, enf.prenom, enf.age() or "", enf.tuteur_nom,
                    enf.tuteur_telephone, "oui" if enf.autorisation_photo else "non",
                    "oui" if enf.autorisation_sortie else "non", enf.statut])
    tracer(request.utilisateur, "enfants", "exporter", "Export de la liste des enfants")
    return reponse


@auth_requise()
@permission_requise("enfants", "consulter")
def enfants_bord(request):
    e = _eglise(request)
    aujourdhui = date.today()
    debut_mois = aujourdhui.replace(day=1)
    actifs = Enfant.objects.filter(eglise=e, statut="actif")
    sans_autorisation = sum(1 for x in actifs if not x.autorises.filter(actif=True).exists())
    return ok({"actifs": actifs.count(),
               "presents_aujourdhui": PresenceEnfant.objects.filter(eglise=e, date=aujourdhui,
                                                                    statut__in=["present", "retard"]).count(),
               "incidents_mois": IncidentEnfant.objects.filter(eglise=e, date__gte=debut_mois).count(),
               "parents_non_informes": IncidentEnfant.objects.filter(eglise=e, parent_informe=False).count(),
               "sans_autorisation": sans_autorisation,
               "classes": ClasseEnfants.objects.filter(eglise=e, active=True).count(),
               "enfants": [_json_enfant(x, request.utilisateur) for x in actifs[:40]]})
