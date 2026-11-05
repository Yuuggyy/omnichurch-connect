"""Tests du suivi pastoral : dossiers, actions, prières, confidentialité, audit, isolation."""
import json, os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client
from core.models import (Eglise, Utilisateur, Role, UserRole, TokenSession, Membre,
                         DossierPastoral, ActionPastorale, DemandePriere, JournalAudit)
from core.security import hasher

c = Client()
res = []
def check(nom, condition, detail=""):
    res.append((nom, bool(condition), detail))
    print(("  ✓ " if condition else "  ✗ ") + nom + (f" — {detail}" if detail and not condition else ""))

def post(url, payload, tok=None):
    h = {"HTTP_X_AUTH_TOKEN": tok} if tok else {}
    return c.post(url, data=json.dumps(payload), content_type="application/json", **h)

def tok_de(u):
    return TokenSession.objects.create(utilisateur=u).token

# ── préparation
for slug in ("test-pas-a", "test-pas-b"):
    anc = Eglise.objects.filter(slug=slug).first()
    if anc:
        DemandePriere.objects.filter(eglise=anc).delete()
        ActionPastorale.objects.filter(eglise=anc).delete()
        DossierPastoral.objects.filter(eglise=anc).delete()
        anc.delete()

e1 = Eglise.objects.create(nom="Église Pastorale A", slug="test-pas-a", statut="approuve")
e2 = Eglise.objects.create(nom="Église Pastorale B", slug="test-pas-b", statut="approuve")

