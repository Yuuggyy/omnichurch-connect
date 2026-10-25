from django.urls import path
from . import views_api as v

urlpatterns = [
    # Auth
    path("auth/inscription-eglise/", v.inscription_eglise),
    path("auth/login/", v.login),
    path("auth/logout/", v.logout),
    path("auth/moi/", v.moi),
    path("auth/sessions-revoquer/", v.sessions_revoquer),
    # Église
    path("eglise/parametres/", v.parametres_eglise),
    path("tableau-bord/", v.tableau_bord),
    # Utilisateurs & rôles
    path("utilisateurs/", v.utilisateurs_liste),
    path("utilisateur/creer/", v.utilisateur_creer),
    path("utilisateur/modifier/", v.utilisateur_modifier),
    path("utilisateur/supprimer/", v.utilisateur_supprimer),
    path("roles/", v.roles_liste),
    path("role/creer/", v.role_creer),
    path("role/supprimer/", v.role_supprimer),
    path("role/attribuer/", v.role_attribuer),
    path("invitation/creer/", v.invitation_creer),
    path("invitations/", v.invitations_liste),
    path("invitation/accepter/", v.invitation_accepter),
    # Audit
    path("audit/", v.audit_liste),
    # Super-admin
    path("super/eglises/", v.super_eglises),
]
