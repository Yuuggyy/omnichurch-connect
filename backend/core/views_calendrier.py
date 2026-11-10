"""API OmniChurch Connect — Phase 3 : calendrier et événements.

Calendrier mensuel avec récurrences, fiche complète d'un événement, inscriptions
des membres, export iCalendar et CSV, rappels des prochains jours.
Règle absolue : tout est filtré sur l'Église de l'utilisateur authentifié.
"""
import calendar as calendrier_py
import csv
import io
import json
from datetime import date, datetime, timedelta

from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone

from core.models import Eglise, Membre, Evenement, EvenementInscription, Presence
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


def _mois(v):
    """« 2026-11 » → (premier jour, dernier jour). Par défaut : mois courant."""
    aujourdhui = timezone.localdate()
    if v:
        try:
            annee, mois_num = [int(x) for x in str(v).split("-")[:2]]
            debut = date(annee, mois_num, 1)
            return debut, date(annee, mois_num, calendrier_py.monthrange(annee, mois_num)[1])
        except (ValueError, IndexError):
            pass
    return aujourdhui.replace(day=1), date(aujourdhui.year, aujourdhui.month,
                                          calendrier_py.monthrange(aujourdhui.year, aujourdhui.month)[1])


def _json_ev(ev, jour=None):
    return {
        "id": ev.id,
        "titre": ev.titre,
        "type": ev.type,
        "date": (jour or ev.date).isoformat(),
        "heure": ev.heure,
        "heure_fin": ev.heure_fin,
        "duree_minutes": ev.duree(),
        "journee_entiere": ev.journee_entiere,
        "lieu": ev.lieu,
        "description": ev.description,
        "statut": ev.statut,
        "recurrence": ev.recurrence,
        "capacite": ev.capacite,
        "groupe_id": ev.groupe_id,
        "inscrits": getattr(ev, "nb_inscrits", None),
    }


def _occurrences(ev, debut, fin):
    """Dates d'occurrence d'un événement dans la fenêtre demandée."""
    if ev.recurrence == "aucune":
        return [ev.date] if debut <= ev.date <= fin else []
    jours = []
    courant = ev.date
    if ev.recurrence == "hebdomadaire":
        while courant <= fin:
            if courant >= debut:
                jours.append(courant)
            courant = courant + timedelta(days=7)
    elif ev.recurrence == "mensuelle":
        annee, mois_num, jour = ev.date.year, ev.date.month, ev.date.day
        while date(annee, mois_num, 1) <= fin:
            dernier = calendrier_py.monthrange(annee, mois_num)[1]
            occurrence = date(annee, mois_num, min(jour, dernier))
            if debut <= occurrence <= fin:
                jours.append(occurrence)
            mois_num += 1
            if mois_num > 12:
                mois_num, annee = 1, annee + 1
    elif ev.recurrence == "annuelle":
        annee = ev.date.year
        while date(annee, 1, 1) <= fin:
            try:
                occurrence = date(annee, ev.date.month, ev.date.day)
                if debut <= occurrence <= fin:
                    jours.append(occurrence)
            except ValueError:
                pass
            annee += 1
    return sorted(set(jours))


# ─────────────────────────── lecture ───────────────────────────

@auth_requise()
@permission_requise("evenements", "consulter")
def calendrier_mois(request):
    e = _eglise(request)
    debut, fin = _mois(request.GET.get("mois"))
    qs = Evenement.objects.filter(eglise=e).select_related("groupe").annotate(
        nb_inscrits=Count("inscriptions", filter=Q(inscriptions__statut__in=["inscrit", "confirme"])))
    if request.GET.get("type"):
        qs = qs.filter(type=request.GET["type"])
    if request.GET.get("groupe"):
        qs = qs.filter(groupe_id=request.GET["groupe"])
    jours, par_type, total = {}, {}, 0
    for ev in qs:
        for jour in _occurrences(ev, debut, fin):
            jours.setdefault(jour.isoformat(), []).append(_json_ev(ev, jour))
            par_type[ev.type] = par_type.get(ev.type, 0) + 1
            total += 1
    for liste in jours.values():
        liste.sort(key=lambda x: (not x["journee_entiere"], x["heure"] or "99:99"))
    return ok({"mois": debut.strftime("%Y-%m"), "debut": debut.isoformat(), "fin": fin.isoformat(),
               "jours": jours, "total": total, "par_type": par_type})


