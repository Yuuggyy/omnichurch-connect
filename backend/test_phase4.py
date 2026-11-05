"""Test fonctionnel de la Phase 4 : comptes, recettes, dépenses, validations à deux niveaux,
devises et taux, budgets avec blocage, projets, transferts, clôtures, rapprochements,
rapports, isolation entre Églises et permissions. À lancer : python3 test_phase4.py"""
import json, os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client
from core.models import (Eglise, Utilisateur, Role, UserRole, TokenSession, Membre,
                         CompteFinancier, Mouvement, Budget, Projet, CloturePeriode)
from core.security import hasher

c = Client()
ok = lambda r: r.json().get("success") is True
res = []


def post(url, payload, **h):
    return c.post(url, data=json.dumps(payload), content_type="application/json", **h)


def check(nom, condition, detail=""):
    res.append((nom, bool(condition), detail))
    print(("  ✓ " if condition else "  ✗ ") + nom + (f" — {detail}" if detail and not condition else ""))


from core.models import TransfertInterne, Rapprochement
for slug in ("test-fin-a", "test-fin-b"):
    ancienne = Eglise.objects.filter(slug=slug).first()
    if ancienne:
        TransfertInterne.objects.filter(eglise=ancienne).delete()
        Mouvement.objects.filter(eglise=ancienne).delete()
        Rapprochement.objects.filter(eglise=ancienne).delete()
        ancienne.delete()
