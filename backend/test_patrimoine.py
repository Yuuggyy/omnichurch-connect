"""Test fonctionnel de la Phase 5a : patrimoine et équipements (section 18)."""
import json, os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client
from core.models import Eglise, Utilisateur, Role, UserRole, TokenSession, Membre, BienPatrimoine
from core.security import hasher

c = Client()
ok = lambda r: r.json().get("success") is True
res = []


def post(url, payload, **h):
    return c.post(url, data=json.dumps(payload), content_type="application/json", **h)


def check(nom, condition, detail=""):
    res.append((nom, bool(condition), detail))
    print(("  ✓ " if condition else "  ✗ ") + nom + (f" — {detail}" if detail and not condition else ""))


for slug in ("test-pat-a", "test-pat-b"):
    ancienne = Eglise.objects.filter(slug=slug).first()
    if ancienne:
        ancienne.delete()
e1 = Eglise.objects.create(nom="Église Patrimoine A", slug="test-pat-a", statut="approuve")
e2 = Eglise.objects.create(nom="Église Patrimoine B", slug="test-pat-b", statut="approuve")
a1 = Utilisateur.objects.create(eglise=e1, nom_complet="Intendant A", email="patA@test.cd",
                                mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
b1 = Utilisateur.objects.create(eglise=e2, nom_complet="Intendant B", email="patB@test.cd",
                                mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
role = Role.objects.create(eglise=e1, nom="Lecteur patrimoine", permissions={"patrimoine": ["consulter"]})
lecteur = Utilisateur.objects.create(eglise=e1, nom_complet="Lecteur", email="patL@test.cd",
                                     mot_de_passe=hasher("Test!2026"))
UserRole.objects.create(utilisateur=lecteur, role=role)
H1 = {"HTTP_X_AUTH_TOKEN": TokenSession.objects.create(utilisateur=a1).token}
HB = {"HTTP_X_AUTH_TOKEN": TokenSession.objects.create(utilisateur=b1).token}
HL = {"HTTP_X_AUTH_TOKEN": TokenSession.objects.create(utilisateur=lecteur).token}
membre = Membre.objects.create(eglise=e1, nom="Mbala", prenom="Joseph", matricule="PAT-0001",
                               etat_validation="valide")

print("\n── Création et validations")
r = post("/api/patrimoine/bien/creer/", {"nom": "Toyota Hiace", "categorie": "vehicule",
         "code": "VEH-001", "date_acquisition": "2023-04-10", "valeur_achat": 18000,
         "devise": "USD", "localisation": "Garage du temple", "etat": "bon"}, **H1)
check("création d'un véhicule", ok(r), r.content[:200])
vehicule = r.json()["data"]["bien"]["id"]
check("valeur totale calculée", r.json()["data"]["bien"]["valeur_totale"] == "18000.00")
check("nom obligatoire", post("/api/patrimoine/bien/creer/", {"categorie": "vehicule"}, **H1).status_code == 400)
check("catégorie inconnue refusée", post("/api/patrimoine/bien/creer/",
      {"nom": "X", "categorie": "fusee"}, **H1).status_code == 400)
check("code en double refusé", post("/api/patrimoine/bien/creer/",
      {"nom": "Autre véhicule", "code": "VEH-001"}, **H1).status_code == 400)
check("quantité nulle refusée", post("/api/patrimoine/bien/creer/",
      {"nom": "Chaise", "quantite": 0}, **H1).status_code == 400)
r = post("/api/patrimoine/bien/creer/", {"nom": "Chaise plastique", "categorie": "mobilier",
         "quantite": 120, "valeur_achat": 12, "devise": "USD", "etat": "a_reparer",
         "responsable_id": membre.id}, **H1)
check("création avec quantité", ok(r), r.content[:200])
chaises = r.json()["data"]["bien"]["id"]
check("valeur totale = unitaire × quantité", r.json()["data"]["bien"]["valeur_totale"] == "1440.00")

print("\n── Inventaire, filtres et alertes")
r = c.get("/api/patrimoine/", **H1)
d = r.json()["data"]
check("inventaire complet", d["nombre"] == 2, str(d["nombre"]))
check("total USD", d["totaux"]["USD"] == "19440.00", d["totaux"]["USD"])
check("alerte bien à réparer", d["alertes"]["a_reparer"] == 1, str(d["alertes"]["a_reparer"]))
check("alerte bien sans justificatif", d["alertes"]["sans_justificatif"] == 2)
check("filtre par catégorie", c.get("/api/patrimoine/?categorie=vehicule", **H1)
      .json()["data"]["nombre"] == 1)
check("recherche par nom", c.get("/api/patrimoine/?q=chaise", **H1).json()["data"]["nombre"] == 1)
r = c.get("/api/patrimoine/alertes/", **H1)
check("liste des biens à réparer", len(r.json()["data"]["a_reparer"]) == 1)

print("\n── Mouvements et effets sur l'état")
r = post("/api/patrimoine/bien/mouvement/", {"bien_id": chaises, "type": "reparation",
         "cout": 40, "note": "Remplacement de 12 assises", "date": "2026-11-04"}, **H1)
check("réparation enregistrée", ok(r), r.content[:200])
check("réparation remet le bien en bon état", r.json()["data"]["mouvement"]["etat_bien"] == "bon")
r = post("/api/patrimoine/bien/mouvement/", {"bien_id": vehicule, "type": "affectation",
         "personne": "Joseph Mbala", "membre_id": membre.id, "lieu": "Paroisse annexe"}, **H1)
check("affectation enregistrée", ok(r), r.content[:200])
r = c.get(f"/api/patrimoine/bien/?id={vehicule}", **H1)
check("localisation mise à jour", r.json()["data"]["bien"]["localisation"] == "Paroisse annexe")
check("historique des mouvements", len(r.json()["data"]["bien"]["mouvements"]) == 1)
check("type inconnu refusé", post("/api/patrimoine/bien/mouvement/", {"bien_id": vehicule,
      "type": "teleportation"}, **H1).status_code == 400)
r = post("/api/patrimoine/bien/mouvement/", {"bien_id": vehicule, "type": "reforme",
         "note": "Hors d'usage, pièces introuvables"}, **H1)
check("réforme du véhicule", ok(r) and r.json()["data"]["mouvement"]["etat_bien"] == "reforme")
check("bien réformé n'évolue plus", post("/api/patrimoine/bien/mouvement/", {"bien_id": vehicule,
      "type": "affectation"}, **H1).status_code == 400)
r = c.get("/api/patrimoine/alertes/", **H1)
check("coût d'entretien de l'année suivi", r.json()["data"]["cout_entretien_annee"] == "40.00",
      r.json()["data"]["cout_entretien_annee"])

print("\n── Modification, export, isolation et permissions")
check("modification du bien", ok(post("/api/patrimoine/bien/modifier/", {"id": chaises,
      "observation": "Lot de 120 chaises", "justificatif_url": "https://exemple.cd/facture.pdf"}, **H1)))
check("justificatif levé de l'alerte",
      c.get("/api/patrimoine/", **H1).json()["data"]["alertes"]["sans_justificatif"] == 1)
r = c.get("/api/patrimoine/export/", **H1)
check("export d'inventaire CSV", r["Content-Type"].startswith("text/csv") and b"Toyota" in r.content)
check("Église B ne voit pas le patrimoine de A",
      c.get("/api/patrimoine/", **HB).json()["data"]["nombre"] == 0)
check("Église B ne peut pas modifier un bien de A",
      post("/api/patrimoine/bien/modifier/", {"id": chaises, "nom": "Piratage"}, **HB).status_code == 404)
check("Église B ne peut pas créer de mouvement sur un bien de A",
      post("/api/patrimoine/bien/mouvement/", {"bien_id": chaises, "type": "pret"}, **HB).status_code == 404)
check("lecteur consulte", c.get("/api/patrimoine/", **HL).status_code == 200)
check("lecteur ne crée pas", post("/api/patrimoine/bien/creer/", {"nom": "X"}, **HL).status_code == 403)
check("lecteur n'exporte pas", c.get("/api/patrimoine/export/", **HL).status_code == 403)
check("sans jeton refusé", c.get("/api/patrimoine/").status_code in (401, 403))

total, reussis = len(res), sum(1 for _, c_, _ in res if c_)
print(f"\n{'='*54}\n{reussis}/{total} tests réussis")
if reussis < total:
    for nom, c_, detail in res:
        if not c_:
            print("  -", nom, "|", detail)
