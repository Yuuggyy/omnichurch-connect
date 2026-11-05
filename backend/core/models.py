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
