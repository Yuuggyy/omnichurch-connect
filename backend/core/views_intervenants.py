"""Intervenants et bibliothèque média (section 14)."""
from datetime import date

from django.db.models import Count, Q

from core.models import (Membre, Intervenant, DisponibiliteIntervenant, InvitationIntervenant,
                         Media, MediaVu, Evenement)
from core.security import auth_requise, permission_requise, tracer
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


def _json_intervenant(i, avec_contact=True):
    d = {"id": i.id, "nom": i.nom, "type": i.type, "organisation": i.organisation,
         "ville": i.ville, "specialites": i.specialites, "disponible": i.disponible,
         "membre_id": i.membre_id, "tarif": str(i.tarif), "devise": i.devise,
         "interventions": i.invitations.count(), "medias": i.medias.count()}
    if avec_contact:
        d.update({"telephone": i.telephone, "email": i.email, "notes": i.notes,
                  "document_url": i.document_url})
    else:
        d["contact_restreint"] = True
    return d


@auth_requise()
@permission_requise("intervenants", "consulter")
def intervenants_liste(request):
    e = _eglise(request)
    d = corps(request)
    qs = Intervenant.objects.filter(eglise=e)
    if d.get("type"):
        qs = qs.filter(type=d["type"])
    if d.get("q"):
        q = d["q"]
        qs = qs.filter(Q(nom__icontains=q) | Q(organisation__icontains=q) | Q(specialites__icontains=q))
    avec_contact = _voit_contact(request.utilisateur)
    return ok({"intervenants": [_json_intervenant(i, avec_contact) for i in qs[:120]],
               "total": qs.count(),
               "types": [{"code": c, "libelle": l} for c, l in Intervenant.TYPES]})


def _voit_contact(user):
    from core.security import a_permission
    return a_permission(user, "intervenants", "valider")


@auth_requise()
@permission_requise("intervenants", "creer")
def intervenant_creer(request):
    e = _eglise(request)
    d = corps(request)
    if not (d.get("nom") or "").strip():
        return err("Le nom de l'intervenant est obligatoire.")
    membre = None
    if d.get("membre_id"):
        membre = Membre.objects.filter(eglise=e, id=d["membre_id"]).first()
    # pas de doublon : si un membre est déjà relié, on réutilise sa fiche
    if membre:
        existant = Intervenant.objects.filter(eglise=e, membre=membre).first()
        if existant:
            return ok({"intervenant": _json_intervenant(existant), "existant": True})
    i = Intervenant.objects.create(
        eglise=e, membre=membre, nom=d["nom"].strip(), type=d.get("type", "orateur"),
        organisation=d.get("organisation", ""), telephone=d.get("telephone", ""),
        email=d.get("email", ""), ville=d.get("ville", ""), specialites=d.get("specialites", ""),
        tarif=d.get("tarif") or 0, devise=d.get("devise", "USD"),
        disponible=bool(d.get("disponible", True)), notes=d.get("notes", ""),
        document_url=d.get("document_url", ""))
    tracer(request.utilisateur, "intervenants", "creer", f"Intervenant enregistré : {i.nom}")
    return ok({"intervenant": _json_intervenant(i)})


@auth_requise()
@permission_requise("intervenants", "modifier")
def intervenant_modifier(request):
    e = _eglise(request)
    d = corps(request)
    i = Intervenant.objects.filter(eglise=e, id=d.get("id")).first()
    if not i:
        return err("Intervenant introuvable.", 404)
    for champ in ("nom", "type", "organisation", "telephone", "email", "ville", "specialites",
                  "notes", "document_url", "devise"):
        if champ in d:
            setattr(i, champ, d[champ])
    if "tarif" in d:
        i.tarif = d["tarif"] or 0
    if "disponible" in d:
        i.disponible = bool(d["disponible"])
    i.save()
    tracer(request.utilisateur, "intervenants", "modifier", f"Intervenant modifié : {i.nom}")
    return ok({"intervenant": _json_intervenant(i)})


@auth_requise()
@permission_requise("intervenants", "modifier")
def disponibilite_ajouter(request):
    e = _eglise(request)
    d = corps(request)
    i = Intervenant.objects.filter(eglise=e, id=d.get("intervenant_id")).first()
    if not i:
        return err("Intervenant introuvable.", 404)
    jour = _date(d.get("date"))
    if not jour:
        return err("La date de disponibilité est obligatoire.")
    obj, _ = DisponibiliteIntervenant.objects.update_or_create(
        intervenant=i, date=jour,
        defaults={"note": d.get("note", ""), "disponible": bool(d.get("disponible", True))})
    return ok({"disponibilite": {"id": obj.id, "date": jour.isoformat()}})


