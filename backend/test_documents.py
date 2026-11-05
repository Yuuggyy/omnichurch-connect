"""Tests documents et actes officiels (section 17)."""
import json, os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from datetime import date, timedelta
from django.test import Client
from core.models import (Eglise, Utilisateur, Role, UserRole, TokenSession, Membre,
                         ModeleDocument, Document, DocumentVersion)
from core.security import hasher

c = Client(); res = []
def post(url, payload, **h):
    return c.post(url, data=json.dumps(payload), content_type="application/json", **h)
def check(n, cond, d=""):
    res.append((n, bool(cond))); print(("  ✓ " if cond else "  ✗ ") + n + (f" — {d}" if d and not cond else ""))

for s in ("test-doc-a", "test-doc-b"):
    v = Eglise.objects.filter(slug=s).first()
    if v:
        DocumentVersion.objects.filter(document__eglise=v).delete(); Document.objects.filter(eglise=v).delete()
        ModeleDocument.objects.filter(eglise=v).delete(); Membre.objects.filter(eglise=v).delete(); v.delete()

e1 = Eglise.objects.create(nom="Église Documents", slug="test-doc-a", statut="approuve", ville="Kinshasa")
e2 = Eglise.objects.create(nom="Église Doc B", slug="test-doc-b", statut="approuve")
adm = Utilisateur.objects.create(eglise=e1, nom_complet="Secrétaire", email="doc1@test.cd",
                                 mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
lec = Utilisateur.objects.create(eglise=e1, nom_complet="Lecteur", email="doc2@test.cd",
                                 mot_de_passe=hasher("Test!2026"))
b = Utilisateur.objects.create(eglise=e2, nom_complet="Admin B", email="doc3@test.cd",
                               mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
r = Role.objects.create(eglise=e1, nom="Lecture docs", permissions={"documents": ["consulter"]})
UserRole.objects.create(utilisateur=lec, role=r)
T, TL, TB = [TokenSession.objects.create(utilisateur=u).token for u in (adm, lec, b)]
H = lambda t: {"HTTP_X_AUTH_TOKEN": t}
m = Membre.objects.create(eglise=e1, nom="Mbala", prenom="Josué", matricule="LDM-0007", statut="valide")

print("── Modèles et génération")
d = post("/api/documents/modele/creer/", {"nom": "Baptême standard", "type": "certificat_bapteme",
        "jours_alerte": 60}, **H(T)).json()
check("modèle créé", d.get("success") is True, d)
mid = d["data"]["modele"]["id"]
check("corps par défaut injecté", "Nous certifions" in post("/api/documents/modeles/", {}, **H(T)).json()["data"]["modeles"][0]["apercu"])
check("type inconnu refusé", post("/api/documents/modele/creer/", {"nom": "X", "type": "inconnu"}, **H(T)).status_code == 400)

d = post("/api/document/generer/", {"type": "certificat_bapteme", "modele_id": mid, "membre_id": m.id}, **H(T)).json()
check("document généré", d.get("success") is True, d)
doc = d["data"]["document"]
did = doc["id"]
check("numérotation unique par type", doc["numero"].startswith("BAP-") and doc["numero"].endswith("00001"), doc["numero"])
det = post("/api/document/", {"id": did}, **H(T)).json()["data"]["document"]
check("variables remplacées (nom)", "Mbala Josué" in det["contenu"], det["contenu"])
check("matricule remplacé", "LDM-0007" in det["contenu"])
check("version 1 enregistrée", det["versions"][0]["version"] == 1)
check("titre par défaut du modèle", doc["titre"] == "Baptême standard", doc["titre"])

d2 = post("/api/document/generer/", {"type": "certificat_bapteme", "modele_id": mid, "membre_id": m.id}, **H(T)).json()
check("deuxième numéro incrémenté", d2["data"]["document"]["numero"].endswith("00002"), d2["data"]["document"]["numero"])

print("── Réédition et historique")
d = post("/api/document/reediter/", {"id": did, "contenu": "Contenu corrigé après vérification.",
        "motif": "Correction du nom"}, **H(T)).json()
check("réédition en version 2", d["data"]["document"]["version"] == 2, d["data"])
det = post("/api/document/", {"id": did}, **H(T)).json()["data"]["document"]
check("historique à deux versions", len(det["versions"]) == 2, len(det["versions"]))
check("contenu mis à jour", "corrigé" in det["contenu"])
check("motif conservé", any(v["motif"] == "Correction du nom" for v in det["versions"]))

print("── Statuts, PDF, vérification publique")
check("validation réservée au droit de validation", post("/api/document/statut/", {"id": did, "statut": "valide"}, **H(TL)).status_code == 403)
d = post("/api/document/statut/", {"id": did, "statut": "valide"}, **H(T)).json()
check("document validé", d["data"]["document"]["statut"] == "valide")
r = c.get(f"/api/document/pdf/?id={did}", **H(T))
check("PDF généré", r.status_code == 200 and r["Content-Type"] == "application/pdf" and r.content[:4] == b"%PDF", r.status_code)
check("PDF non vide", len(r.content) > 1500, len(r.content))
check("statut inconnu refusé", post("/api/document/statut/", {"id": did, "statut": "perdu"}, **H(T)).status_code == 400)

d = post("/api/document/verifier/", {"numero": doc["numero"]}, **H(TL)).json()
check("vérification d'authenticité", d["data"]["trouve"] is True and d["data"]["eglise"] == "Église Documents", d)
check("numéro inconnu non trouvé", post("/api/document/verifier/", {"numero": "BAP-2026-99999"}, **H(TL)).json()["data"]["trouve"] is False)
check("vérification sans numéro refusée", post("/api/document/verifier/", {}, **H(TL)).status_code == 400)

print("── Expiration, recherche, export, isolation")
proche = (date.today() + timedelta(days=10)).isoformat()
d = post("/api/document/generer/", {"type": "attestation_formation", "membre_id": m.id,
        "titre": "Formation leadership", "date_expiration": proche}, **H(T)).json()
check("document avec expiration", d["data"]["document"]["expire_bientot"] is True, d["data"]["document"])
bord = post("/api/documents/bord/", {}, **H(T)).json()["data"]
check("tableau de bord documents", bord["total"] >= 2 and bord["expirant_30j"] >= 1, bord)
check("recherche par numéro", post("/api/documents/", {"q": doc["numero"]}, **H(T)).json()["data"]["total"] == 1)
check("recherche par nom de membre", post("/api/documents/", {"q": "Mbala"}, **H(T)).json()["data"]["total"] >= 2)
check("filtre expirant", post("/api/documents/", {"expirant": True}, **H(T)).json()["data"]["total"] >= 1)
r = post("/api/documents/export/", {}, **H(T))
check("export CSV", r.status_code == 200 and b"BAP-" in r.content)
check("Église B ne voit rien", post("/api/documents/", {}, **H(TB)).json()["data"]["total"] == 0)
check("Église B ne peut pas rééditer", post("/api/document/reediter/", {"id": did}, **H(TB)).status_code == 404)
check("lecteur ne génère pas", post("/api/document/generer/", {"type": "pv", "titre": "X"}, **H(TL)).status_code == 403)
check("sans jeton refusé", post("/api/documents/", {}).status_code == 401)

print("\n" + "=" * 54)
n_ok = sum(1 for _, v in res if v)
print(f"{n_ok}/{len(res)} tests réussis")
for n, v in res:
    if not v: print("  -", n)
