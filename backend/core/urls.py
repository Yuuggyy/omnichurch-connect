from django.urls import path
from . import views_api as v
from . import views_membres as m

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
    # ── Phase 2 : membres
    path("membres/", m.membres_liste),
    path("membre/", m.membre_detail),
    path("membre/creer/", m.membre_creer),
    path("membre/modifier/", m.membre_modifier),
    path("membre/valider/", m.membre_valider),
    path("membre/retourner/", m.membre_retourner),
    path("membre/rejeter/", m.membre_rejeter),
    path("membre/archiver/", m.membre_archiver),
    path("membres/doublons/", m.membres_doublons),
    path("membres/export/", m.membres_export),
    path("effectifs/", m.effectifs_liste),
    path("effectif/creer/", m.effectif_creer),
    path("matricule/parametres/", m.matricule_parametres),
    # ── Phase 2 : groupes
    path("groupes/", m.groupes_liste),
    path("groupe/creer/", m.groupe_creer),
    path("groupe/modifier/", m.groupe_modifier),
    path("groupe/supprimer/", m.groupe_supprimer),
    path("groupe/affecter/", m.groupe_affecter),
    path("groupe/retirer/", m.groupe_retirer),
    # ── Phase 2 : présences
    path("evenements/", m.evenements_liste),
    path("evenement/creer/", m.evenement_creer),
    path("presences/", m.presences_liste),
    path("presence/pointer/", m.presence_pointer),
    path("presence/supprimer/", m.presence_supprimer),
    path("presences/stats/", m.presences_stats),
    # ── Phase 2 : documents de base
    path("document/fiche/", m.document_fiche),
    path("document/carte/", m.document_carte),
    # ── Phase 2 : tableau de bord
    path("bord/stats/", m.bord_stats),
]
