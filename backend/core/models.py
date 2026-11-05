from django.db import models
import secrets


class Eglise(models.Model):
    """Tenant : chaque Église est strictement isolée."""
    STATUTS = [("a_completer", "À compléter"), ("approuve", "Approuvé"),
               ("refuse", "Refusé"), ("suspendu", "Suspendu")]
    nom = models.CharField(max_length=200)
    slug = models.CharField(max_length=60, unique=True)
    pays = models.CharField(max_length=100, default="RDC")
    ville = models.CharField(max_length=100, blank=True, default="")
    adresse = models.CharField(max_length=250, blank=True, default="")
    denomination = models.CharField(max_length=200, blank=True, default="")
    annee_fondation = models.IntegerField(null=True, blank=True)
    email = models.EmailField(blank=True, default="")
    telephone = models.CharField(max_length=40, blank=True, default="")
    logo_url = models.CharField(max_length=500, blank=True, default="")
    couleur_primaire = models.CharField(max_length=9, default="#16233F")
    couleur_accent = models.CharField(max_length=9, default="#C9A227")
    langue = models.CharField(max_length=2, default="fr")
    statut = models.CharField(max_length=20, choices=STATUTS, default="a_completer")
    motif = models.CharField(max_length=500, blank=True, default="")
    essai_expire_le = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nom} ({self.slug})"


class Utilisateur(models.Model):
    STATUTS = [("actif", "Actif"), ("suspendu", "Suspendu"), ("revoque", "Révoqué")]
    eglise = models.ForeignKey(Eglise, null=True, blank=True, on_delete=models.CASCADE,
                               related_name="utilisateurs")
    nom_complet = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=40, blank=True, default="")
    mot_de_passe = models.CharField(max_length=128)
    is_super_admin = models.BooleanField(default=False)
    is_admin_principal = models.BooleanField(default=False)
    statut = models.CharField(max_length=20, choices=STATUTS, default="actif")
    langue = models.CharField(max_length=2, default="fr")
    tentatives_echec = models.IntegerField(default=0)
    verrouille_jusqua = models.DateTimeField(null=True, blank=True)
    dernier_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nom_complet} <{self.email}>"


class TokenSession(models.Model):
    """Session par appareil, révocable individuellement."""
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name="sessions")
    token = models.CharField(max_length=80, unique=True, default=secrets.token_hex)
    appareil = models.CharField(max_length=250, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    expire_le = models.DateTimeField(null=True, blank=True)
    actif = models.BooleanField(default=True)

    def __str__(self):
        return f"session {self.token[:8]}… {self.utilisateur.email}"


class Role(models.Model):
    """Rôle personnalisable : permissions = {module: [actions]}."""
    eglise = models.ForeignKey(Eglise, null=True, blank=True, on_delete=models.CASCADE,
                               related_name="roles")
    nom = models.CharField(max_length=100)
    description = models.CharField(max_length=300, blank=True, default="")
    permissions = models.JSONField(default=dict)
    systeme = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nom} ({'système' if self.systeme else self.eglise})"


class UserRole(models.Model):
    """Attribution de rôle, éventuellement temporaire (date_fin)."""
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name="roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    date_debut = models.DateTimeField(auto_now_add=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    accorde_par = models.ForeignKey(Utilisateur, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="delegations")

    def __str__(self):
        return f"{self.utilisateur.email} → {self.role.nom}"


class Invitation(models.Model):
    """Invitation à usage unique, expirable."""
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    nom_complet = models.CharField(max_length=200, blank=True, default="")
    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.SET_NULL)
    token = models.CharField(max_length=80, unique=True, default=secrets.token_hex)
    expire_le = models.DateTimeField(null=True, blank=True)
    utilise_le = models.DateTimeField(null=True, blank=True)
    cree_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"invitation {self.email} ({self.eglise.slug})"


class JournalAudit(models.Model):
    """Journal d'audit des opérations sensibles — non modifiable par les utilisateurs."""
    eglise = models.ForeignKey(Eglise, null=True, blank=True, on_delete=models.CASCADE,
                               related_name="audits")
    utilisateur = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL)
    module = models.CharField(max_length=60)
    action = models.CharField(max_length=80)
    details = models.TextField(blank=True, default="")
    ip = models.CharField(max_length=60, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.module}] {self.action} — {self.utilisateur}"


