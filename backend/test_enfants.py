"""Tests du module enfants et école du dimanche."""
import json, os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client
from core.models import (Eglise, Utilisateur, Role, UserRole, TokenSession, JournalAudit,
                         Enfant, PersonneAutorisee, ClasseEnfants, PresenceEnfant, IncidentEnfant)

c = Client()
res = []
def post(url, payload, **h):
    return c.post(url, data=json.dumps(payload), content_type="application/json", **h)
def check(nom, cond, detail=""):
    res.append((nom, bool(cond)))
    print(("  ✓ " if cond else "  ✗ ") + nom + (f" — {detail}" if detail and not cond else ""))

from core.security import hasher
for slug in ("test-enf-a", "test-enf-b"):
    ancienne = Eglise.objects.filter(slug=slug).first()
    if ancienne:
        PresenceEnfant.objects.filter(eglise=ancienne).delete()
        IncidentEnfant.objects.filter(eglise=ancienne).delete()
        PersonneAutorisee.objects.filter(enfant__eglise=ancienne).delete()
        Enfant.objects.filter(eglise=ancienne).delete()
        ClasseEnfants.objects.filter(eglise=ancienne).delete()
        ancienne.delete()

e1 = Eglise.objects.create(nom="Église Enfants A", slug="test-enf-a", statut="approuve")
e2 = Eglise.objects.create(nom="Église Enfants B", slug="test-enf-b", statut="approuve")
adm = Utilisateur.objects.create(eglise=e1, nom_complet="Admin Enfants", email="enf1@test.cd",
                                 mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
mon = Utilisateur.objects.create(eglise=e1, nom_complet="Monitrice", email="mon1@test.cd",
                                 mot_de_passe=hasher("Test!2026"))
lect = Utilisateur.objects.create(eglise=e1, nom_complet="Lecteur", email="lec1@test.cd",
                                  mot_de_passe=hasher("Test!2026"))
adm2 = Utilisateur.objects.create(eglise=e2, nom_complet="Admin B", email="enf2@test.cd",
                                  mot_de_passe=hasher("Test!2026"), is_admin_principal=True)

role_mon = Role.objects.create(eglise=e1, nom="Moniteur", systeme=False,
    permissions={"enfants": ["consulter", "creer", "modifier"]})
UserRole.objects.create(utilisateur=mon, role=role_mon, accorde_par=adm)
role_lect = Role.objects.create(eglise=e1, nom="Lecteur enfants", systeme=False,
    permissions={"enfants": ["consulter"]})
UserRole.objects.create(utilisateur=lect, role=role_lect, accorde_par=adm)

def jeton(u):
    return TokenSession.objects.create(utilisateur=u).token
T_ADM, T_MON, T_LEC, T_ADM2 = jeton(adm), jeton(mon), jeton(lect), jeton(adm2)
H = lambda t: {"HTTP_X_AUTH_TOKEN": t}

print("── Création et champs sensibles")
r = post("/api/enfant/creer/", {"nom": "Kalala", "prenom": "Grâce", "sexe": "F",
        "date_naissance": "2018-04-12", "tuteur_nom": "Mme Kalala", "tuteur_telephone": "+243810000000",
        "sante": "Asthme léger", "besoins": "Aucun", "autorisation_photo": True}, **H(T_ADM))
d = r.json(); check("enfant créé", d.get("success") is True, d)
eid = d["data"]["enfant"]["id"]
check("code enfant attribué", d["data"]["enfant"]["code"].startswith("ENF-"), d["data"]["enfant"].get("code"))
check("âge calculé", d["data"]["enfant"]["age"] == 8, d["data"]["enfant"].get("age"))
check("santé visible avec droit de validation", d["data"]["enfant"].get("sante") == "Asthme léger")
r2 = post("/api/enfant/", {"id": eid}, **H(T_MON))
check("santé masquée pour un moniteur", "sante" not in r2.json()["data"]["enfant"]
      and r2.json()["data"]["enfant"].get("sensible_restreint") is True, r2.json()["data"]["enfant"])

print("── Personnes autorisées et sortie")
r = post("/api/enfant/autorise/", {"enfant_id": eid, "nom": "Papa Kalala", "lien": "père",
        "telephone": "+243820000000", "piece": "Passeport"}, **H(T_ADM))
check("personne autorisée ajoutée", r.json().get("success") is True)
aid = r.json()["data"]["autorise"]["id"]
r = post("/api/enfants/pointer/", {"enfant_id": eid, "arrivee": "09:05"}, **H(T_MON))
check("arrivée pointée", r.json().get("success") is True)
r = post("/api/enfants/sortie/", {"enfant_id": eid, "autorise_id": 99999, "heure": "12:00"}, **H(T_MON))
check("sortie refusée à une personne non autorisée", r.status_code == 403, r.status_code)
r = post("/api/enfants/sortie/", {"enfant_id": eid, "autorise_id": aid, "heure": "12:00"}, **H(T_MON))
check("sortie acceptée pour la personne autorisée", r.json().get("success") is True, r.json())
check("audit de la sortie", JournalAudit.objects.filter(eglise=e1, action="sortie").exists())
check("audit du refus", JournalAudit.objects.filter(eglise=e1, action="sortie_refusee").exists())
p = PresenceEnfant.objects.get(enfant_id=eid)
check("départ enregistré", p.depart == "12:00")

print("── Classes et affectation")
r = post("/api/enfants/classe/creer/", {"nom": "Étoiles 6-8", "age_min": 6, "age_max": 8,
        "capacite": 2, "salle": "Salle B"}, **H(T_ADM))
check("classe créée", r.json().get("success") is True)
cid = r.json()["data"]["classe"]["id"]
r = post("/api/enfants/affecter/", {"enfant_id": eid, "classe_id": cid}, **H(T_ADM))
check("enfant affecté", r.json().get("success") is True, r.json())
r = post("/api/enfants/affecter/", {"enfant_id": 0, "classe_id": cid}, **H(T_ADM))
check("affectation refusée si enfant inconnu", r.status_code == 404)

print("── Incidents, leçons et progression")
r = post("/api/enfants/incident/creer/", {"enfant_id": eid, "type": "sante", "gravite": "legere",
        "description": "Petite chute au terrain"}, **H(T_MON))
check("incident signalé", r.json().get("success") is True)
r = post("/api/enfants/incident/creer/", {"enfant_id": eid, "description": ""}, **H(T_MON))
check("incident sans description refusé", r.status_code == 400)
r = post("/api/enfants/incidents/", {}, **H(T_ADM))
check("incident non signalé au parent compté", r.json()["data"]["non_informes"] == 1, r.json()["data"])
r = post("/api/enfants/lecon/creer/", {"titre": "Le bon Samaritain", "classe_id": cid,
        "objectif": "Aimer son prochain"}, **H(T_MON))
check("leçon créée", r.json().get("success") is True)
lid = r.json()["data"]["lecon"]["id"]
r = post("/api/enfants/progression/", {"enfant_id": eid, "lecon_id": lid, "niveau": "acquis"}, **H(T_MON))
check("progression enregistrée", r.json().get("success") is True)
r = post("/api/enfants/lecons/", {}, **H(T_MON))
check("leçon marquée acquise", r.json()["data"]["lecons"][0]["acquis"] == 1, r.json()["data"]["lecons"])

print("── Tableau de bord, export, isolation, permissions")
r = post("/api/enfants/bord/", {}, **H(T_ADM))
b = r.json()["data"]
check("tableau de bord enfants", b["actifs"] == 1 and b["classes"] == 1, b)
check("autorisations manquantes détectées", b["sans_autorisation"] == 0, b["sans_autorisation"])
r = post("/api/enfants/export/", {}, **H(T_ADM))
check("export CSV", r.status_code == 200 and b"ENF-" in r.content)
r = post("/api/enfants/", {}, **H(T_ADM2))
check("Église B ne voit aucun enfant", r.json()["data"]["total"] == 0)
r = post("/api/enfant/", {"id": eid}, **H(T_ADM2))
check("Église B ne peut pas ouvrir la fiche", r.status_code == 404)
r = post("/api/enfant/creer/", {"nom": "Intrus"}, **H(T_LEC))
check("lecteur ne crée pas", r.status_code == 403)
r = post("/api/enfants/", {}, **H(T_LEC))
check("lecteur consulte", r.json().get("success") is True)
r = post("/api/enfants/export/", {}, **H(T_LEC))
check("lecteur n'exporte pas", r.status_code == 403)
r = post("/api/enfants/", {})
check("sans jeton refusé", r.status_code == 401)

print("\n" + "=" * 54)
ok_n = sum(1 for _, v in res if v)
print(f"{ok_n}/{len(res)} tests réussis")
if ok_n < len(res):
    print("Échecs :")
    for n, v in res:
        if not v:
            print("  -", n)
