"""Injecte un jeu de données de démonstration réaliste dans l'Église Lumière du Monde.
Idempotent : efface les données de démonstration de cette Église avant de les recréer.
N'efface jamais les utilisateurs, les rôles ni les paramètres de l'Église.
"""
import os, random, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from datetime import date, timedelta, datetime
from decimal import Decimal
from django.utils import timezone
from core.models import (Eglise, Utilisateur, Membre, ParametreMatricule, EffectifDeclare, Groupe,
                         MembreGroupe, Evenement, EvenementInscription, Presence, CompteFinancier,
                         CategorieOperation, TauxChange, Projet, Budget, Mouvement, TransfertInterne,
                         BienPatrimoine, MouvementBien, DossierPastoral, ActionPastorale,
                         DemandePriere, Enfant, PersonneAutorisee, ClasseEnfants, InscriptionEnfant,
                         PresenceEnfant, IncidentEnfant, LeconEnfants, ProgressionEnfant,
                         Intervenant, DisponibiliteIntervenant, InvitationIntervenant, Media,
                         ModeleDocument, Document, DocumentVersion)
random.seed(20261105)

e = Eglise.objects.get(slug="lumiere-du-monde")
admin = Utilisateur.objects.get(email="admin@lumieredumonde.cd")
AJD = date.today()

# ─── 1. Nettoyage des données de démonstration ───
A_SUPPRIMER = [
    DocumentVersion.objects.filter(document__eglise=e),
    Document.objects.filter(eglise=e), ModeleDocument.objects.filter(eglise=e),
    Media.objects.filter(eglise=e),
    InvitationIntervenant.objects.filter(eglise=e),
    DisponibiliteIntervenant.objects.filter(intervenant__eglise=e),
    Intervenant.objects.filter(eglise=e),
    ProgressionEnfant.objects.filter(eglise=e), LeconEnfants.objects.filter(eglise=e),
    IncidentEnfant.objects.filter(eglise=e), PresenceEnfant.objects.filter(eglise=e),
    InscriptionEnfant.objects.filter(eglise=e),
    PersonneAutorisee.objects.filter(enfant__eglise=e),
    Enfant.objects.filter(eglise=e), ClasseEnfants.objects.filter(eglise=e),
    DemandePriere.objects.filter(eglise=e),
    ActionPastorale.objects.filter(dossier__eglise=e), DossierPastoral.objects.filter(eglise=e),
    MouvementBien.objects.filter(eglise=e), BienPatrimoine.objects.filter(eglise=e),
    TransfertInterne.objects.filter(eglise=e), Mouvement.objects.filter(eglise=e),
    Budget.objects.filter(eglise=e), Projet.objects.filter(eglise=e),
    TauxChange.objects.filter(eglise=e), CategorieOperation.objects.filter(eglise=e),
    CompteFinancier.objects.filter(eglise=e),
    Presence.objects.filter(eglise=e), EvenementInscription.objects.filter(eglise=e),
    Evenement.objects.filter(eglise=e),
    MembreGroupe.objects.filter(groupe__eglise=e), Groupe.objects.filter(eglise=e),
    EffectifDeclare.objects.filter(eglise=e), Membre.objects.filter(eglise=e),
]
for q in A_SUPPRIMER:
    q.delete()

# ─── 2. Membres ───
NOMS = ["Kabeya", "Mbuyi", "Ilunga", "Nsimba", "Mbala", "Kanku", "Tshibangu", "Mutombo", "Lukusa",
        "Kasongo", "Bemba", "Nkulu", "Mabiala", "Ngoma", "Bosenge", "Kalala", "Mputu", "Tshiala",
        "Mbombo", "Kasaï", "Ntumba", "Bakala", "Mukendi", "Kayembe", "Nzuzi", "Lumbala", "Mwamba",
        "Ndaya", "Kalonji", "Bope", "Lokombe", "Mpiana", "Kapinga", "Ngalula", "Tshimanga"]
PRENOMS_H = ["Jean", "Patrick", "Emmanuel", "Didier", "Serge", "Blaise", "Josué", "Fabrice",
             "Christian", "Landry", "Bienvenu", "Gédéon", "Michel", "Éric", "Franck", "Olivier"]
PRENOMS_F = ["Marie", "Grâce", "Esther", "Béatrice", "Nadine", "Clarisse", "Rachel", "Sylvie",
             "Chantal", "Fifi", "Divine", "Bénédicte", "Joséphine", "Léonie", "Gloria", "Prisca"]
POSTNOMS = ["Wa Mukala", "Mbuyi", "Kabasele", "Tshilombo", "Nkashama", "Muleka", "Kazadi",
            "Mutombo", "Kasongo", "Beya", "Nsimba", "Lukoki"]
PROFS = ["Enseignante", "Commerçante", "Infirmière", "Chauffeur", "Comptable", "Menuisier",
         "Étudiante", "Étudiant", "Fonctionnaire", "Couturière", "Mécanicien", "Agent commercial",
         "Médecin", "Juriste", "Sans emploi", "Petit commerce"]
QUARTIERS = ["Gombe", "Limete", "Kintambo", "Ngaliema", "Bandal", "Matonge", "Kalamu",
             "Lemba", "Masina", "Ndjili", "Kisenso", "Selembao", "Mont-Ngafula", "Lingwala"]