# ═══════════════════════════════════════════════════════════════
# PHASE 2 — Membres, effectifs déclarés, groupes, présences
# ═══════════════════════════════════════════════════════════════

class Membre(models.Model):
    """Dossier individuel d'un membre. Toujours rattaché à une seule Église."""
    STATUTS = [
        ("actif", "Actif"), ("visiteur", "Visiteur"), ("nouveau", "Nouveau venu"),
        ("integration", "En intégration"), ("transfere", "Transféré"),
        ("suspendu", "Suspendu"), ("decede", "Décédé"),
    ]
    ETATS_VALIDATION = [("brouillon", "Brouillon"), ("a_valider", "À valider"),
                        ("valide", "Validé"), ("retourne", "Retourné"), ("rejete", "Rejeté")]
    SEXES = [("M", "Masculin"), ("F", "Féminin")]

    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="membres")
    matricule = models.CharField(max_length=40, blank=True, default="")
    nom = models.CharField(max_length=120)
    postnom = models.CharField(max_length=120, blank=True, default="")
    prenom = models.CharField(max_length=120, blank=True, default="")
    sexe = models.CharField(max_length=1, choices=SEXES, blank=True, default="")
    date_naissance = models.DateField(null=True, blank=True)
    lieu_naissance = models.CharField(max_length=150, blank=True, default="")
    nationalite = models.CharField(max_length=80, blank=True, default="Congolaise (RDC)")
    profession = models.CharField(max_length=120, blank=True, default="")
    etat_civil = models.CharField(max_length=40, blank=True, default="")
    telephone = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    adresse = models.CharField(max_length=250, blank=True, default="")
    contact_urgence = models.CharField(max_length=200, blank=True, default="")
    date_adhesion = models.DateField(null=True, blank=True)
    date_ordination = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUTS, default="nouveau")
    etat_validation = models.CharField(max_length=20, choices=ETATS_VALIDATION, default="a_valider")
    observation = models.TextField(blank=True, default="")
    motif_rejet = models.CharField(max_length=400, blank=True, default="")
    photo_url = models.CharField(max_length=500, blank=True, default="")
    valide_le = models.DateTimeField(null=True, blank=True)
    valide_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="membres_valides")
    cree_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="membres_crees")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nom", "postnom", "prenom"]
        constraints = [
            models.UniqueConstraint(fields=["eglise", "matricule"],
                                    condition=~models.Q(matricule=""),
                                    name="matricule_unique_par_eglise"),
        ]

    def __str__(self):
        return f"{self.nom_complet} ({self.matricule or 'sans matricule'})"

    @property
    def nom_complet(self):
        return " ".join(p for p in [self.nom, self.postnom, self.prenom] if p)


class ParametreMatricule(models.Model):
    """Format du matricule, configurable par Église. Exemple : ELM-2026-0001"""
    eglise = models.OneToOneField(Eglise, on_delete=models.CASCADE, related_name="matricule_param")
    prefixe = models.CharField(max_length=20, default="EGL")
    inclure_annee = models.BooleanField(default=True)
    chiffres = models.IntegerField(default=4)
    separateur = models.CharField(max_length=3, default="-")
    compteur = models.IntegerField(default=0)

    def __str__(self):
        return f"matricule {self.eglise.slug} : {self.prefixe}…"


class EffectifDeclare(models.Model):
    """Effectif global déclaré des personnes sans dossier individuel.
    Total général = somme des effectifs déclarés + membres enregistrés."""
    CATEGORIES = [("adultes", "Adultes"), ("hommes", "Hommes"), ("femmes", "Femmes"),
                  ("jeunes", "Jeunes"), ("enfants", "Enfants"), ("invites", "Invités"),
                  ("autre", "Autre")]
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="effectifs")
    categorie = models.CharField(max_length=30, choices=CATEGORIES, default="adultes")
    valeur = models.IntegerField(default=0)
    periode = models.CharField(max_length=40, blank=True, default="")
    observation = models.CharField(max_length=400, blank=True, default="")
    auteur = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Groupe(models.Model):
    """Départements, ministères, cellules, chorales, équipes."""
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="groupes")
    nom = models.CharField(max_length=150)
    type = models.CharField(max_length=60, blank=True, default="département")
    description = models.CharField(max_length=400, blank=True, default="")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="sous_groupes")
    responsable = models.ForeignKey(Membre, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="groupes_diriges")
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} ({self.eglise.slug})"