@auth_requise()
@permission_requise("evenements", "consulter")
def evenement_detail(request):
    e = _eglise(request)
    ev = Evenement.objects.filter(eglise=e, id=request.GET.get("id")).select_related(
        "groupe", "responsable").first()
    if not ev:
        return err("Événement introuvable dans cette Église.", 404)
    inscriptions = EvenementInscription.objects.filter(eglise=e, evenement=ev).select_related("membre")
    pointage = Presence.objects.filter(eglise=e, evenement=ev)
    data = _json_ev(ev)
    data.update({
        "description": ev.description,
        "date_fin": ev.date_fin.isoformat() if ev.date_fin else None,
        "public_cible": ev.public_cible,
        "rappel_jours": ev.rappel_jours,
        "responsable": ev.responsable.nom_complet if ev.responsable else "",
        "groupe": ev.groupe.nom if ev.groupe else "",
        "inscrits": inscriptions.filter(statut__in=["inscrit", "confirme"]).count(),
        "confirmes": inscriptions.filter(statut="confirme").count(),
        "capacite_restante": (ev.capacite - inscriptions.filter(
            statut__in=["inscrit", "confirme"]).count()) if ev.capacite else None,
        "presents": pointage.filter(membre__isnull=False).count(),
        "participants": [{"id": i.membre_id, "matricule": i.membre.matricule,
                          "nom": i.membre.nom_complet if hasattr(i.membre, "nom_complet")
                          else f"{i.membre.nom} {i.membre.prenom}".strip(),
                          "statut": i.statut} for i in inscriptions],
    })
    return ok({"evenement": data})


@auth_requise()
@permission_requise("evenements", "consulter")
def evenements_a_venir(request):
    e = _eglise(request)
    try:
        horizon = int(request.GET.get("jours") or 7)
    except ValueError:
        horizon = 7
    aujourdhui = timezone.localdate()
    limite = aujourdhui + timedelta(days=max(1, min(horizon, 365)))
    liste = []
    for ev in Evenement.objects.filter(eglise=e, statut__in=["planifie", "confirme"],
                                       date__lte=limite).select_related("groupe"):
        for jour in _occurrences(ev, aujourdhui, limite):
            liste.append((jour, ev))
    liste.sort(key=lambda x: (x[0], x[1].heure or "99:99"))
    return ok({"horizon_jours": horizon, "evenements": [
        {**_json_ev(ev, jour), "dans_jours": (jour - aujourdhui).days}
        for jour, ev in liste[:200]]})


# ─────────────────────────── écriture ───────────────────────────

def _valider(d, ev=None):
    """Contrôles communs création / modification. Retourne (champs, erreur)."""
    titre = (d.get("titre") or "").strip()
    if not titre:
        return None, "Le titre de l'événement est obligatoire."
    debut = _date(d.get("date"))
    if not debut:
        return None, "La date de l'événement est obligatoire (format AAAA-MM-JJ)."
    fin = _date(d.get("date_fin")) or debut
    if fin < debut:
        return None, "La date de fin ne peut pas précéder la date de début."
    type_ev = d.get("type") or "culte"
    if type_ev not in dict(Evenement.TYPES):
        return None, "Type d'événement inconnu."
    statut = d.get("statut") or "planifie"
    if statut not in dict(Evenement.STATUTS_EVENEMENT):
        return None, "Statut d'événement inconnu."
    recurrence = d.get("recurrence") or "aucune"
    if recurrence not in dict(Evenement.RECURRENCES):
        return None, "Récurrence inconnue."
    capacite = d.get("capacite")
    if capacite in ("", None):
        capacite = None
    else:
        try:
            capacite = int(capacite)
        except (TypeError, ValueError):
            return None, "La capacité doit être un nombre entier."
        if capacite < 1:
            return None, "La capacité doit être au moins de 1 personne."
        if ev:
            deja = EvenementInscription.objects.filter(
                evenement=ev, statut__in=["inscrit", "confirme"]).count()
            if capacite and capacite < deja:
                return None, f"La capacité ne peut pas être inférieure aux {deja} inscrits actuels."
    try:
        rappel = int(d.get("rappel_jours") if d.get("rappel_jours") not in (None, "") else 1)
    except (TypeError, ValueError):
        rappel = 1
    champs = {
        "titre": titre[:200],
        "type": type_ev,
        "date": debut,
        "date_fin": fin if fin != debut else None,
        "heure": (d.get("heure") or "")[:5],
        "heure_fin": (d.get("heure_fin") or "")[:5],
        "lieu": (d.get("lieu") or "")[:200],
        "description": (d.get("description") or "").strip(),
        "journee_entiere": bool(d.get("journee_entiere")),
        "capacite": capacite,
        "public_cible": (d.get("public_cible") or "")[:120],
        "statut": statut,
        "recurrence": recurrence,
        "rappel_jours": max(0, min(rappel, 90)),
        "groupe_id": d.get("groupe_id") or None,
    }
    if champs["journee_entiere"]:
        champs["heure"] = ""
        champs["heure_fin"] = ""
    return champs, None


