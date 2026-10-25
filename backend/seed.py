import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from datetime import timedelta
from django.utils import timezone
from core.models import Eglise, Utilisateur, Role
from core.security import hasher, MODULES, ACTIONS

TOUT = {m: list(ACTIONS) for m in MODULES}
ROLES = [
    ("Pasteur", "Responsable spirituel : consultation élargie, suivi pastoral.", ["membres", "presences", "evenements", "pastoral", "groupes", "communication", "documents"]),
    ("Trésorier", "Gestion des finances de l'Église.", ["finances"]),
    ("Secrétaire", "Gestion administrative des membres et documents.", ["membres", "documents", "presences", "groupes", "evenements"]),
    ("Responsable de département", "Gestion de son département et de ses activités.", ["presences", "evenements", "groupes"]),
    ("Moniteur école du dimanche", "Encadrement des enfants et école du dimanche.", ["enfants"]),
]
if not Role.objects.filter(systeme=True).exists():
    for nom, desc, modules in ROLES:
        Role.objects.create(nom=nom, description=desc, systeme=True,
                            permissions={m: list(ACTIONS) for m in modules})
    print("Rôles système créés :", ROLES.__len__())
if not Utilisateur.objects.filter(is_super_admin=True).exists():
    Utilisateur.objects.create(nom_complet="Administrateur Plateforme",
                               email="superadmin@omnichurch.app",
                               mot_de_passe=hasher("Omni!Super2026"),
                               is_super_admin=True)
    print("Super-admin créé : superadmin@omnichurch.app / Omni!Super2026")
if not Eglise.objects.filter(slug="lumiere-du-monde").exists():
    e = Eglise.objects.create(nom="Église Lumière du Monde — Temple de Positionnement",
                              slug="lumiere-du-monde", ville="Kinshasa", pays="RDC",
                              denomination="Lumière du Monde",
                              essai_expire_le=timezone.now() + timedelta(days=7),
                              statut="approuve")
    admin = Utilisateur.objects.create(eglise=e, nom_complet="Administrateur Principal",
                                      email="admin@lumieredumonde.cd",
                                      mot_de_passe=hasher("Lumiere!2026"),
                                      is_admin_principal=True)
    print("Église démo créée : admin@lumieredumonde.cd / Lumiere!2026")
print("Seed terminé.")
