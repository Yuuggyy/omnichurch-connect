"""Test fonctionnel de la Phase 2 : membres, matricules, effectifs, groupes, présences,
isolation entre Églises et contrôle des permissions. À lancer : python3 test_phase2.py"""
import json, os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client
from core.models import Eglise, Utilisateur, Role, UserRole, TokenSession, Membre, Presence
from core.security import hasher, ACTIONS, MODULES

c = Client()
ok = lambda r: r.json().get("success") is True

def post(url, payload, **h):
    return c.post(url, data=json.dumps(payload), content_type="application/json", **h)
res = []

def check(nom, condition, detail=""):
    res.append((nom, bool(condition), detail))
    print(("  ✓ " if condition else "  ✗ ") + nom + (f" — {detail}" if detail and not condition else ""))

# ── préparation : deux Églises indépendantes
for slug in ("test-elm", "test-autre"):
    Eglise.objects.filter(slug=slug).delete()
e1 = Eglise.objects.create(nom="Église Test Lumière", slug="test-elm", statut="approuve", ville="Kinshasa")
e2 = Eglise.objects.create(nom="Église Test Autre", slug="test-autre", statut="approuve", ville="Lubumbashi")
admin1 = Utilisateur.objects.create(eglise=e1, nom_complet="Admin Un", email="admin1@test.cd",
                                    mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
admin2 = Utilisateur.objects.create(eglise=e2, nom_complet="Admin Deux", email="admin2@test.cd",
                                    mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
# utilisateur limité à la consultation des membres
role_lecture = Role.objects.create(eglise=e1, nom="Secrétaire", permissions={"membres": ["consulter"]})
lecture = Utilisateur.objects.create(eglise=e1, nom_complet="Secrétaire", email="sec@test.cd",
                                     mot_de_passe=hasher("Test!2026"))
UserRole.objects.create(utilisateur=lecture, role=role_lecture)
t1 = TokenSession.objects.create(utilisateur=admin1).token
t2 = TokenSession.objects.create(utilisateur=admin2).token
tl = TokenSession.objects.create(utilisateur=lecture).token
H1, H2, HL = {"HTTP_X_AUTH_TOKEN": t1}, {"HTTP_X_AUTH_TOKEN": t2}, {"HTTP_X_AUTH_TOKEN": tl}

print("\n── Création et validation des dossiers")
r = post("/api/membre/creer/", {"nom": "Kabila", "postnom": "Mwamba", "prenom": "Jean",
         "sexe": "M", "telephone": "+243810000001", "date_naissance": "1990-05-12"}, **H1)
check("création d'un membre", ok(r), r.content[:200])
m1 = r.json()["data"]["membre"]["id"]
check("matricule vide avant validation", r.json()["data"]["membre"]["matricule"] == "")
check("dossier en attente de validation", r.json()["data"]["membre"]["etat_validation"] == "a_valider")

r = post("/api/membre/valider/", {"id": m1}, **H1)
mat = r.json()["data"]["matricule"]
check("matricule attribué à la validation", mat == "EGL-2026-0001", mat)

r = post("/api/membre/creer/", {"nom": "Kabila", "postnom": "Mwamba", "prenom": "Jean",
         "telephone": "+243810000001"}, **H1)
m_dup = r.json()["data"]["membre"]["id"]
r = post("/api/membre/valider/", {"id": m_dup}, **H1)
check("matricules jamais réutilisés", r.json()["data"]["matricule"].endswith("0002"), r.content[:120])

r = c.get("/api/membres/doublons/", **H1)
check("doublons potentiels détectés", r.json()["data"]["total"] >= 1,
      str(r.json()["data"].get("total")))
check("fusion jamais automatique", "Aucune fusion" in r.json()["data"]["note"])

print("\n── Workflow retour et rejet")
r = post("/api/membre/creer/", {"nom": "Nsimba", "prenom": "Alice", "sexe": "F"}, **H1)
m3 = r.json()["data"]["membre"]["id"]
r = post("/api/membre/retourner/", {"id": m3, "motif": "Téléphone manquant"}, **H1)
check("retour pour correction", r.json()["data"]["membre"]["etat_validation"] == "retourne")
r = post("/api/membre/rejeter/", {"id": m3}, **H1)
check("rejet sans motif refusé", not ok(r), r.content[:120])
r = post("/api/membre/rejeter/", {"id": m3, "motif": "Dossier incomplet"}, **H1)
check("rejet avec motif", r.json()["data"]["membre"]["etat_validation"] == "rejete")

print("\n── Effectif global déclaré")
post("/api/effectif/creer/", {"categorie": "adultes", "valeur": 120, "periode": "10/2026"}, **H1)
post("/api/effectif/creer/", {"categorie": "enfants", "valeur": 45, "periode": "10/2026"}, **H1)
r = c.get("/api/effectifs/", **H1).json()["data"]
check("règle additive respectée", r["total_general"] == r["membres_enregistres"] + r["effectif_declare"],
      f'{r["membres_enregistres"]} + {r["effectif_declare"]} = {r["total_general"]}')
check("total général = 165 + dossiers", r["effectif_declare"] == 165, str(r["effectif_declare"]))
check("avertissement de chevauchement présent", "double comptage" in r["avertissement"])

print("\n── Groupes")
r = post("/api/groupe/creer/", {"nom": "Chorale", "type": "chorale"}, **H1)
gid = r.json()["data"]["groupe"]["id"]
check("groupe créé", ok(r))
r = post("/api/groupe/affecter/", {"membre_id": m1, "groupe_id": gid, "fonction": "chef de chorale"}, **H1)
check("membre affecté au groupe", ok(r))
r = c.get("/api/groupes/", **H1).json()["data"]["groupes"][0]
check("effectif du groupe calculé", r["effectif"] == 1, str(r["effectif"]))
r = post("/api/groupe/affecter/", {"membre_id": m1, "groupe_id": gid}, **H1)
check("pas de double appartenance", ok(r))

print("\n── Présences")
r = post("/api/evenement/creer/", {"titre": "Culte du dimanche", "type": "culte", "date": "2026-10-25"}, **H1)
ev = r.json()["data"]["evenement"]["id"]
post("/api/presence/pointer/", {"evenement": ev, "membre_id": m1, "statut": "present"}, **H1)
r = post("/api/presence/pointer/", {"evenement": ev, "membre_id": m1, "statut": "retard"}, **H1)
check("pointage unique par membre", r.json()["data"]["nouveau"] is False)
post("/api/presence/pointer/", {"evenement": ev, "visiteur_nom": "Visiteur inconnu"}, **H1)
post("/api/presence/pointer/", {"evenement": ev, "effectif_global": 80}, **H1)
r = c.get("/api/presences/?evenement=" + str(ev), **H1).json()["data"]
check("présents identifiés", r["total_identifies"] == 1, str(r["total_identifies"]))
check("visiteurs comptés", r["visiteurs"] == 1, str(r["visiteurs"]))
check("effectif global pointé", r["effectif_global"] == 80, str(r["effectif_global"]))

print("\n── Permissions vérifiées côté serveur")
r = post("/api/membre/creer/", {"nom": "Interdit"}, **HL)
check("création refusée au rôle lecture seule", r.status_code == 403, str(r.status_code))
r = c.get("/api/membres/", **HL)
check("consultation autorisée au rôle lecture", ok(r))

print("\n── Isolation entre Églises")
r = c.get(f"/api/membre/?id={m1}", **H2)
check("autre Église ne lit pas le dossier", r.status_code == 404, str(r.status_code))
r = post("/api/membre/valider/", {"id": m1}, **H2)
check("autre Église ne valide pas le dossier", r.status_code == 404, str(r.status_code))
r = c.get("/api/groupes/", **H2).json()["data"]["groupes"]
check("aucun groupe d'une autre Église visible", all(g["id"] != gid for g in r))
r = c.get("/api/membres/", **H2).json()["data"]
check("liste des membres vide pour l'autre Église", r["total"] == 0, str(r["total"]))
r = post("/api/presence/pointer/", {"evenement": ev, "membre_id": m1}, **H2)
check("pointage croisé refusé", r.status_code == 404, str(r.status_code))

print("\n── Documents")
r = c.get(f"/api/document/fiche/?id={m1}", **H1)
check("fiche PDF générée", r.status_code == 200 and r["Content-Type"] == "application/pdf",
      str(r.status_code))
check("fiche PDF non vide", len(r.content) > 2000, str(len(r.content)))
r = c.get(f"/api/document/carte/?id={m1}", **H1)
check("carte PDF générée", r.status_code == 200 and len(r.content) > 1000)
r = c.get(f"/api/document/carte/?id={m3}", **H1)
check("carte refusée sans matricule", r.status_code == 400, str(r.status_code))

print("\n── Export et tableau de bord")
r = c.get("/api/membres/export/", **H1)
check("export CSV", r.status_code == 200 and "Matricule" in r.content.decode("utf-8-sig")[:60])
r = c.get("/api/bord/stats/", **H1).json()["data"]
check("tableau de bord alimenté", r["membres_total"] >= 3 and r["effectif_declare"] == 165,
      str(r))

print("\n── Journal d'audit")
from core.models import JournalAudit
acts = list(JournalAudit.objects.filter(eglise=e1).values_list("action", flat=True))
for a in ("creation", "validation", "retour", "rejet", "effectif"):
    check(f"audit : {a}", a in acts)

total = len(res); reussis = sum(1 for _, c_, _ in res if c_)
print(f"\n{'═'*60}\n{reussis}/{total} vérifications réussies")
for nom, c_, detail in res:
    if not c_:
        print("  ÉCHEC :", nom, detail)