ADRESSES = ["Avenue Kasa-Vubu", "Avenue Lumumba", "Boulevard du 30 Juin", "Avenue de la Libération",
            "Avenue Kimbangu", "Rue Kasavubu", "Avenue des Huileries", "Avenue Bongolo",
            "Avenue Kianza", "Rue Pumbu", "Avenue Nguma", "Avenue Mokali"]
ETAT_CIVIL = ["Célibataire", "Marié(e)", "Veuf(ve)", "Divorcé(e)"]

pm = ParametreMatricule.objects.filter(eglise=e).first()
if not pm:
    pm = ParametreMatricule.objects.create(eglise=e, prefixe="ELM", inclure_annee=True,
                                           chiffres=4, separateur="-", compteur=0)

membres = []
for i in range(1, 121):
    masculin = random.random() < 0.46
    nom = random.choice(NOMS)
    prenom = random.choice(PRENOMS_H if masculin else PRENOMS_F)
    if random.random() < 0.55:
        statut = "actif"
    else:
        statut = random.choice(["actif", "actif", "nouveau", "integration", "visiteur",
                                "transfere", "suspendu"])
    adhesion = AJD - timedelta(days=random.randint(30, 3600))
    m = Membre.objects.create(
        eglise=e, nom=nom, postnom=random.choice(POSTNOMS), prenom=prenom,
        sexe="M" if masculin else "F",
        date_naissance=date(random.randint(1955, 2008), random.randint(1, 12), random.randint(1, 28)),
        lieu_naissance=random.choice(["Kinshasa", "Matadi", "Kananga", "Lubumbashi",
                                      "Mbuji-Mayi", "Kikwit", "Kisangani"]),
        profession=random.choice(PROFS), etat_civil=random.choice(ETAT_CIVIL),
        telephone=f"+2439{random.randint(10000000, 99999999)}",
        email=f"{prenom.lower().replace('é','e')}.{nom.lower()}@gmail.com" if random.random() < 0.45 else "",
        adresse=f"{random.randint(1, 240)} {random.choice(ADRESSES)}, {random.choice(QUARTIERS)}",
        contact_urgence=random.choice(PRENOMS_F + PRENOMS_H) + " " + random.choice(NOMS) + f" · +2438{random.randint(10000000, 99999999)}",
        date_adhesion=adhesion,
        statut=statut,
    )
    membres.append(m)

# matricules et états de validation
for m in membres:
    pm.compteur += 1
    m.matricule = f"{pm.prefixe}-{AJD.year}-{pm.compteur:0{pm.chiffres}d}"
    r = random.random()
    if r < 0.78:
        m.etat_validation = "valide"; m.valide_le = timezone.now(); m.valide_par = admin
    elif r < 0.90:
        m.etat_validation = "a_valider"
    elif r < 0.96:
        m.etat_validation = "brouillon"
    else:
        m.etat_validation = "retourne"; m.motif_rejet = "Pièce d'identité illisible, à représenter."
    m.cree_par = admin
    m.save()
pm.save()

# quelques anciens pour la crédibilité
EffectifDeclare.objects.bulk_create([
    EffectifDeclare(eglise=e, categorie="adultes", valeur=310, periode="Octobre 2026",
                    observation="Recensement du culte de clôture du mois", auteur=admin),
    EffectifDeclare(eglise=e, categorie="jeunes", valeur=145, periode="Octobre 2026", auteur=admin),
    EffectifDeclare(eglise=e, categorie="enfants", valeur=95, periode="Octobre 2026", auteur=admin),
    EffectifDeclare(eglise=e, categorie="invites", valeur=40, periode="Octobre 2026", auteur=admin),
])

# ─── 3. Groupes ───
GROUPES = [
    ("Chorale Bethel", "ministère", "Chorale principale du culte du dimanche"),
    ("Département de la jeunesse", "département", "Jeunes de 15 à 30 ans"),
    ("Dames de valeur", "département", "Femmes de l'Église, actions sociales"),
    ("Hommes de courage", "département", "Hommes, construction et logistique"),
    ("École du dimanche", "département", "Enfants de 3 à 14 ans"),
    ("Équipe d'intercession", "ministère", "Prière quotidienne et veillées"),
    ("Diaconat", "service", "Accueil, protocole et assistance"),
    ("Cellule Gombe", "cellule", "Cellule de maison, quartier Gombe"),
    ("Cellule Limete", "cellule", "Cellule de maison, quartier Limete"),
    ("Média et sonorisation", "service", "Son, captation et diffusion"),
]
groupes = []
for nom, type_g, desc in GROUPES:
    groupes.append(Groupe.objects.create(eglise=e, nom=nom, type=type_g, description=desc))

for i, g in enumerate(groupes):
    g.responsable = membres[i * 3]
    g.save()
    for m in random.sample(membres, random.randint(9, 26)):
        try:
            MembreGroupe.objects.create(membre=m, groupe=g,
                                        fonction="responsable" if m == g.responsable else "membre",
                                        date_debut=m.date_adhesion)
        except Exception:
            pass