class MembreGroupe(models.Model):
    membre = models.ForeignKey(Membre, on_delete=models.CASCADE, related_name="appartenances")
    groupe = models.ForeignKey(Groupe, on_delete=models.CASCADE, related_name="membres")
    fonction = models.CharField(max_length=80, blank=True, default="membre")
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["membre", "groupe"], name="un_membre_une_fois_par_groupe"),
        ]


class Evenement(models.Model):
    """Calendrier de l'Église : cultes, réunions, formations, activités spéciales (Phase 3)."""
    TYPES = [("culte", "Culte"), ("reunion", "Réunion"), ("priere", "Prière"),
             ("veillee", "Veillée"), ("formation", "Formation"), ("autre", "Autre")]
    STATUTS_EVENEMENT = [("planifie", "Planifié"), ("confirme", "Confirmé"),
                         ("annule", "Annulé"), ("termine", "Terminé")]
    RECURRENCES = [("aucune", "Aucune"), ("hebdomadaire", "Chaque semaine"),
                   ("mensuelle", "Chaque mois"), ("annuelle", "Chaque année")]
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="evenements")
    titre = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TYPES, default="culte")
    date = models.DateField()
    heure = models.CharField(max_length=10, blank=True, default="")
    heure_fin = models.CharField(max_length=10, blank=True, default="")
    lieu = models.CharField(max_length=200, blank=True, default="")
    groupe = models.ForeignKey(Groupe, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="evenements")
    # ── Phase 3
    description = models.TextField(blank=True, default="")
    date_fin = models.DateField(null=True, blank=True)
    duree_minutes = models.IntegerField(null=True, blank=True)
    journee_entiere = models.BooleanField(default=False)
    capacite = models.IntegerField(null=True, blank=True)
    public_cible = models.CharField(max_length=120, blank=True, default="")
    statut = models.CharField(max_length=20, choices=STATUTS_EVENEMENT, default="planifie")
    recurrence = models.CharField(max_length=20, choices=RECURRENCES, default="aucune")
    rappel_jours = models.IntegerField(default=1)
    responsable = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="evenements_diriges")
    cree_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="evenements_crees")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "heure"]

    def duree(self):
        """Durée en minutes : explicite, ou déduite de l'heure de fin quand elle existe."""
        if self.duree_minutes:
            return self.duree_minutes
        if self.heure and self.heure_fin:
            try:
                h1, m1 = [int(x) for x in self.heure.split(":")[:2]]
                h2, m2 = [int(x) for x in self.heure_fin.split(":")[:2]]
                return max(0, (h2 * 60 + m2) - (h1 * 60 + m1))
            except (ValueError, IndexError):
                return None
        return None


class EvenementInscription(models.Model):
    """Personnes annoncées à un événement, distinctes du pointage de présence."""
    STATUTS = [("inscrit", "Inscrit"), ("confirme", "Confirmé"), ("desinscrit", "Désinscrit")]
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="inscriptions_evenements")
    evenement = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name="inscriptions")
    membre = models.ForeignKey(Membre, on_delete=models.CASCADE, related_name="inscriptions_evenements")
    statut = models.CharField(max_length=20, choices=STATUTS, default="inscrit")
    note = models.CharField(max_length=300, blank=True, default="")
    cree_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["evenement", "membre"], name="unique_inscription_evenement"),
        ]