pasteur = Utilisateur.objects.create(eglise=e1, nom_complet="Pasteur Jean", email="pasteur@pas.cd",
                                     mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
autre = Utilisateur.objects.create(eglise=e1, nom_complet="Responsable Anne", email="anne@pas.cd",
                                   mot_de_passe=hasher("Test!2026"))
lecteur = Utilisateur.objects.create(eglise=e1, nom_complet="Lecteur Paul", email="paul@pas.cd",
                                     mot_de_passe=hasher("Test!2026"))
admin_b = Utilisateur.objects.create(eglise=e2, nom_complet="Admin B", email="admin@pasb.cd",
                                     mot_de_passe=hasher("Test!2026"), is_admin_principal=True)

role_lecture = Role.objects.create(eglise=e1, nom="Lecteur pastoral",
                                   permissions={"pastoral": ["consulter"]})
UserRole.objects.create(utilisateur=lecteur, role=role_lecture)
role_suivi = Role.objects.create(eglise=e1, nom="Responsable suivi",
                                 permissions={"pastoral": ["consulter", "creer", "modifier"]})
UserRole.objects.create(utilisateur=autre, role=role_suivi)

T_PAST, T_AUTRE, T_LECT = tok_de(pasteur), tok_de(autre), tok_de(lecteur)
T_B = tok_de(admin_b)

membre = Membre.objects.create(eglise=e1, nom="Kabila", prenom="Marie", statut="valide")

print("── Création et numérotation")
r = post("/api/pastoral/dossier/creer/", {"membre_id": membre.id, "type": "nouveau_converti",
        "objet": "Suivi après conversion", "confidentialite": "normal"}, T_PAST).json()
check("dossier créé", r.get("success") is True)
d1 = r["data"]["dossier"]
check("nom repris du membre", d1["personne_nom"] == "Kabila Marie", d1["personne_nom"])
check("numéro attribué", d1["numero"].startswith("DP-") and d1["numero"].endswith("00001"), d1["numero"])
r = post("/api/pastoral/dossier/creer/", {"personne_nom": "Visiteur Simon", "type": "visite"}, T_AUTRE).json()
check("deuxième dossier numéroté", r["data"]["dossier"]["numero"].endswith("00002"))
check("refus sans nom", post("/api/pastoral/dossier/creer/", {"objet": "x"}, T_PAST).json().get("success") is False)
check("responsable par défaut = créateur", r["data"]["dossier"]["responsable_id"] == autre.id)

print("── Actions et étapes")
r = post("/api/pastoral/action/", {"dossier_id": d1["id"], "type": "visite_domicile",
        "lieu": "Kintambo", "resume": "Famille accueillante, prière faite.",
        "prochaine_etape": "Revoir dans deux semaines", "echeance": "2026-12-01"}, T_PAST).json()
check("action enregistrée", r.get("success") is True)
check("dossier passé en cours", r["data"]["dossier"]["statut"] == "en_cours")
check("prochaine étape enregistrée", r["data"]["dossier"]["prochaine_etape"].startswith("Revoir"))
check("type d'action inconnu refusé",
      post("/api/pastoral/action/", {"dossier_id": d1["id"], "type": "nimportequoi"}, T_PAST)
      .json().get("success") is False)

r = post("/api/pastoral/dossier/", {"id": d1["id"]}, T_PAST).json()
check("historique du dossier", len(r["data"]["dossier"]["historique"]) == 1)
check("échéance visible", r["data"]["dossier"]["echeance"] == "2026-12-01")

print("── Confidentialité")
r = post("/api/pastoral/dossier/modifier/", {"id": d1["id"], "confidentialite": "confidentiel"}, T_PAST).json()
check("passage en confidentiel", r["data"]["dossier"]["confidentialite"] == "confidentiel")

avant = JournalAudit.objects.filter(eglise=e1, module="pastoral").count()
r = post("/api/pastoral/dossier/", {"id": d1["id"]}, T_PAST).json()
check("responsable principal lit le confidentiel", r.get("success") is True)
apres = JournalAudit.objects.filter(eglise=e1, module="pastoral", action="consulter").count()
check("consultation tracée dans l'audit", apres > 0, f"{avant} → {apres}")

r = c.post("/api/pastoral/dossier/", data=json.dumps({"id": d1["id"]}),
           content_type="application/json", HTTP_X_AUTH_TOKEN=T_AUTRE).json()
check("tiers non responsable refusé", r.get("success") is False and "confidentiel" in r.get("error", "").lower())
r = post("/api/pastoral/dossier/", {"id": d1["id"]}, T_LECT).json()
check("lecteur simple refusé sur confidentiel", r.get("success") is False)
r = post("/api/pastoral/", {}, T_AUTRE).json()
dossiers_vus = {x["numero"] for x in r["data"]["dossiers"]}
check("liste masque le confidentiel", d1["numero"] not in dossiers_vus, str(dossiers_vus))
check("compteur de dossiers masqués", r["data"]["masques"] >= 1)

r = post("/api/pastoral/dossier/", {"id": d1["id"]}, T_B).json()
check("Église B n'accède pas au dossier", r.get("success") is False)

print("── Prières")
r = post("/api/pastoral/priere/creer/", {"membre_id": membre.id, "sujet": "Santé de la mère",
        "urgence": "haute"}, T_PAST).json()
check("prière enregistrée", r.get("success") is True)
pid = r["data"]["priere"]["id"]
check("sujet obligatoire", post("/api/pastoral/priere/creer/", {"detail": "x"}, T_PAST)
      .json().get("success") is False)
r = post("/api/pastoral/prieres/", {}, T_PAST).json()
check("prière listée", r["data"]["total"] >= 1 and r["data"]["nouvelles"] >= 1)
r = post("/api/pastoral/priere/statut/", {"id": pid, "statut": "exaucee"}, T_PAST).json()
check("statut prière modifié", r["data"]["priere"]["statut"] == "exaucee")
check("statut inconnu refusé", post("/api/pastoral/priere/statut/", {"id": pid, "statut": "x"}, T_PAST)
      .json().get("success") is False)

print("── Tableau de bord, export, isolation, permissions")
post("/api/pastoral/dossier/creer/", {"personne_nom": "Converti Public", "type": "nouveau_converti",
     "confidentialite": "normal"}, T_PAST)
r = post("/api/pastoral/bord/", {}, T_PAST).json()
check("tableau de bord pastoral", r.get("success") is True and "ouverts" in r["data"])
check("confidentiels comptés", r["data"]["confidentiels"] >= 1)
check("nouveaux convertis comptés", r["data"]["nouveaux_convertis"] >= 1)
r = post("/api/pastoral/export/", {}, T_PAST)
check("export CSV", r.status_code == 200 and "Numéro" in r.content.decode())
r = post("/api/pastoral/", {}, T_B).json()
check("Église B ne voit aucun dossier", r["data"]["total"] == 0)
check("Église B ne peut pas créer", post("/api/pastoral/dossier/creer/",
      {"personne_nom": "X"}, T_B).json().get("success") is True and
      DossierPastoral.objects.filter(eglise=e2).count() == 1)
check("lecteur consulte", post("/api/pastoral/", {}, T_LECT).json().get("success") is True)
check("lecteur ne crée pas", post("/api/pastoral/dossier/creer/",
      {"personne_nom": "Y"}, T_LECT).json().get("success") is False)
check("lecteur n'exporte pas", post("/api/pastoral/export/", {}, T_LECT).status_code == 403)
check("sans jeton refusé", c.post("/api/pastoral/", data="{}",
      content_type="application/json").status_code == 401)

print("\n" + "=" * 54)
reussis = sum(1 for _, ok_, _ in res if ok_)
print(f"{reussis}/{len(res)} tests réussis")
if reussis < len(res):
    print("Échecs :")
    for nom, ok_, detail in res:
        if not ok_:
            print("  -", nom, "|", detail)