@auth_requise()
@permission_requise("evenements", "creer")
def evenement_creer(request):
    """Création complète (remplace la version minimale de la Phase 2)."""
    e = _eglise(request)
    d = corps(request)
    champs, message = _valider(d)
    if message:
        return err(message)
    ev = Evenement.objects.create(eglise=e, cree_par=request.utilisateur,
                                  responsable_id=d.get("responsable_id") or None, **champs)
    tracer(request.utilisateur, "evenements", "creer",
           f"Événement créé : {ev.titre} du {ev.date} ({ev.get_statut_display()})")
    return ok({"evenement": _json_ev(ev)})


@auth_requise()
@permission_requise("evenements", "modifier")
def evenement_modifier(request):
    e = _eglise(request)
    d = corps(request)
    ev = Evenement.objects.filter(eglise=e, id=d.get("id")).first()
    if not ev:
        return err("Événement introuvable dans cette Église.", 404)
    champs, message = _valider(d, ev)
    if message:
        return err(message)
    ancien = f"{ev.titre} du {ev.date}"
    for cle, valeur in champs.items():
        setattr(ev, cle, valeur)
    ev.save()
    tracer(request.utilisateur, "evenements", "modifier", f"Événement modifié : {ancien}")
    return ok({"evenement": _json_ev(ev)})


@auth_requise()
@permission_requise("evenements", "modifier")
def evenement_statut(request):
    e = _eglise(request)
    d = corps(request)
    ev = Evenement.objects.filter(eglise=e, id=d.get("id")).first()
    if not ev:
        return err("Événement introuvable dans cette Église.", 404)
    statut = d.get("statut")
    if statut not in dict(Evenement.STATUTS_EVENEMENT):
        return err("Statut d'événement inconnu.")
    ev.statut = statut
    ev.save(update_fields=["statut", "updated_at"])
    tracer(request.utilisateur, "evenements", "modifier",
           f"Événement {ev.titre} passé en « {statut} »")
    return ok({"evenement": _json_ev(ev)})


@auth_requise()
@permission_requise("evenements", "supprimer")
def evenement_supprimer(request):
    e = _eglise(request)
    d = corps(request)
    ev = Evenement.objects.filter(eglise=e, id=d.get("id")).first()
    if not ev:
        return err("Événement introuvable dans cette Église.", 404)
    if Presence.objects.filter(eglise=e, evenement=ev).exists():
        return err("Cet événement porte des pointages de présence : annulez-le plutôt que de le supprimer.")
    titre = f"{ev.titre} du {ev.date}"
    ev.delete()
    tracer(request.utilisateur, "evenements", "supprimer", f"Événement supprimé : {titre}")
    return ok({"supprime": True})


# ─────────────────────────── inscriptions ───────────────────────────

@auth_requise()
@permission_requise("evenements", "creer")
def evenement_inscrire(request):
    e = _eglise(request)
    d = corps(request)
    ev = Evenement.objects.filter(eglise=e, id=d.get("evenement_id")).first()
    if not ev:
        return err("Événement introuvable dans cette Église.", 404)
    membre = Membre.objects.filter(eglise=e, id=d.get("membre_id")).first()
    if not membre:
        return err("Membre introuvable dans cette Église.", 404)
    if ev.statut in ("annule", "termine"):
        return err("Cet événement est annulé ou terminé : les inscriptions sont fermées.")
    actives = EvenementInscription.objects.filter(evenement=ev, statut__in=["inscrit", "confirme"])
    if ev.capacite and actives.count() >= ev.capacite:
        return err("La capacité de cet événement est atteinte.")
    inscription, cree = EvenementInscription.objects.get_or_create(
        eglise=e, evenement=ev, membre=membre,
        defaults={"cree_par": request.utilisateur})
    if not cree and inscription.statut == "desinscrit":
        inscription.statut = "inscrit"
        inscription.save(update_fields=["statut"])
    tracer(request.utilisateur, "evenements", "creer",
           f"Inscription de {membre.nom} à {ev.titre}")
    return ok({"inscription": {"id": inscription.id, "statut": inscription.statut},
               "inscrits": actives.count() + (1 if cree else 0)})