class Presence(models.Model):
    """Pointage. Soit un membre identifié, soit un visiteur, soit un effectif global."""
    STATUTS = [("present", "Présent"), ("retard", "Retard"), ("absent", "Absent")]
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="presences")
    evenement = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name="presences")
    membre = models.ForeignKey(Membre, null=True, blank=True, on_delete=models.CASCADE,
                               related_name="presences")
    visiteur_nom = models.CharField(max_length=200, blank=True, default="")
    statut = models.CharField(max_length=10, choices=STATUTS, default="present")
    effectif_global = models.IntegerField(null=True, blank=True,
                                          help_text="Nombre de personnes non identifiées présentes")
    observation = models.CharField(max_length=300, blank=True, default="")
    pointe_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["evenement", "membre"],
                                    condition=models.Q(membre__isnull=False),
                                    name="un_pointage_par_membre_et_evenement"),
        ]

# ═══════════════════ Phase 4 : module financier ═══════════════════

DEVISES = [("USD", "Dollar américain"), ("CDF", "Franc congolais")]

TYPES_COMPTE = [("espece", "Espèces"), ("banque", "Compte bancaire"),
                ("mobile_money", "Mobile Money"), ("autre", "Autre")]

SENS_OPERATION = [("recette", "Recette"), ("depense", "Dépense")]

STATUTS_MOUVEMENT = [("demande", "Demandé"), ("a_verifier", "À vérifier"),
                     ("approuve", "Approuvé"), ("rejete", "Rejeté"),
                     ("paye", "Payé"), ("cloture", "Clôturé"), ("annule", "Annulé")]


class CompteFinancier(models.Model):
    """Caisse ou compte de l'Église : espèces, banque, Mobile Money."""
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="comptes")
    nom = models.CharField(max_length=120)
    type = models.CharField(max_length=20, choices=TYPES_COMPTE, default="espece")
    devise = models.CharField(max_length=3, choices=DEVISES, default="CDF")
    solde_initial = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    responsable = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="comptes_diriges")
    actif = models.BooleanField(default=True)
    observation = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]

    def solde(self):
        """Solde initial plus recettes payées moins dépenses payées, transferts compris."""
        from django.db.models import Sum
        entrees = Mouvement.objects.filter(compte=self, sens="recette",
                                           statut__in=["paye", "cloture"]).aggregate(
            s=Sum("montant"))["s"] or 0
        sorties = Mouvement.objects.filter(compte=self, sens="depense",
                                           statut__in=["paye", "cloture"]).aggregate(
            s=Sum("montant"))["s"] or 0
        recus = TransfertInterne.objects.filter(compte_destination=self).aggregate(
            s=Sum("montant_recu"))["s"] or 0
        emis = TransfertInterne.objects.filter(compte_source=self).aggregate(
            s=Sum("montant"))["s"] or 0
        return self.solde_initial + entrees - sorties + recus - emis


class CategorieOperation(models.Model):
    """Catégorie de recette ou de dépense, personnalisable par Église."""
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="categories_finance")
    nom = models.CharField(max_length=120)
    sens = models.CharField(max_length=10, choices=SENS_OPERATION, default="recette")
    systeme = models.BooleanField(default=False)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["sens", "nom"]
        constraints = [models.UniqueConstraint(fields=["eglise", "nom", "sens"],
                                               name="unique_categorie_finance")]


class TauxChange(models.Model):
    """Taux historique : jamais recalculé quand le taux courant change."""
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="taux")
    devise_source = models.CharField(max_length=3, default="USD")
    devise_cible = models.CharField(max_length=3, default="CDF")
    taux = models.DecimalField(max_digits=14, decimal_places=4)
    date = models.DateField()
    source = models.CharField(max_length=120, blank=True, default="")
    saisi_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]


