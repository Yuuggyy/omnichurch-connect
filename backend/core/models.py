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