# ─── 4. Calendrier et présences ───
cultes = []
for sem in range(5, 0, -1):
    d = AJD - timedelta(days=AJD.weekday() + 7 * (sem - 1))
    cultes.append(Evenement.objects.create(
        eglise=e, titre="Culte de célébration", type="culte", date=d, heure="09:00",
        heure_fin="11:30", lieu="Temple principal", statut="termine", recurrence="hebdomadaire",
        cree_par=admin))

for sem in range(1, 5):
    d = AJD + timedelta(days=(6 - AJD.weekday()) + 7 * (sem - 1))
    Evenement.objects.create(eglise=e, titre="Culte de célébration", type="culte", date=d,
                             heure="09:00", heure_fin="11:30", lieu="Temple principal",
                             statut="confirme", recurrence="hebdomadaire",
                             cree_par=admin)

Evenement.objects.create(eglise=e, titre="Veillée de prière", type="veillee",
                         date=AJD + timedelta(days=3), heure="22:00", heure_fin="05:00",
                         lieu="Temple principal", statut="confirme", recurrence="mensuelle",
                         description="Veillée d'intercession pour la nation et les familles.",
                         cree_par=admin)
Evenement.objects.create(eglise=e, titre="Réunion du conseil pastoral", type="reunion",
                         date=AJD + timedelta(days=2), heure="18:00", heure_fin="20:00",
                         lieu="Salle annexe", statut="confirme", groupe=groupes[6],
                         capacite=20, cree_par=admin)
Evenement.objects.create(eglise=e, titre="Formation des responsables de cellule",
                         type="formation", date=AJD + timedelta(days=9), heure="16:00",
                         heure_fin="18:30", lieu="Salle annexe", statut="planifie",
                         capacite=40, cree_par=admin)
Evenement.objects.create(eglise=e, titre="Concert de la chorale Bethel", type="autre",
                         date=AJD + timedelta(days=16), heure="17:00", heure_fin="20:00",
                         lieu="Temple principal", statut="planifie", capacite=400,
                         groupe=groupes[0], cree_par=admin)
Evenement.objects.create(eglise=e, titre="Action sociale — visite de l'hôpital", type="autre",
                         date=AJD + timedelta(days=6), heure="14:00", heure_fin="17:00",
                         lieu="Hôpital Général de Référence", statut="confirme",
                         groupe=groupes[2], cree_par=admin)

for c in cultes:
    presents = random.sample(membres, random.randint(78, 104))
    for m in presents:
        Presence.objects.create(eglise=e, evenement=c, membre=m, statut=random.choice(
            ["present", "present", "present", "present", "retard"]), pointe_par=admin)

# ─── 5. Finances ───
comptes = [
    CompteFinancier.objects.create(eglise=e, nom="Caisse générale (espèces)", type="espece",
                                   devise="CDF", solde_initial=Decimal("1250000"),
                                   responsable=admin),
    CompteFinancier.objects.create(eglise=e, nom="Compte bancaire RawBank", type="banque",
                                   devise="USD", solde_initial=Decimal("4200"),
                                   responsable=admin),
    CompteFinancier.objects.create(eglise=e, nom="Mobile Money Airtel", type="mobile_money",
                                   devise="CDF", solde_initial=Decimal("340000"),
                                   responsable=admin),
    CompteFinancier.objects.create(eglise=e, nom="Caisse construction", type="espece",
                                   devise="USD", solde_initial=Decimal("8600"),
                                   responsable=admin),
]

CAT_R = ["Dîmes", "Offrandes", "Offrande spéciale", "Dons de projet", "Location de salle",
         "Recettes d'événement", "Vente d'ouvrages"]
CAT_D = ["Carburant et transport", "Électricité et eau", "Loyer du terrain", "Entretien du temple",
         "Matériel de sonorisation", "Aide sociale aux familles", "Indemnités des intervenants",
         "Fournitures et papeterie", "Communication et internet", "Restauration des activités"]
cat_r = [CategorieOperation.objects.create(eglise=e, nom=n, sens="recette", systeme=n in ("Dîmes", "Offrandes"))
         for n in CAT_R]
cat_d = [CategorieOperation.objects.create(eglise=e, nom=n, sens="depense") for n in CAT_D]

TauxChange.objects.create(eglise=e, devise_source="USD", devise_cible="CDF",
                          taux=Decimal("2800"), date=AJD - timedelta(days=30),
                          source="Marché de Kintambo", saisi_par=admin)
TauxChange.objects.create(eglise=e, devise_source="USD", devise_cible="CDF",
                          taux=Decimal("2840"), date=AJD, source="Marché de Kintambo",
                          saisi_par=admin)

projet = Projet.objects.create(eglise=e, nom="Réhabilitation de la toiture du temple",
                               objectif="Remplacer la couverture et la charpente avant la saison des pluies.",
                               budget_montant=Decimal("14500"), devise="USD",
                               date_debut=AJD - timedelta(days=60),
                               date_fin=AJD + timedelta(days=120), avancement=42,
                               statut="en_cours", cree_par=admin)
projet2 = Projet.objects.create(eglise=e, nom="Acquisition d'un bus de ramassage",
                                objectif="Transport des membres des cellules éloignées.",
                                budget_montant=Decimal("28000"), devise="USD",
                                date_debut=AJD - timedelta(days=20),
                                date_fin=AJD + timedelta(days=200), avancement=18,
                                statut="en_cours", cree_par=admin)