@auth_requise()
@permission_requise("intervenants", "consulter")
def invitation_liste(request):
    e = _eglise(request)
    d = corps(request)
    qs = InvitationIntervenant.objects.filter(eglise=e).select_related("intervenant", "evenement")
    if d.get("intervenant_id"):
        qs = qs.filter(intervenant_id=d["intervenant_id"])
    if d.get("statut"):
        qs = qs.filter(statut=d["statut"])
    return ok({"invitations": [{
        "id": x.id, "intervenant": x.intervenant.nom, "objet": x.objet,
        "date": x.date.isoformat() if x.date else None, "statut": x.statut,
        "theme": x.theme, "evenement": x.evenement.titre if x.evenement_id else ""}
        for x in qs[:100]], "total": qs.count()})


@auth_requise()
@permission_requise("intervenants", "creer")
def invitation_creer(request):
    e = _eglise(request)
    d = corps(request)
    i = Intervenant.objects.filter(eglise=e, id=d.get("intervenant_id")).first()
    if not i:
        return err("Intervenant introuvable.", 404)
    if not i.disponible:
        return err("Cet intervenant est marqué indisponible.")
    jour = _date(d.get("date"))
    if jour:
        bloquee = DisponibiliteIntervenant.objects.filter(intervenant=i, date=jour,
                                                          disponible=False).exists()
        if bloquee:
            return err("L'intervenant s'est déclaré indisponible à cette date.")
    ev = None
    if d.get("evenement_id"):
        ev = Evenement.objects.filter(eglise=e, id=d["evenement_id"]).first()
    inv = InvitationIntervenant.objects.create(
        eglise=e, intervenant=i, evenement=ev, objet=d.get("objet", ""), date=jour,
        theme=d.get("theme", ""), note=d.get("note", ""), statut="proposee")
    tracer(request.utilisateur, "intervenants", "inviter",
           f"Invitation proposée à {i.nom}" + (f" pour le {jour}" if jour else ""))
    return ok({"invitation": {"id": inv.id, "statut": inv.statut}})


@auth_requise()
@permission_requise("intervenants", "modifier")
def invitation_statut(request):
    e = _eglise(request)
    d = corps(request)
    inv = InvitationIntervenant.objects.filter(eglise=e, id=d.get("id")).first()
    if not inv:
        return err("Invitation introuvable.", 404)
    statut = d.get("statut")
    if statut not in dict(InvitationIntervenant.STATUTS):
        return err("Statut d'invitation inconnu.")
    inv.statut = statut
    inv.save(update_fields=["statut"])
    tracer(request.utilisateur, "intervenants", "modifier", f"Invitation {inv.id} : {statut}")
    return ok({"invitation": {"id": inv.id, "statut": inv.statut}})


# ─────────────── médiathèque ───────────────

@auth_requise()
@permission_requise("mediatheque", "consulter")
def medias_liste(request):
    e = _eglise(request)
    d = corps(request)
    qs = Media.objects.filter(eglise=e).select_related("intervenant")
    if d.get("type"):
        qs = qs.filter(type=d["type"])
    if d.get("categorie"):
        qs = qs.filter(categorie=d["categorie"])
    if d.get("serie"):
        qs = qs.filter(serie=d["serie"])
    if d.get("playlist"):
        qs = qs.filter(playlist=d["playlist"])
    if d.get("q"):
        q = d["q"]
        qs = qs.filter(Q(titre__icontains=q) | Q(theme__icontains=q) | Q(serie__icontains=q)
                       | Q(reference_biblique__icontains=q) | Q(transcription__icontains=q))
    return ok({"medias": [{
        "id": m.id, "titre": m.titre, "type": m.type, "categorie": m.categorie,
        "intervenant": m.intervenant.nom if m.intervenant_id else "",
        "date": m.date.isoformat() if m.date else None, "theme": m.theme, "serie": m.serie,
        "reference_biblique": m.reference_biblique, "duree_minutes": m.duree_minutes,
        "url": m.url, "fichier_url": m.fichier_url, "playlist": m.playlist,
        "diffusion_autorisee": m.diffusion_autorisee, "public": m.public,
        "transcription": bool(m.transcription), "ecoutes": m.ecoutes.count()}
        for m in qs[:150]],
        "total": qs.count(),
        "series": list(Media.objects.filter(eglise=e).exclude(serie="")
                       .values_list("serie", flat=True).distinct()[:30])})