class Projet(models.Model):
    STATUTS = [("preparation", "En préparation"), ("en_cours", "En cours"),
               ("suspendu", "Suspendu"), ("termine", "Terminé"), ("annule", "Annulé")]
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="projets")
    nom = models.CharField(max_length=150)
    objectif = models.TextField(blank=True, default="")
    budget_montant = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    devise = models.CharField(max_length=3, choices=DEVISES, default="USD")
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    avancement = models.IntegerField(default=0)
    statut = models.CharField(max_length=20, choices=STATUTS, default="en_cours")
    cree_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Budget(models.Model):
    """Budget par département, activité ou projet, avec seuils d'alerte configurables."""
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="budgets")
    nom = models.CharField(max_length=150)
    groupe = models.ForeignKey(Groupe, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="budgets")
    projet = models.ForeignKey(Projet, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="budgets")
    montant = models.DecimalField(max_digits=16, decimal_places=2)
    devise = models.CharField(max_length=3, choices=DEVISES, default="USD")
    date_debut = models.DateField()
    date_fin = models.DateField()
    seuils = models.JSONField(default=list, blank=True)
    bloquer_depassement = models.BooleanField(default=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_debut"]

    def consomme(self):
        from django.db.models import Sum
        return Mouvement.objects.filter(budget=self, sens="depense", statut__in=[
            "demande", "a_verifier", "approuve", "paye", "cloture"]).aggregate(
            s=Sum("montant"))["s"] or 0

    def paye(self):
        from django.db.models import Sum
        return Mouvement.objects.filter(budget=self, sens="depense", statut__in=[
            "paye", "cloture"]).aggregate(s=Sum("montant"))["s"] or 0


class Mouvement(models.Model):
    """Recette ou dépense. Une dépense approuvée n'est pas encore payée."""
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="mouvements")
    compte = models.ForeignKey(CompteFinancier, on_delete=models.PROTECT, related_name="mouvements")
    categorie = models.ForeignKey(CategorieOperation, null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="mouvements")
    sens = models.CharField(max_length=10, choices=SENS_OPERATION, default="recette")
    montant = models.DecimalField(max_digits=16, decimal_places=2)
    devise = models.CharField(max_length=3, choices=DEVISES, default="CDF")
    montant_converti = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True,
                                           help_text="Contre-valeur dans la devise de référence")
    taux = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    date = models.DateField()
    libelle = models.CharField(max_length=250)
    membre = models.ForeignKey(Membre, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="mouvements")
    donateur_nom = models.CharField(max_length=150, blank=True, default="")
    anonyme = models.BooleanField(default=False)
    collecte_globale = models.BooleanField(default=False)
    justificatif_url = models.CharField(max_length=500, blank=True, default="")
    justification = models.CharField(max_length=400, blank=True, default="")
    statut = models.CharField(max_length=20, choices=STATUTS_MOUVEMENT, default="demande")
    reference_recu = models.CharField(max_length=40, blank=True, default="")
    projet = models.ForeignKey(Projet, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="mouvements")
    budget = models.ForeignKey(Budget, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="mouvements")
    cree_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="mouvements_crees")
    verifie_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="mouvements_verifies")
    approuve_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="mouvements_approuves")
    seconde_validation_par = models.ForeignKey(Utilisateur, null=True, blank=True,
                                               on_delete=models.SET_NULL,
                                               related_name="mouvements_double_valides")
    paye_le = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]


class TransfertInterne(models.Model):
    """Transfert entre deux comptes : ni recette ni dépense, frais enregistrés à part."""
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="transferts")
    compte_source = models.ForeignKey(CompteFinancier, on_delete=models.PROTECT,
                                      related_name="transferts_emis")
    compte_destination = models.ForeignKey(CompteFinancier, on_delete=models.PROTECT,
                                           related_name="transferts_recus")
    montant = models.DecimalField(max_digits=16, decimal_places=2)
    devise = models.CharField(max_length=3, choices=DEVISES, default="CDF")
    montant_recu = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    frais = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    date = models.DateField()
    libelle = models.CharField(max_length=250, blank=True, default="")
    cree_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)


class CloturePeriode(models.Model):
    """Clôture mensuelle : préparation puis approbation par une autre personne."""
    STATUTS = [("prepare", "Préparée"), ("approuve", "Approuvée")]
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="clotures")
    periode = models.CharField(max_length=7)  # AAAA-MM
    statut = models.CharField(max_length=20, choices=STATUTS, default="prepare")
    total_recettes = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_depenses = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    ecart = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    justification = models.CharField(max_length=500, blank=True, default="")
    prepare_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="clotures_preparees")
    approuve_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="clotures_approuvees")
    verrouille = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-periode"]
        constraints = [models.UniqueConstraint(fields=["eglise", "periode"],
                                               name="unique_cloture_periode")]