budgets = [
    Budget.objects.create(eglise=e, nom="Fonctionnement mensuel", montant=Decimal("2200"),
                          devise="USD", date_debut=AJD.replace(day=1),
                          date_fin=(AJD.replace(day=28) + timedelta(days=5)),
                          seuils=[70, 90], groupe=groupes[6]),
    Budget.objects.create(eglise=e, nom="Toiture du temple", montant=Decimal("14500"),
                          devise="USD", date_debut=AJD - timedelta(days=60),
                          date_fin=AJD + timedelta(days=120), seuils=[50, 80, 95], projet=projet),
    Budget.objects.create(eglise=e, nom="Action sociale", montant=Decimal("800"), devise="USD",
                          date_debut=AJD - timedelta(days=30), date_fin=AJD + timedelta(days=30),
                          seuils=[70, 90], groupe=groupes[2]),
]

recus = 0
for jour in range(75, -1, -1):
    d = AJD - timedelta(days=jour)
    dimanche = d.weekday() == 6
    if dimanche:
        for cpt, devise, mont in ((comptes[0], "CDF", random.randint(380000, 720000)),
                                  (comptes[2], "CDF", random.randint(90000, 210000))):
            recus += 1
            Mouvement.objects.create(eglise=e, compte=cpt, categorie=cat_r[0], sens="recette",
                                     montant=Decimal(mont), devise=devise, date=d,
                                     libelle="Dîmes du culte dominical", collecte_globale=True,
                                     statut="paye", reference_recu=f"REC-{d.year}-{recus:05d}",
                                     cree_par=admin, paye_le=timezone.now())
            recus += 1
            Mouvement.objects.create(eglise=e, compte=cpt, categorie=cat_r[1], sens="recette",
                                     montant=Decimal(int(mont * 0.55)), devise=devise, date=d,
                                     libelle="Offrandes du culte dominical", collecte_globale=True,
                                     statut="paye", reference_recu=f"REC-{d.year}-{recus:05d}",
                                     cree_par=admin, paye_le=timezone.now())
    if jour % 9 == 0:
        recus += 1
        Mouvement.objects.create(eglise=e, compte=comptes[1], categorie=cat_r[3], sens="recette",
                                 montant=Decimal(random.choice([150, 200, 300, 500])),
                                 devise="USD", date=d, libelle="Don pour la toiture du temple",
                                 projet=projet, budget=budgets[1], statut="paye",
                                 reference_recu=f"REC-{d.year}-{recus:05d}", cree_par=admin,
                                 paye_le=timezone.now())
    if jour % 14 == 0:
        recus += 1
        Mouvement.objects.create(eglise=e, compte=comptes[1], categorie=cat_r[5], sens="recette",
                                 montant=Decimal(random.choice([250, 400, 650])), devise="USD",
                                 date=d, libelle="Location de la salle pour mariage", statut="paye",
                                 reference_recu=f"REC-{d.year}-{recus:05d}", cree_par=admin,
                                 paye_le=timezone.now())

depenses = [
    ("Carburant et transport", 0, "CDF", (60000, 140000), "Carburant du bus et déplacements pastoraux", None),
    ("Électricité et eau", 1, "USD", (90, 210), "Facture SNEL et REGIDESO", None),
    ("Entretien du temple", 0, "CDF", (45000, 180000), "Nettoyage, peinture et petites réparations", None),
    ("Aide sociale aux familles", 2, "CDF", (40000, 120000), "Assistance aux veuves et familles éprouvées", budgets[2]),
    ("Matériel de sonorisation", 1, "USD", (120, 480), "Réparation de la console et des micros", None),
    ("Indemnités des intervenants", 1, "USD", (80, 250), "Indemnité du prédicateur invité", None),
    ("Communication et internet", 2, "CDF", (25000, 60000), "Crédit téléphonique et abonnement internet", None),
    ("Fournitures et papeterie", 0, "CDF", (18000, 55000), "Papeterie du secrétariat et bulletins", None),
]
for i in range(46):
    lib, idx_cpt, devise, (lo, hi), libelle, bud = random.choice(depenses)
    d = AJD - timedelta(days=random.randint(0, 70))
    statut = random.choice(["paye", "paye", "paye", "paye", "approuve", "a_verifier", "demande"])
    mo = Mouvement(eglise=e, compte=comptes[idx_cpt], sens="depense",
                   categorie=next(c for c in cat_d if c.nom == lib),
                   montant=Decimal(random.randint(lo, hi)), devise=devise, date=d,
                   libelle=libelle, statut=statut, cree_par=admin,
                   justification="Pièce justificative déposée au secrétariat.")
    if bud:
        mo.budget = bud
    if statut in ("approuve", "paye"):
        mo.verifie_par = admin; mo.approuve_par = admin
        mo.seconde_validation_par = admin
    if statut == "paye":
        mo.paye_le = timezone.now()
    mo.save()