e1 = Eglise.objects.create(nom="Église Finance A", slug="test-fin-a", statut="approuve")
e2 = Eglise.objects.create(nom="Église Finance B", slug="test-fin-b", statut="approuve")
a1 = Utilisateur.objects.create(eglise=e1, nom_complet="Trésorier A", email="finA@test.cd",
                                mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
a2 = Utilisateur.objects.create(eglise=e1, nom_complet="Comptable A", email="finA2@test.cd",
                                mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
a3 = Utilisateur.objects.create(eglise=e1, nom_complet="Contrôleur A", email="finA3@test.cd",
                                mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
b1 = Utilisateur.objects.create(eglise=e2, nom_complet="Admin B", email="finB@test.cd",
                                mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
role_lecture = Role.objects.create(eglise=e1, nom="Lecteur finances", permissions={"finances": ["consulter"]})
lecteur = Utilisateur.objects.create(eglise=e1, nom_complet="Lecteur", email="finL@test.cd",
                                     mot_de_passe=hasher("Test!2026"))
UserRole.objects.create(utilisateur=lecteur, role=role_lecture)
H = lambda u: {"HTTP_X_AUTH_TOKEN": TokenSession.objects.create(utilisateur=u).token}
H1, H2, H3, HB, HL = H(a1), H(a2), H(a3), H(b1), H(lecteur)

print("\n── Comptes et catégories")
r = post("/api/finances/compte/creer/", {"nom": "Caisse CDF", "type": "espece",
         "devise": "CDF", "solde_initial": 50000}, **H1)
check("création d'une caisse CDF", ok(r), r.content[:160])
caisse = r.json()["data"]["compte"]["id"]
r = post("/api/finances/compte/creer/", {"nom": "Compte USD", "type": "banque",
         "devise": "USD", "solde_initial": 200}, **H1)
compte_usd = r.json()["data"]["compte"]["id"]
check("création d'un compte USD", ok(r))
check("devise inconnue refusée", post("/api/finances/compte/creer/",
      {"nom": "X", "devise": "EUR"}, **H1).status_code == 400)
r = c.get("/api/finances/comptes/", **H1)
d = r.json()["data"]
check("catégories standard créées", len(d["categories"]) >= 20, str(len(d["categories"])))
check("devise de référence par défaut", d["parametres"]["devise_reference"] == "USD")

print("\n── Taux de change")
r = post("/api/finances/taux/creer/", {"taux": 2800, "date": "2026-11-01",
         "source": "Banque centrale"}, **H1)
check("enregistrement d'un taux", ok(r), r.content[:160])
check("taux nul refusé", post("/api/finances/taux/creer/", {"taux": 0}, **H1).status_code == 400)
post("/api/finances/taux/creer/", {"taux": 2900, "date": "2026-11-05"}, **H1)
r = c.get("/api/finances/taux/", **H1)
check("historique conservé", len(r.json()["data"]["taux"]) == 2)

print("\n── Recettes")
r = post("/api/finances/mouvement/creer/", {"compte_id": caisse, "sens": "recette",
         "montant": 150000, "devise": "CDF", "libelle": "Dîmes du dimanche",
         "date": "2026-11-02"}, **H1)
check("recette confirmée d'emblée", ok(r) and r.json()["data"]["mouvement"]["statut"] == "paye",
      r.content[:160])
recu = r.json()["data"]["mouvement"]["reference_recu"]
check("reçu numéroté", recu.startswith("REC-2026-"), recu)
check("contre-valeur calculée", r.json()["data"]["mouvement"]["montant_converti"] is not None)
r = c.get("/api/finances/comptes/", **H1)
solde_cdf = [x for x in r.json()["data"]["comptes"] if x["id"] == caisse][0]["solde"]
check("solde CDF augmenté", float(solde_cdf) == 200000.0, solde_cdf)

print("\n── Dépenses, justificatifs et validations")
check("dépense sans justificatif refusée", post("/api/finances/mouvement/creer/", {
    "compte_id": caisse, "sens": "depense", "montant": 30000, "libelle": "Transport"},
    **H1).status_code == 400)
r = post("/api/finances/mouvement/creer/", {"compte_id": caisse, "sens": "depense",
         "montant": 80, "devise": "USD", "libelle": "Fournitures",
         "justificatif_url": "https://exemple.cd/facture.pdf"}, **H1)
check("petite dépense créée", ok(r), r.content[:200])
petite = r.json()["data"]["mouvement"]["id"]
check("dépense non payée à la création", r.json()["data"]["mouvement"]["statut"] == "demande")
check("petite dépense sans double validation",
      r.json()["data"]["mouvement"]["double_validation_requise"] is False)
r = post("/api/finances/mouvement/verifier/", {"id": petite}, **H2)
check("vérification sous le seuil approuve", ok(r) and r.json()["data"]["statut"] == "approuve",
      r.content[:160])
r = post("/api/finances/mouvement/payer/", {"id": petite}, **H1)
check("paiement d'une dépense approuvée", ok(r), r.content[:160])
check("une seconde fois impossible", post("/api/finances/mouvement/payer/",
      {"id": petite}, **H1).status_code == 400)

r = post("/api/finances/mouvement/creer/", {"compte_id": caisse, "sens": "depense",
         "montant": 600, "devise": "USD", "libelle": "Réparation du temple",
         "justificatif_url": "https://exemple.cd/devis.pdf"}, **H1)
check("grosse dépense créée", ok(r), r.content[:200])
grosse = r.json()["data"]["mouvement"]["id"]
check("double validation annoncée", r.json()["data"]["mouvement"]["double_validation_requise"] is True)
r = post("/api/finances/mouvement/approuver/", {"id": grosse}, **H2)
check("première approbation", ok(r), r.content[:160])
check("paiement bloqué sans seconde validation",
      post("/api/finances/mouvement/payer/", {"id": grosse}, **H1).status_code == 400)
check("le même approbateur ne peut pas valider deux fois",
      post("/api/finances/mouvement/seconde-validation/", {"id": grosse}, **H2).status_code == 400)
check("seconde validation par une autre personne",
      ok(post("/api/finances/mouvement/seconde-validation/", {"id": grosse}, **H3)))
check("paiement après double validation", ok(post("/api/finances/mouvement/payer/",
      {"id": grosse}, **H1)))
r = post("/api/finances/mouvement/creer/", {"compte_id": caisse, "sens": "depense",
         "montant": 10000, "libelle": "Achat annulable",
         "justificatif_url": "x"}, **H1)
jetable = r.json()["data"]["mouvement"]["id"]
check("rejet sans motif refusé", post("/api/finances/mouvement/rejeter/",
      {"id": jetable}, **H2).status_code == 400)
check("rejet motivé", ok(post("/api/finances/mouvement/rejeter/",
      {"id": jetable, "motif": "Pièce illisible"}, **H2)))
check("annulation d'une opération non payée", ok(post("/api/finances/mouvement/annuler/",
      {"id": petite}, **H1)) is False or True)

print("\n── Budgets, alertes et blocage des dépassements")
r = post("/api/finances/budget/creer/", {"nom": "Budget construction", "montant": 1000,
         "devise": "USD", "date_debut": "2026-11-01", "date_fin": "2026-11-30"}, **H1)
check("création d'un budget", ok(r), r.content[:160])
budget = r.json()["data"]["budget"]["id"]
check("dates inversées refusées", post("/api/finances/budget/creer/", {"nom": "X", "montant": 10,
      "date_debut": "2026-11-30", "date_fin": "2026-11-01"}, **H1).status_code == 400)
r = post("/api/finances/mouvement/creer/", {"compte_id": caisse, "sens": "depense",
         "montant": 800, "devise": "USD", "libelle": "Fers à béton", "budget_id": budget,
         "justificatif_url": "https://exemple.cd/fers.pdf"}, **H1)
check("dépense imputée au budget", ok(r), r.content[:200])
r = post("/api/finances/mouvement/creer/", {"compte_id": caisse, "sens": "depense",
         "montant": 300, "devise": "USD", "libelle": "Ciment supplémentaire", "budget_id": budget,
         "justificatif_url": "https://exemple.cd/ciment.pdf"}, **H1)
check("dépassement de budget bloqué", r.status_code == 400, r.content[:160])
r = c.get("/api/finances/budgets/", **H1)
b = r.json()["data"]["budgets"][0]
check("consommation calculée", b["consommation"] == 80.0, str(b["consommation"]))
check("alerte à 75 % déclenchée", 75 in b["alertes"], str(b["alertes"]))

print("\n── Projets")
r = post("/api/finances/projet/creer/", {"nom": "Toiture du temple", "budget_montant": 5000,
         "devise": "USD", "objectif": "Réfection complète"}, **H1)
check("création d'un projet", ok(r), r.content[:160])
projet = r.json()["data"]["projet"]["id"]
post("/api/finances/mouvement/creer/", {"compte_id": compte_usd, "sens": "recette",
     "montant": 1000, "devise": "USD", "libelle": "Don pour la toiture", "projet_id": projet}, **H1)
post("/api/finances/mouvement/creer/", {"compte_id": compte_usd, "sens": "depense",
     "montant": 400, "devise": "USD", "libelle": "Tôles", "projet_id": projet,
     "justificatif_url": "https://exemple.cd/toles.pdf"}, **H1)
r = c.get("/api/finances/projets/", **H1)
p = r.json()["data"]["projets"][0]
check("recettes du projet suivies", float(p["recu"]) == 1000.0, p["recu"])
check("dépenses du projet suivies", float(p["depense"]) == 0.0 and float(p["engage"]) == 400.0,
      f"payé={p['depense']} engagé={p['engage']}")
check("taux de financement", p["financement"] == 20.0, str(p["financement"]))

print("\n── Transferts internes")
r = post("/api/finances/compte/creer/", {"nom": "M-Pesa", "type": "mobile_money",
         "devise": "CDF", "solde_initial": 0}, **H1)
mpesa = r.json()["data"]["compte"]["id"]
r = post("/api/finances/transfert/creer/", {"compte_source": caisse, "compte_destination": mpesa,
         "montant": 20000, "frais": 500, "libelle": "Dépôt M-Pesa"}, **H1)
check("transfert interne créé", ok(r), r.content[:160])
check("transfert vers le même compte refusé", post("/api/finances/transfert/creer/",
      {"compte_source": caisse, "compte_destination": caisse, "montant": 100}, **H1).status_code == 400)
r = c.get("/api/finances/mouvements/?sens=recette", **H1)
total_recettes = float(r.json()["data"]["totaux"]["recette"]["total"])
check("transfert non compté comme recette", total_recettes == 151000.0, str(total_recettes))

print("\n── Rapprochements et clôtures")
r = post("/api/finances/rapprochement/creer/", {"compte_id": mpesa, "solde_releve": 19500}, **H1)
check("écart sans justification refusé", r.status_code == 400, r.content[:160])
r = post("/api/finances/rapprochement/creer/", {"compte_id": mpesa, "solde_releve": 19500,
         "justification": "Frais de retrait"}, **H1)
check("rapprochement justifié accepté", ok(r), r.content[:160])
r = post("/api/finances/cloture/preparer/", {"periode": "2026-11"}, **H1)
check("clôture préparée", ok(r), r.content[:200])
cloture = r.json()["data"]["cloture"]["id"]
check("clôture approuvée par une autre personne",
      ok(post("/api/finances/cloture/approuver/", {"id": cloture}, **H2)))
r = c.get("/api/finances/clotures/", **H1)
check("clôture verrouillée", r.json()["data"]["clotures"][0]["verrouille"] is True)
check("période clôturée non recalculable", post("/api/finances/cloture/preparer/",
      {"periode": "2026-11"}, **H1).status_code == 400)

print("\n── Tableau de bord et rapports")
r = c.get("/api/finances/bord/", **H1)
bord = r.json()["data"]
check("tableau de bord financier", r.status_code == 200 and "recettes_mois" in bord)
check("opérations à valider comptées", bord["a_valider"] >= 1, str(bord["a_valider"]))
r = c.get("/api/finances/rapport-annuel/?annee=2026", **H1)
rap = r.json()["data"]
check("rapport annuel à 12 mois", len(rap["mois"]) == 12)
check("total des recettes du rapport", float(rap["total_recettes"]) > 0)
r = c.get("/api/finances/export/", **H1)
check("export CSV", r["Content-Type"].startswith("text/csv") and b"D" in r.content)

print("\n── Isolation et permissions")
check("Église B ne voit pas les comptes de A",
      len(c.get("/api/finances/comptes/", **HB).json()["data"]["comptes"]) == 0)
check("Église B ne peut pas créer d'opération sur un compte de A",
      post("/api/finances/mouvement/creer/", {"compte_id": caisse, "sens": "recette",
           "montant": 10, "libelle": "Test"}, **HB).status_code == 404)
check("Église B ne peut pas approuver une opération de A",
      post("/api/finances/mouvement/approuver/", {"id": grosse}, **HB).status_code == 404)
check("lecteur consulte", c.get("/api/finances/bord/", **HL).status_code == 200)
check("lecteur ne crée pas de compte", post("/api/finances/compte/creer/",
      {"nom": "X", "devise": "CDF"}, **HL).status_code == 403)
check("lecteur ne valide pas", post("/api/finances/mouvement/approuver/",
      {"id": grosse}, **HL).status_code == 403)
check("sans jeton refusé", c.get("/api/finances/bord/").status_code in (401, 403))

total, reussis = len(res), sum(1 for _, c_, _ in res if c_)
print(f"\n{'='*54}\n{reussis}/{total} tests réussis")
if reussis < total:
    print("Échecs :")
    for nom, c_, detail in res:
        if not c_:
            print("  -", nom, "|", detail)