class Rapprochement(models.Model):
    """Rapprochement de caisse, de banque ou de Mobile Money avec le relevé."""
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="rapprochements")
    compte = models.ForeignKey(CompteFinancier, on_delete=models.CASCADE, related_name="rapprochements")
    date = models.DateField()
    solde_releve = models.DecimalField(max_digits=16, decimal_places=2)
    solde_calcule = models.DecimalField(max_digits=16, decimal_places=2)
    ecart = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    justification = models.CharField(max_length=500, blank=True, default="")
    cree_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

class ParametreFinance(models.Model):
    """Seuils de validation configurables par Église (section 10.3)."""
    eglise = models.OneToOneField(Eglise, on_delete=models.CASCADE, related_name="finance_param")
    devise_reference = models.CharField(max_length=3, default="USD")
    seuil_verification = models.DecimalField(max_digits=16, decimal_places=2, default=100)
    seuil_double_validation = models.DecimalField(max_digits=16, decimal_places=2, default=500)
    justificatif_obligatoire = models.BooleanField(default=True)
    prefixe_recu = models.CharField(max_length=12, default="REC")
    compteur_recu = models.IntegerField(default=0)

# ═══════════════════ Phase 5 : patrimoine et équipements ═══════════════════

ETATS_BIEN = [("neuf", "Neuf"), ("bon", "Bon état"), ("usage", "Usagé"),
              ("a_reparer", "À réparer"), ("hors_service", "Hors service"), ("reforme", "Réformé")]

CATEGORIES_BIEN = [("terrain", "Terrain"), ("batiment", "Bâtiment"), ("vehicule", "Véhicule"),
                   ("mobilier", "Mobilier"), ("informatique", "Informatique et son"),
                   ("instrument", "Instrument de musique"), ("electromenager", "Électroménager"),
                   ("autre", "Autre")]

TYPES_MOUVEMENT_BIEN = [("acquisition", "Acquisition"), ("affectation", "Affectation"),
                        ("retour", "Retour"), ("pret", "Prêt"), ("entretien", "Entretien"),
                        ("reparation", "Réparation"), ("reforme", "Réforme"),
                        ("inventaire", "Constat d'inventaire")]


class BienPatrimoine(models.Model):
    """Bien durable de l'Église : terrain, bâtiment, véhicule, mobilier, matériel."""
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="biens")
    code = models.CharField(max_length=40, blank=True, default="")
    nom = models.CharField(max_length=200)
    categorie = models.CharField(max_length=20, choices=CATEGORIES_BIEN, default="mobilier")
    description = models.TextField(blank=True, default="")
    quantite = models.IntegerField(default=1)
    date_acquisition = models.DateField(null=True, blank=True)
    valeur_achat = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    devise = models.CharField(max_length=3, choices=DEVISES, default="USD")
    localisation = models.CharField(max_length=200, blank=True, default="")
    responsable = models.ForeignKey(Membre, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="biens_sous_responsabilite")
    etat = models.CharField(max_length=20, choices=ETATS_BIEN, default="bon")
    groupe = models.ForeignKey(Groupe, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="biens")
    justificatif_url = models.CharField(max_length=500, blank=True, default="")
    observation = models.CharField(max_length=400, blank=True, default="")
    cree_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["categorie", "nom"]
        constraints = [models.UniqueConstraint(fields=["eglise", "code"],
                                               condition=~models.Q(code=""),
                                               name="unique_code_bien_eglise")]

    def valeur_totale(self):
        return self.valeur_achat * max(self.quantite or 1, 1)


class MouvementBien(models.Model):
    """Journal d'un bien : affectation, prêt, entretien, réparation, réforme, inventaire."""
    eglise = models.ForeignKey(Eglise, on_delete=models.CASCADE, related_name="mouvements_biens")
    bien = models.ForeignKey(BienPatrimoine, on_delete=models.CASCADE, related_name="mouvements")
    type = models.CharField(max_length=20, choices=TYPES_MOUVEMENT_BIEN, default="affectation")
    date = models.DateField()
    personne = models.CharField(max_length=150, blank=True, default="")
    membre = models.ForeignKey(Membre, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="mouvements_biens")
    lieu = models.CharField(max_length=200, blank=True, default="")
    cout = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=400, blank=True, default="")
    cree_par = models.ForeignKey(Utilisateur, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