for i in range(14):
    recus += 1
    d = AJD - timedelta(days=random.randint(0, 70))
    Mouvement.objects.create(eglise=e, compte=comptes[1], categorie=cat_r[3], sens="recette",
                             montant=Decimal(random.choice([100, 150, 200, 250, 400])),
                             devise="USD", date=d, libelle="Don pour la toiture du temple",
                             projet=projet, budget=budgets[1], statut="paye",
                             reference_recu=f"REC-{d.year}-{recus:05d}", cree_par=admin,
                             paye_le=timezone.now())
for i in range(10):
    recus += 1
    d = AJD - timedelta(days=random.randint(0, 70))
    Mouvement.objects.create(eglise=e, compte=comptes[0], categorie=cat_r[4], sens="recette",
                             montant=Decimal(random.randint(120000, 380000)), devise="CDF", date=d,
                             libelle="Location de la salle pour formation", statut="paye",
                             reference_recu=f"REC-{d.year}-{recus:05d}", cree_par=admin,
                             paye_le=timezone.now())

TransfertInterne.objects.create(eglise=e, compte_source=comptes[1], compte_destination=comptes[2],
                                montant=Decimal("500"), devise="USD",
                                montant_recu=Decimal("1385000"),
                                frais=Decimal("6000"), date=AJD - timedelta(days=12),
                                libelle="Alimentation de la caisse mobile money", cree_par=admin)

# ─── 6. Patrimoine ───
BIENS = [
    ("Sonorisation principale", "sonorisation", 1, "1200", "USD", "Temple principal", "bon"),
    ("Console de mixage Yamaha", "sonorisation", 1, "850", "USD", "Régie", "bon"),
    ("Micros sans fil", "sonorisation", 6, "95", "USD", "Régie", "bon"),
    ("Bancs du temple", "mobilier", 180, "35", "USD", "Temple principal", "bon"),
    ("Chaises plastiques", "mobilier", 240, "8", "USD", "Dépôt", "usage"),
    ("Groupe électrogène 15 kVA", "equipement", 1, "3800", "USD", "Cour arrière", "usage"),
    ("Projecteur vidéo", "equipement", 1, "620", "USD", "Temple principal", "bon"),
    ("Ordinateur portable du secrétariat", "informatique", 2, "780", "USD", "Bureau", "bon"),
    ("Imprimante multifonction", "informatique", 1, "340", "USD", "Bureau", "usage"),
    ("Caméra de captation", "informatique", 1, "560", "USD", "Régie", "bon"),
    ("Bus de ramassage Toyota", "vehicule", 1, "16500", "USD", "Parking", "usage"),
    ("Moto de terrain", "vehicule", 2, "1450", "USD", "Parking", "entretien"),
    ("Tente de 500 places", "materiel_evenementiel", 2, "900", "USD", "Dépôt", "bon"),
    ("Bâches et nappes", "materiel_evenementiel", 40, "12", "USD", "Dépôt", "usage"),
    ("Enceinte mobile JBL", "sonorisation", 2, "320", "USD", "Dépôt", "bon"),
    ("Réfrigérateur de la cuisine", "equipement", 1, "540", "USD", "Cuisine", "usage"),
    ("Terrain annexe (titre foncier)", "terrain", 1, "32000", "USD", "Quartier Gombe", "bon"),
    ("Bibliothèque et ouvrages", "mobilier", 1, "300", "USD", "Salle annexe", "bon"),
]
biens = []
for i, (nom, cat, qte, val, dev, loc, etat) in enumerate(BIENS, start=1):
    b = BienPatrimoine.objects.create(
        eglise=e, code=f"PAT-{AJD.year}-{i:04d}", nom=nom, categorie=cat,
        description="Bien recensé au cours de l'inventaire annuel.", quantite=qte,
        date_acquisition=AJD - timedelta(days=random.randint(60, 2400)),
        valeur_achat=Decimal(val), devise=dev, localisation=loc, etat=etat,
        responsable=membres[3], cree_par=admin)
    biens.append(b)

for i in range(22):
    b = random.choice(biens)
    type_mv = random.choice(["inventaire", "affectation", "pret", "entretien", "retour", "reforme"])
    MouvementBien.objects.create(eglise=e, bien=b, type=type_mv,
                                 date=AJD - timedelta(days=random.randint(1, 400)),
                                 personne=random.choice(["Diacre Kisita", "Sœur Micheline",
                                                         "Frère Aimé", "Pasteur adjoint"]),
                                 lieu=b.localisation, cout=Decimal(random.randint(0, 120)),
                                 note="Mouvement enregistré lors du suivi du bien.",
                                 cree_par=admin)

