"""Test fonctionnel de la Phase 3 : calendrier, événements, récurrences, inscriptions,
exports, isolation entre Églises et permissions. À lancer : python3 test_phase3.py"""
import json, os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client
from core.models import (Eglise, Utilisateur, Role, UserRole, TokenSession, Membre,
                         Evenement, EvenementInscription, Presence)
from core.security import hasher

c = Client()
ok = lambda r: r.json().get("success") is True
res = []


def post(url, payload, **h):
    return c.post(url, data=json.dumps(payload), content_type="application/json", **h)


def check(nom, condition, detail=""):
    res.append((nom, bool(condition), detail))
    print(("  ✓ " if condition else "  ✗ ") + nom + (f" — {detail}" if detail and not condition else ""))


# ── préparation
for slug in ("test-cal-a", "test-cal-b"):
    Eglise.objects.filter(slug=slug).delete()
e1 = Eglise.objects.create(nom="Église Cal A", slug="test-cal-a", statut="approuve", ville="Kinshasa")
e2 = Eglise.objects.create(nom="Église Cal B", slug="test-cal-b", statut="approuve", ville="Goma")
a1 = Utilisateur.objects.create(eglise=e1, nom_complet="Admin Cal A", email="calA@test.cd",
                                mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
a2 = Utilisateur.objects.create(eglise=e2, nom_complet="Admin Cal B", email="calB@test.cd",
                                mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
role_lecture = Role.objects.create(eglise=e1, nom="Lecteur calendrier",
                                   permissions={"evenements": ["consulter"]})
lecteur = Utilisateur.objects.create(eglise=e1, nom_complet="Lecteur", email="lecteur@test.cd",
                                     mot_de_passe=hasher("Test!2026"))
UserRole.objects.create(utilisateur=lecteur, role=role_lecture)
H1 = {"HTTP_X_AUTH_TOKEN": TokenSession.objects.create(utilisateur=a1).token}
H2 = {"HTTP_X_AUTH_TOKEN": TokenSession.objects.create(utilisateur=a2).token}
HL = {"HTTP_X_AUTH_TOKEN": TokenSession.objects.create(utilisateur=lecteur).token}

membre = Membre.objects.create(eglise=e1, nom="Kalala", postnom="Tshibang", prenom="Marie",
                               matricule="CAL-0001", etat_validation="valide")

print("\n── Création et validations")
r = post("/api/evenement/creer/", {"titre": "Culte de la Réformation", "type": "culte",
         "date": "2026-11-08", "heure": "09:00", "heure_fin": "11:30",
         "lieu": "Temple central", "capacite": 2}, **H1)
check("création d'un événement", ok(r), r.content[:200])
ev1 = r.json()["data"]["evenement"]["id"]
check("durée déduite des heures", r.json()["data"]["evenement"]["duree_minutes"] == 150,
      str(r.json()["data"]["evenement"].get("duree_minutes")))

check("titre obligatoire", post("/api/evenement/creer/", {"date": "2026-11-08"}, **H1).status_code == 400)
check("date invalide refusée",
      post("/api/evenement/creer/", {"titre": "X", "date": "08/13/2026"}, **H1).status_code == 400)
check("date de fin antérieure refusée",
      post("/api/evenement/creer/", {"titre": "X", "date": "2026-11-10",
                                     "date_fin": "2026-11-08"}, **H1).status_code == 400)
check("type inconnu refusé",
      post("/api/evenement/creer/", {"titre": "X", "date": "2026-11-10",
                                     "type": "banquet"}, **H1).status_code == 400)
check("capacité nulle refusée",
      post("/api/evenement/creer/", {"titre": "X", "date": "2026-11-10",
                                     "capacite": 0}, **H1).status_code == 400)

print("\n── Récurrences")
r = post("/api/evenement/creer/", {"titre": "Prière du mercredi", "type": "priere",
         "date": "2026-11-04", "heure": "18:00", "recurrence": "hebdomadaire"}, **H1)
ev_hebdo = r.json()["data"]["evenement"]["id"]
r = post("/api/evenement/creer/", {"titre": "Réunion des anciens", "type": "reunion",
         "date": "2026-11-15", "recurrence": "mensuelle"}, **H1)
ev_mens = r.json()["data"]["evenement"]["id"]
r = c.get("/api/calendrier/?mois=2026-11", **H1)
jours = r.json()["data"]["jours"]
mercredis = [j for j in jours if any(e["titre"] == "Prière du mercredi" for e in jours[j])]
check("récurrence hebdomadaire projetée", len(mercredis) == 4, f"{sorted(mercredis)}")
check("récurrence mensuelle projetée", any(
    e["titre"] == "Réunion des anciens" for j in jours for e in jours[j]))
r = c.get("/api/calendrier/?mois=2026-12", **H1)
jours12 = r.json()["data"]["jours"]
check("récurrence suit le mois suivant", any(
    e["titre"] == "Prière du mercredi" for j in jours12 for e in jours12[j]))
check("événement unique absent d'un autre mois",
      not any(e["titre"] == "Culte de la Réformation 2026"
              for liste in c.get("/api/calendrier/?mois=2027-02", **H1)
              .json()["data"]["jours"].values() for e in liste))

print("\n── Filtres et fiche")
r = c.get("/api/calendrier/?mois=2026-11&type=culte", **H1)
check("filtre par type", r.json()["data"]["total"] == 1, str(r.json()["data"]["total"]))
r = c.get(f"/api/evenement/?id={ev1}", **H1)
d = r.json()["data"]["evenement"]
check("fiche complète", d["titre"] == "Culte de la Réformation" and d["lieu"] == "Temple central")

print("\n── Inscriptions et capacité")
check("inscription d'un membre", ok(post("/api/evenement/inscrire/",
      {"evenement_id": ev1, "membre_id": membre.id}, **H1)))
membre2 = Membre.objects.create(eglise=e1, nom="Nsimba", prenom="Paul",
                                matricule="CAL-0002", etat_validation="valide")
membre3 = Membre.objects.create(eglise=e1, nom="Ilunga", prenom="Chantal",
                                matricule="CAL-0003", etat_validation="valide")
post("/api/evenement/inscrire/", {"evenement_id": ev1, "membre_id": membre2.id}, **H1)
r = post("/api/evenement/inscrire/", {"evenement_id": ev1, "membre_id": membre3.id}, **H1)
check("capacité respectée", r.status_code == 400, r.content[:150])
r = c.get(f"/api/evenement/participants/?id={ev1}", **H1)
check("liste des participants", len(r.json()["data"]["participants"]) == 2)
check("places restantes", r.json()["data"]["places_restantes"] == 0)
check("désinscription", ok(post("/api/evenement/desinscrire/",
      {"evenement_id": ev1, "membre_id": membre2.id}, **H1)))
check("nouvelle inscription après désinscription", ok(post("/api/evenement/inscrire/",
      {"evenement_id": ev1, "membre_id": membre3.id}, **H1)))
check("capacité réduite sous les inscrits refusée",
      post("/api/evenement/modifier/", {"id": ev1, "titre": "Culte", "date": "2026-11-08",
                                        "capacite": 1}, **H1).status_code == 400)

print("\n── Statuts, modification, suppression")
check("passage en confirmé", ok(post("/api/evenement/statut/",
      {"id": ev1, "statut": "confirme"}, **H1)))
check("statut inconnu refusé", post("/api/evenement/statut/",
      {"id": ev1, "statut": "peut-etre"}, **H1).status_code == 400)
check("modification du titre", ok(post("/api/evenement/modifier/", {
    "id": ev1, "titre": "Culte de la Réformation 2026", "date": "2026-11-08",
    "heure": "09:00", "heure_fin": "12:00", "capacite": 5, "statut": "confirme"}, **H1)))
check("journée entière efface les heures", ok(post("/api/evenement/modifier/", {
    "id": ev1, "titre": "Culte de la Réformation 2026", "date": "2026-11-08",
    "journee_entiere": True, "capacite": 5, "statut": "confirme"}, **H1)))
check("heures bien effacées", c.get(f"/api/evenement/?id={ev1}", **H1)
      .json()["data"]["evenement"]["heure"] == "")
Presence.objects.create(eglise=e1, evenement_id=ev1, membre=membre, statut="present")
check("suppression refusée si pointage",
      post("/api/evenement/supprimer/", {"id": ev1}, **H1).status_code == 400)
ev_libre = post("/api/evenement/creer/", {"titre": "Événement jetable",
                "date": "2026-11-20"}, **H1).json()["data"]["evenement"]["id"]
check("suppression d'un événement sans pointage",
      ok(post("/api/evenement/supprimer/", {"id": ev_libre}, **H1)))

print("\n── Rappels et exports")
r = c.get("/api/evenements/a-venir/?jours=30", **H1)
check("agenda à venir", r.json()["data"]["evenements"] and all(
    e["dans_jours"] >= 0 for e in r.json()["data"]["evenements"]))
r = c.get(f"/api/evenement/ical/?id={ev1}", **H1)
check("export iCalendar", r["Content-Type"].startswith("text/calendar")
      and b"BEGIN:VEVENT" in r.content)
r = c.get("/api/calendrier/export/?mois=2026-11", **H1)
check("export CSV", b"Culte de la" in r.content and b"Priere" in r.content or b"Pri" in r.content)

print("\n── Isolation et permissions")
check("Église B ne voit pas l'événement de A",
      c.get(f"/api/evenement/?id={ev1}", **H2).status_code == 404)
check("Église B ne peut pas modifier celui de A",
      post("/api/evenement/modifier/", {"id": ev1, "titre": "Piratage",
                                        "date": "2026-11-08"}, **H2).status_code == 404)
check("Église B ne peut pas inscrire un membre de A",
      post("/api/evenement/inscrire/", {"evenement_id": ev1, "membre_id": membre.id},
           **H2).status_code in (400, 404))
check("lecteur consulte", c.get("/api/calendrier/?mois=2026-11", **HL).status_code == 200)
check("lecteur ne crée pas", post("/api/evenement/creer/", {"titre": "X",
      "date": "2026-11-25"}, **HL).status_code == 403)
check("lecteur n'exporte pas", c.get("/api/evenement/ical/?id=" + str(ev1), **HL).status_code == 403)
check("sans jeton, refusé", c.get("/api/calendrier/").status_code in (401, 403))

total, reussis = len(res), sum(1 for _, c_, _ in res if c_)
print(f"\n{'='*54}\n{reussis}/{total} tests réussis")
if reussis < total:
    print("Échecs :")
    for nom, c_, detail in res:
        if not c_:
            print("  -", nom, detail)