@auth_requise()
@permission_requise("mediatheque", "creer")
def media_creer(request):
    e = _eglise(request)
    d = corps(request)
    if not (d.get("titre") or "").strip():
        return err("Le titre du média est obligatoire.")
    if not (d.get("url") or d.get("fichier_url")):
        return err("Un lien ou un fichier est nécessaire pour publier ce média.")
    i = None
    if d.get("intervenant_id"):
        i = Intervenant.objects.filter(eglise=e, id=d["intervenant_id"]).first()
    m = Media.objects.create(
        eglise=e, titre=d["titre"].strip(), type=d.get("type", "audio"),
        categorie=d.get("categorie", "predication"), intervenant=i,
        date=_date(d.get("date")), theme=d.get("theme", ""), serie=d.get("serie", ""),
        reference_biblique=d.get("reference_biblique", ""),
        duree_minutes=d.get("duree_minutes") or None, url=d.get("url", ""),
        fichier_url=d.get("fichier_url", ""), transcription=d.get("transcription", ""),
        playlist=d.get("playlist", ""), licence=d.get("licence", ""),
        diffusion_autorisee=bool(d.get("diffusion_autorisee")), public=bool(d.get("public")),
        cree_par=request.utilisateur)
    tracer(request.utilisateur, "mediatheque", "creer", f"Média ajouté : {m.titre}")
    return ok({"media": {"id": m.id, "titre": m.titre}})


@auth_requise()
@permission_requise("mediatheque", "modifier")
def media_modifier(request):
    e = _eglise(request)
    d = corps(request)
    m = Media.objects.filter(eglise=e, id=d.get("id")).first()
    if not m:
        return err("Média introuvable.", 404)
    for champ in ("titre", "type", "categorie", "theme", "serie", "reference_biblique", "url",
                  "fichier_url", "transcription", "playlist", "licence"):
        if champ in d:
            setattr(m, champ, d[champ])
    if "date" in d:
        m.date = _date(d["date"])
    if "duree_minutes" in d:
        m.duree_minutes = d["duree_minutes"] or None
    for b in ("diffusion_autorisee", "public"):
        if b in d:
            setattr(m, b, bool(d[b]))
    if "intervenant_id" in d:
        m.intervenant_id = d["intervenant_id"] or None
    m.save()
    tracer(request.utilisateur, "mediatheque", "modifier", f"Média modifié : {m.titre}")
    return ok({"media": {"id": m.id, "titre": m.titre, "public": m.public}})


@auth_requise()
@permission_requise("mediatheque", "consulter")
def media_ecouter(request):
    e = _eglise(request)
    d = corps(request)
    m = Media.objects.filter(eglise=e, id=d.get("id")).first()
    if not m:
        return err("Média introuvable.", 404)
    media_url = m.url or m.fichier_url
    if media_url and not m.diffusion_autorisee:
        return err("Diffusion non autorisée pour ce média : vérifiez la licence.", 403)
    MediaVu.objects.create(media=m, utilisateur=request.utilisateur)
    return ok({"url": media_url, "titre": m.titre, "transcription": m.transcription})


@auth_requise()
@permission_requise("intervenants", "consulter")
def intervenants_bord(request):
    e = _eglise(request)
    mois = date.today().replace(day=1)
    return ok({
        "intervenants": Intervenant.objects.filter(eglise=e).count(),
        "disponibles": Intervenant.objects.filter(eglise=e, disponible=True).count(),
        "invitations_en_attente": InvitationIntervenant.objects.filter(
            eglise=e, statut="proposee").count(),
        "interventions_mois": InvitationIntervenant.objects.filter(
            eglise=e, statut="effectuee", date__gte=mois).count(),
        "medias": Media.objects.filter(eglise=e).count(),
        "sans_licence": Media.objects.filter(eglise=e, diffusion_autorisee=False).count(),
        "audios": Media.objects.filter(eglise=e, type="audio").count(),
        "documents": Media.objects.filter(eglise=e, type="document").count(),
    })