# ─── 7. Suivi pastoral ───
DOSSIERS = [
    ("Visite de la famille Kabeya après deuil", "visite", "Veuve avec trois enfants, soutien financier et spirituel demandé.", "haute", "confidentiel", "ouvert"),
    ("Accompagnement d'un couple en difficulté", "rendez_vous", "Couple marié depuis huit ans, demande de conseil conjugal.", "haute", "confidentiel", "en_cours"),
    ("Suivi d'un jeune en décrochage scolaire", "accompagnement", "Jeune de 16 ans, retour à l'école à organiser.", "normale", "normal", "en_cours"),
    ("Visite d'un membre hospitalisé", "visite_domicile", "Hospitalisé à l'Hôpital Général, prière et visite.", "haute", "restreint", "en_cours"),
    ("Demande de baptême d'un nouveau converti", "rendez_vous", "Préparation au baptême, quatre séances prévues.", "normale", "normal", "ouvert"),
    ("Médiation familiale après conflit d'héritage", "accompagnement", "Deux frères en conflit, réunion de médiation souhaitée.", "haute", "confidentiel", "en_attente"),
    ("Suivi d'une personne en addiction", "rendez_vous", "Accompagnement et orientation vers un centre spécialisé.", "haute", "confidentiel", "en_cours"),
    ("Visite aux personnes âgées de la cellule Limete", "visite", "Trois personnes âgées isolées visitées chaque mois.", "normale", "normal", "clos"),
]
for i, (objet, type_d, nature, prio, conf, statut) in enumerate(DOSSIERS, start=1):
    m = membres[i * 7]
    doss = DossierPastoral.objects.create(
        eglise=e, numero=f"DP-{AJD.year}-{i:04d}", personne_nom=m.nom_complet, membre=m,
        telephone=m.telephone, type=type_d, objet=objet, nature_demande=nature,
        statut=statut, confidentialite=conf, priorite=prio,
        prochaine_etape="Reprendre contact dans la semaine." if statut != "clos" else "",
        echeance=AJD + timedelta(days=random.randint(3, 30)) if statut != "clos" else None,
        cree_par=admin, ouvert_le=timezone.now() - timedelta(days=random.randint(5, 90)),
        clos_le=timezone.now() if statut == "clos" else None)
    for j in range(random.randint(2, 5)):
        ActionPastorale.objects.create(
            eglise=e, dossier=doss, type=random.choice(["visite", "appel", "priere", "conseil", "rendez_vous"]),
            date=AJD - timedelta(days=random.randint(1, 60)),
            lieu=random.choice(["Domicile", "Bureau pastoral", "Temple", "Téléphone"]),
            resume="Échange et prière. La personne se dit soutenue et souhaite poursuivre l'accompagnement.",
            confidentiel=conf == "confidentiel", fait_par=admin)

SUJETS = [
    ("Rétablissement d'une mère malade", "Hospitalisée depuis une semaine, la famille demande la prière de l'Église.", "haute"),
    ("Emploi pour un jeune diplômé", "Recherche d'emploi depuis six mois, demande de soutien dans la prière.", "normale"),
    ("Réussite des examens d'État", "Élèves de la cellule Gombe en période d'examens.", "normale"),
    ("Réconciliation dans une famille", "Tension entre deux branches de la même famille.", "haute"),
    ("Ouverture du chantier de la toiture", "Prière pour les fonds et la sécurité des ouvriers.", "normale"),
    ("Voyage missionnaire au Kasaï", "Équipe de cinq personnes en préparation.", "basse"),
    ("Guérison d'un enfant", "Enfant de six ans suivi à l'hôpital.", "haute"),
    ("Actions de grâce pour un mariage", "Remerciement pour un mariage célébré au temple.", "basse"),
    ("Protection pendant la saison des pluies", "Familles des quartiers inondables.", "normale"),
    ("Soutien aux veuves de l'Église", "Neuf veuves accompagnées par le diaconat.", "normale"),
]
for i, (sujet, detail, urg) in enumerate(SUJETS):
    DemandePriere.objects.create(eglise=e, membre=membres[i * 5 + 3] if i % 2 == 0 else None,
                                 personne_nom="" if i % 2 == 0 else "Anonyme",
                                 sujet=sujet, detail=detail, urgence=urg,
                                 confidentiel=i in (0, 3, 6),
                                 statut=random.choice(["nouvelle", "en_priere", "en_priere", "exaucee"]),
                                 recue_le=timezone.now() - timedelta(days=random.randint(1, 40)),
                                 cree_par=admin)

# ─── 8. Enfants et école du dimanche ───
CLASSES = [("Petits (3-5 ans)", 3, 5, "Salle A", 25), ("Moyens (6-9 ans)", 6, 9, "Salle B", 30),
           ("Grands (10-14 ans)", 10, 14, "Salle C", 35)]
classes = [ClasseEnfants.objects.create(eglise=e, nom=n, age_min=a, age_max=b, salle=s,
                                        capacite=c, moniteur=admin,
                                        active=True) for n, a, b, s, c in CLASSES]

