"""Sécurité : hachage, permissions, décorateurs d'authentification, audit."""
import functools
from datetime import timedelta

from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from django.http import JsonResponse

MODULES = {
    "membres": "Membres",
    "finances": "Finances",
    "groupes": "Groupes & départements",
    "presences": "Présences",
    "evenements": "Calendrier & événements",
    "documents": "Documents",
    "communication": "Communication",
    "patrimoine": "Patrimoine",
    "pastoral": "Suivi pastoral",
    "enfants": "Enfants & école du dimanche",
    "intervenants": "Intervenants",
    "mediatheque": "Bibliothèque média",
    "parametres": "Paramètres",
    "utilisateurs": "Utilisateurs & rôles",
}
ACTIONS = ["consulter", "creer", "modifier", "valider", "supprimer", "exporter"]


def hasher(mot_de_passe):
    return make_password(mot_de_passe)


def verifier(mot_de_passe_clair, mot_de_passe_hache):
    try:
        return check_password(mot_de_passe_clair, mot_de_passe_hache)
    except Exception:
        return False


def permissions_utilisateur(user):
    """Toutes les permissions effectives de l'utilisateur (rôles valides)."""
    if user.is_super_admin or user.is_admin_principal:
        return {m: list(ACTIONS) for m in MODULES}
    perms = {}
    maintenant = timezone.now()
    for ur in user.roles.select_related("role").filter(
            date_fin__isnull=True) | user.roles.select_related("role").filter(date_fin__gt=maintenant):
        for module, actions in (ur.role.permissions or {}).items():
            perms.setdefault(module, [])
            for a in actions:
                if a not in perms[module]:
                    perms[module].append(a)
    return perms


def a_permission(user, module, action):
    return action in permissions_utilisateur(user).get(module, [])


def _reponse(code, data):
    return JsonResponse({"success": code == 200, **({"data": data} if code == 200 else {}),
                         **({} if code == 200 else {"error": data})}, status=code)


def utilisateur_depuis_requete(request):
    """Résout l'utilisateur depuis X-Auth-Token. Ne fait jamais confiance au client
    pour déterminer l'Église : elle vient uniquement de l'utilisateur en base."""
    token = request.headers.get("X-Auth-Token", "")
    if not token:
        return None
    try:
        sess = TokenSession.objects.select_related("utilisateur", "utilisateur__eglise").get(
            token=token, actif=True)
    except TokenSession.DoesNotExist:
        return None
    if sess.expire_le and sess.expire_le < timezone.now():
        return None
    if sess.utilisateur.statut != "actif":
        return None
    return sess.utilisateur


def auth_requise(super_admin=False):
    def decorateur(vue):
        @functools.wraps(vue)
        def enveloppe(request, *args, **kwargs):
            user = utilisateur_depuis_requete(request)
            if not user:
                return _reponse(401, "Session invalide ou expirée.")
            if super_admin and not user.is_super_admin:
                return _reponse(403, "Accès réservé au super-administrateur de la plateforme.")
            request.utilisateur = user
            return vue(request, *args, **kwargs)
        return enveloppe
    return decorateur


def permission_requise(module, action="consulter"):
    def decorateur(vue):
        @functools.wraps(vue)
        def enveloppe(request, *args, **kwargs):
            user = getattr(request, "utilisateur", None) or utilisateur_depuis_requete(request)
            if not user:
                return _reponse(401, "Session invalide ou expirée.")
            if not a_permission(user, module, action):
                return _reponse(403, f"Permission refusée : {module}.{action}")
            request.utilisateur = user
            return vue(request, *args, **kwargs)
        return enveloppe
    return decorateur


def tracer(user, module, action, details="", eglise=None, ip=""):
    """Enregistre une entrée d'audit. Ne peut pas être contournée côté client."""
    try:
        JournalAudit.objects.create(
            eglise=eglise or (user.eglise if user else None),
            utilisateur=user, module=module, action=action,
            details=details[:2000], ip=ip[:60])
    except Exception:
        pass


def nouvelle_session(user, appareil="", duree_jours=30):
    TokenSession.objects.filter(utilisateur=user, actif=True).update(actif=False)
    sess = TokenSession.objects.create(
        utilisateur=user, appareil=appareil[:250],
        expire_le=timezone.now() + timedelta(days=duree_jours))
    return sess.token


def ip_depuis(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return fwd.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")


from core.models import TokenSession, JournalAudit  # noqa: E402