@auth_requise()
@permission_requise("evenements", "modifier")
def evenement_desinscrire(request):
    e = _eglise(request)
    d = corps(request)
    inscription = EvenementInscription.objects.filter(
        eglise=e, evenement_id=d.get("evenement_id"), membre_id=d.get("membre_id")).first()
    if not inscription:
        return err("Aucune inscription à retirer.", 404)
    inscription.statut = "desinscrit"
    inscription.save(update_fields=["statut"])
    tracer(request.utilisateur, "evenements", "modifier", "Désinscription d'un membre à un événement")
    return ok({"desinscrit": True})


@auth_requise()
@permission_requise("evenements", "consulter")
def evenement_participants(request):
    e = _eglise(request)
    ev = Evenement.objects.filter(eglise=e, id=request.GET.get("id")).first()
    if not ev:
        return err("Événement introuvable dans cette Église.", 404)
    lignes = EvenementInscription.objects.filter(eglise=e, evenement=ev).select_related("membre")
    return ok({"evenement": {"id": ev.id, "titre": ev.titre, "capacite": ev.capacite},
               "participants": [{
                   "membre_id": l.membre_id, "matricule": l.membre.matricule,
                   "nom": f"{l.membre.nom} {l.membre.postnom} {l.membre.prenom}".strip(),
                   "telephone": l.membre.telephone, "statut": l.statut,
                   "note": l.note} for l in lignes if l.statut != "desinscrit"],
               "places_restantes": (ev.capacite - lignes.filter(
                   statut__in=["inscrit", "confirme"]).count()) if ev.capacite else None})


# ─────────────────────────── exports ───────────────────────────

@auth_requise()
@permission_requise("evenements", "exporter")
def evenement_ical(request):
    """Flux iCalendar : un événement (?id=) ou le mois entier (?mois=)."""
    e = _eglise(request)
    if request.GET.get("id"):
        qs = Evenement.objects.filter(eglise=e, id=request.GET["id"])
        nom_fichier = "evenement.ics"
    else:
        debut, fin = _mois(request.GET.get("mois"))
        qs = Evenement.objects.filter(eglise=e, date__gte=debut, date__lte=fin)
        nom_fichier = "calendrier.ics"
    lignes = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//OmniChurch Connect//FR",
              f"X-WR-CALNAME:{e.nom}"]
    for ev in qs:
        if ev.statut == "annule":
            continue
        jour = ev.date
        heure = (ev.heure or "09:00").replace(":", "")
        fin_heure = (ev.heure_fin or ev.heure or "10:00").replace(":", "")
        lignes += [
            "BEGIN:VEVENT",
            f"UID:omnichurch-{ev.id}@omnichurch",
            f"DTSTART:{jour.strftime('%Y%m%d')}T{heure}00",
            f"DTEND:{(ev.date_fin or jour).strftime('%Y%m%d')}T{fin_heure}00",
            f"SUMMARY:{ev.titre}",
            f"LOCATION:{ev.lieu or e.ville or ''}",
            f"DESCRIPTION:{(ev.description or '').replace(chr(10), ' ')[:400]}",
            f"STATUS:{'CONFIRMED' if ev.statut == 'confirme' else 'TENTATIVE'}",
            "END:VEVENT",
        ]
    lignes.append("END:VCALENDAR")
    reponse = HttpResponse("\r\n".join(lignes), content_type="text/calendar; charset=utf-8")
    reponse["Content-Disposition"] = f'attachment; filename="{nom_fichier}"'
    tracer(request.utilisateur, "evenements", "exporter", f"Export calendrier {nom_fichier}")
    return reponse


@auth_requise()
@permission_requise("evenements", "exporter")
def calendrier_export(request):
    e = _eglise(request)
    debut, fin = _mois(request.GET.get("mois"))
    sortie = io.StringIO()
    w = csv.writer(sortie, delimiter=";")
    w.writerow(["Date", "Heure", "Fin", "Titre", "Type", "Lieu", "Statut", "Récurrence",
                "Capacité", "Inscrits"])
    for ev in Evenement.objects.filter(eglise=e).order_by("date", "heure"):
        for jour in _occurrences(ev, debut, fin):
            w.writerow([jour.isoformat(), ev.heure, ev.heure_fin, ev.titre, ev.get_type_display(),
                        ev.lieu, ev.get_statut_display(), ev.get_recurrence_display(),
                        ev.capacite or "", EvenementInscription.objects.filter(
                            evenement=ev, statut__in=["inscrit", "confirme"]).count()])
    reponse = HttpResponse("\ufeff" + sortie.getvalue(), content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = f'attachment; filename="calendrier-{debut.strftime("%Y-%m")}.csv"'
    return reponse