enfants = []
for i in range(1, 46):
    masculin = random.random() < 0.5
    nom, prenom = random.choice(NOMS), random.choice(PRENOMS_H if masculin else PRENOMS_F)
    tuteur = membres[random.randrange(len(membres))]
    age = random.randint(3, 14)
    enf = Enfant.objects.create(
        eglise=e, code=f"ENF-{AJD.year}-{i:04d}", nom=nom, postnom=random.choice(POSTNOMS),
        prenom=prenom, sexe="M" if masculin else "F",
        date_naissance=date(AJD.year - age, random.randint(1, 12), random.randint(1, 28)),
        tuteur_nom=tuteur.nom_complet, tuteur_lien=random.choice(["père", "mère", "tuteur", "oncle"]),
        tuteur_telephone=tuteur.telephone, tuteur_email=tuteur.email,
        urgence_nom=random.choice(PRENOMS_F) + " " + random.choice(NOMS),
        urgence_telephone=f"+2439{random.randint(10000000, 99999999)}",
        sante=random.choice(["Aucune allergie connue", "Asthme léger", "Allergie aux arachides", ""]),
        besoins="", autorisation_photo=random.random() < 0.8,
        autorisation_sortie=random.random() < 0.9, statut="actif")
    enfants.append(enf)
    cl = classes[0] if age <= 5 else (classes[1] if age <= 9 else classes[2])
    InscriptionEnfant.objects.create(eglise=e, enfant=enf, classe=cl,
                                     annee_scolaire="2026", date=AJD - timedelta(days=60), active=True)
    pa = PersonneAutorisee.objects.create(enfant=enf, nom=tuteur.nom_complet, lien="Parent",
                                          telephone=tuteur.telephone, piece="Carte d'identité",
                                          actif=True)
    for sem in range(1, 5):
        d = AJD - timedelta(days=AJD.weekday() + 7 * (sem - 1))
        PresenceEnfant.objects.create(eglise=e, enfant=enf, classe=cl, date=d,
                                      statut=random.choice(["present"] * 8 + ["retard", "absent"]),
                                      arrivee="09:05", depart="11:15",
                                      recupere_par=pa)

for cl in classes:
    for j in range(4):
        lec = LeconEnfants.objects.create(eglise=e, classe=cl,
                                          titre=f"Leçon {j+1} — " + random.choice([
                                              "Dieu créateur", "Le respect des parents",
                                              "La prière du matin", "Le partage", "La patience",
                                              "L'amour du prochain"]),
                                          date=AJD - timedelta(days=7 * j),
                                          objectif="Comprendre et appliquer le thème de la semaine.",
                                          activite="Récit, chanson et coloriage.")
        for enf in enfants[:24:4]:
            try:
                ProgressionEnfant.objects.create(eglise=e, enfant=enf, lecon=lec,
                                                 niveau=random.choice(["acquis", "acquis", "en_cours"]),
                                                 note="Bon niveau de participation.")
            except Exception:
                pass

IncidentEnfant.objects.create(eglise=e, enfant=enfants[4], date=AJD - timedelta(days=9),
                              type="sante", gravite="legere",
                              description="Malaise léger pendant la récréation.",
                              action="Repos et verre d'eau, parents informés.",
                              parent_informe=True, signale_par=admin)

# ─── 9. Intervenants et médiathèque ───
INTERVENANTS = [
    ("Pasteur Émile Nkashama", "pasteur", "Église Lumière du Monde", "Enseignement et formation des leaders"),
    ("Révérend Paul Mbala", "pasteur", "Assemblée de la Grâce", "Prédication et réveil"),
    ("Évangéliste Josué Kanku", "evangeliste", "Mission Congo", "Évangélisation et croisades"),
    ("Prophète Daniel Mbuyi", "prophete", "Ministère Bethel", "Intercession et délivrance"),
    ("Pastor Rachel Kapinga", "pasteur", "Dames de valeur", "Femmes et familles"),
    ("Docteur Christian Bope", "enseignant", "Faculté de théologie", "Herméneutique et théologie"),
    ("Frère Landry Mputu", "musicien", "Chorale Bethel", "Direction de louange"),
    ("Sœur Divine Lukusa", "enseignant", "École du dimanche", "Pédagogie de l'enfance"),
]
intervenants = []
for nom, type_i, org, spec in INTERVENANTS:
    intervenants.append(Intervenant.objects.create(
        eglise=e, nom=nom, type=type_i, organisation=org,
        telephone=f"+2439{random.randint(10000000, 99999999)}",
        email=nom.lower().replace(" ", ".").replace("é", "e") + "@gmail.com", ville="Kinshasa",
        specialites=spec, tarif=Decimal(random.choice([80, 120, 150, 200])), devise="USD",
        disponible=True, notes="Intervenant régulier de l'Église."))

for inv in intervenants[:5]:
    for j in range(3):
        DisponibiliteIntervenant.objects.create(intervenant=inv, date=AJD + timedelta(days=j + 3),
                                                note="Disponible pour le culte" if j else "Indisponible",
                                                disponible=j != 0)

InvitationIntervenant.objects.create(eglise=e, intervenant=intervenants[1],
                                     objet="Culte de célébration", date=AJD + timedelta(days=9),
                                     statut="confirmee", theme="La fidélité de Dieu",
                                     note="Prédication du culte principal.")
InvitationIntervenant.objects.create(eglise=e, intervenant=intervenants[3],
                                     objet="Veillée de prière", date=AJD + timedelta(days=3),
                                     statut="proposee", theme="Intercession pour la nation",
                                     note="En attente de réponse.")

MEDIAS = [
    ("La fidélité de Dieu au quotidien", "audio", "predication", "Pasteur principal", "Fidélité", "Série Fidélité", "Lamentations 3:22-23", 42),
    ("Le pardon qui libère", "audio", "predication", "Pasteur Émile Nkashama", "Pardon", "Série Fidélité", "Matthieu 18:21-22", 38),
    ("Prières du matin — semaine 45", "audio", "priere", "Équipe d'intercession", "Prière", "", "Psaume 5:3", 15),
    ("Formation des responsables de cellule", "video", "formation", "Pasteur adjoint", "Leadership", "École des leaders", "Exode 18:21", 65),
    ("Culte du dimanche — captation", "video", "predication", "Pasteur principal", "Culte", "", "Jean 15:5", 90),
    ("Chants de la chorale Bethel", "audio", "musique", "Chorale Bethel", "Louange", "Album 2026", "", 25),
    ("Enseignement : la dîme comprise", "document", "enseignement", "Pasteur principal", "Stewardship", "", "Malachie 3:10", 0),
    ("Préparation au baptême — support", "document", "enseignement", "Pasteur adjoint", "Baptême", "", "Romains 6:4", 0),
    ("Intercession pour la nation", "audio", "priere", "Prophète Daniel Mbuyi", "Intercession", "", "2 Chroniques 7:14", 32),
    ("Concert de la chorale 2025", "video", "musique", "Chorale Bethel", "Louange", "", "", 74),
    ("Le rôle du père dans la famille", "audio", "predication", "Docteur Christian Bope", "Famille", "Série Famille", "Éphésiens 6:4", 47),
    ("Témoignage : guérison et restauration", "video", "temoignage", "Sœur Micheline", "Témoignage", "", "", 12),
]
for titre, type_m, cat, interv, theme, serie, ref, duree in MEDIAS:
    Media.objects.create(eglise=e, titre=titre, type=type_m, categorie=cat,
                         intervenant=intervenants[hash(interv) % len(intervenants)],
                         date=AJD - timedelta(days=random.randint(5, 300)), theme=theme,
                         serie=serie, reference_biblique=ref, duree_minutes=duree,
                         url="https://omnichurch26.pythonanywhere.com/media/" + str(abs(hash(titre)) % 9999),
                         transcription="", licence="Usage interne", diffusion_autorisee=True,
                         public=type_m != "document", cree_par=admin)

# ─── 10. Documents et actes officiels ───
MODELES = [
    ("certificat_bapteme", "Certificat de baptême",
     "Nous certifions que {nom}, matricule {matricule}, membre de {eglise}, a été baptisé(e) par immersion au nom du Père, du Fils et du Saint-Esprit."),
    ("certificat_mariage", "Certificat de mariage",
     "Nous certifions que {nom}, matricule {matricule}, a été uni(e) par les liens sacrés du mariage devant Dieu et devant l'assemblée de {eglise}."),
    ("attestation_presence", "Attestation de présence",
     "Nous attestons que {nom}, matricule {matricule}, a participé aux activités de {eglise} pour la période concernée."),
    ("carte_membre", "Carte de membre",
     "Carte de membre de {eglise}. Titulaire : {nom}, matricule {matricule}."),
]
modeles = {}
for type_d, nom, corps in MODELES:
    modeles[type_d] = ModeleDocument.objects.create(eglise=e, nom=nom, type=type_d,
                                                    corps=corps, jours_alerte=30, actif=True)

compteurs = {}
for i in range(16):
    type_d = random.choice(list(modeles))
    compteurs[type_d] = compteurs.get(type_d, 0) + 1
    prefixe = {"certificat_bapteme": "BAP", "certificat_mariage": "MAR",
               "attestation_presence": "ATT", "carte_membre": "CAR"}[type_d]
    m = membres[random.randrange(len(membres))]
    mod = modeles[type_d]
    txt = (mod.corps.replace("{nom}", m.nom_complet).replace("{matricule}", m.matricule)
           .replace("{eglise}", e.nom))
    Document.objects.create(
        eglise=e, numero=f"{prefixe}-{AJD.year}-{compteurs[type_d]:05d}", type=type_d,
        modele=mod, membre=m, titre=f"{mod.nom} — {m.nom_complet}", contenu=txt, version=1,
        statut=random.choice(["valide", "valide", "brouillon"]),
        date_emission=AJD - timedelta(days=random.randint(1, 300)),
        date_expiration=None if type_d in ("certificat_bapteme", "certificat_mariage") else AJD + timedelta(days=random.randint(20, 500)),
        auteur=admin)

# ─── Contre-valeurs en devise de référence (USD) pour les totaux ───
TAUX = Decimal("2840")
maj = []
for mo in Mouvement.objects.filter(eglise=e):
    if mo.montant_converti is None:
        if mo.devise == "USD":
            mo.taux = Decimal("1"); mo.montant_converti = mo.montant
        else:
            mo.taux = TAUX; mo.montant_converti = (mo.montant / TAUX).quantize(Decimal("0.01"))
        maj.append(mo)
Mouvement.objects.bulk_update(maj, ["taux", "montant_converti"])

# ─── Résumé ───
def compte(M):
    return M.objects.filter(eglise=e).count()

print("Données de démonstration injectées dans", e.nom)
for libelle, M in [("Membres", Membre), ("Groupes", Groupe), ("Événements", Evenement),
                   ("Présences", Presence), ("Comptes financiers", CompteFinancier),
                   ("Mouvements", Mouvement), ("Budgets", Budget), ("Projets", Projet),
                   ("Biens", BienPatrimoine), ("Dossiers pastoraux", DossierPastoral),
                   ("Demandes de prière", DemandePriere), ("Enfants", Enfant),
                   ("Intervenants", Intervenant), ("Médias", Media), ("Documents", Document)]:
    print(f"  {libelle:22} {compte(M)}")
