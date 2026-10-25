"""API OmniChurch Connect — Phase 1 : fondations."""
import json
import re
import secrets
from datetime import timedelta

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from core.models import (Eglise, Utilisateur, TokenSession, Role, UserRole,
                         Invitation, JournalAudit)
from core.security import (MODULES, ACTIONS, hasher, verifier, auth_requise,
                           permission_requise, tracer, nouvelle_session,
                           ip_depuis, permissions_utilisateur)


def ok(data=None):
    return JsonResponse({"success": True, **({"data": data} if data is not None else {})})


def err(message, code=400):
    return JsonResponse({"success": False, "error": message}, status=code)


def corps(request):
    try:
        return json.loads(request.body or b"{}")
    except Exception:
        return {}


def _slug(nom):
    s = re.sub(r"[^a-z0-9]+", "-", nom.lower()).strip("-")[:40] or "eglise"
    base, i = s, 2
    while Eglise.objects.filter(slug=s).exists():
        s = f"{base}-{i}"; i += 1
    return s


def _eglise_json(e):
    return {"id": e.id, "nom": e.nom, "slug": e.slug, "pays": e.pays, "ville": e.ville,
            "adresse": e.adresse, "denomination": e.denomination,
            "annee_fondation": e.annee_fondation, "email": e.email,
            "telephone": e.telephone, "logo_url": e.logo_url,
            "couleur_primaire": e.couleur_primaire, "couleur_accent": e.couleur_accent,
            "langue": e.langue, "statut": e.statut,
            "essai_expire_le": e.essai_expire_le.isoformat() if e.essai_expire_le else None,
            "created_at": e.created_at.isoformat()}


def _user_json(u, perms=None):
    roles = [{"id": ur.role_id, "nom": ur.role.nom,
              "date_fin": ur.date_fin.isoformat() if ur.date_fin else None}
             for ur in u.roles.select_related("role").order_by("-date_debut")]
    return {"id": u.id, "nom_complet": u.nom_complet, "email": u.email,
            "telephone": u.telephone, "eglise_id": u.eglise_id,
            "eglise_nom": u.eglise.nom if u.eglise else None,
            "is_super_admin": u.is_super_admin, "is_admin_principal": u.is_admin_principal,
            "statut": u.statut, "langue": u.langue, "roles": roles,
            "permissions": perms if perms is not None else permissions_utilisateur(u),
            "dernier_login": u.dernier_login.isoformat() if u.dernier_login else None}


# ───────────────────────── Authentification ─────────────────────────

@csrf_exempt
def inscription_eglise(request):
    """Parcours d'inscription : crée l'Église + l'administrateur principal.
    L'Église démarre en statut 'a_completer' avec un essai de 7 jours."""
    d = corps(request)
    nom = (d.get("nom_eglise") or "").strip()
    responsable = (d.get("responsable") or "").strip()
    email = (d.get("email") or "").strip().lower()
    mot_de_passe = d.get("mot_de_passe") or ""
    if not (nom and responsable and email and len(mot_de_passe) >= 8):
        return err("Renseignez : nom de l'Église, responsable, e-mail et un mot de passe de 8 caractères minimum.")
    if Utilisateur.objects.filter(email=email).exists():
        return err("Un compte existe déjà avec cet e-mail. Connectez-vous.")
    # Détection de doublons potentiels (pas de fusion automatique)
    proches = list(Eglise.objects.filter(
        Q(nom__icontains=nom) | Q(email=email)).values_list("id", "nom", "slug"))
    eglise = Eglise.objects.create(
        nom=nom, slug=_slug(nom), pays=(d.get("pays") or "RDC").strip(),
        ville=(d.get("ville") or "").strip(), email=email,
        telephone=(d.get("telephone") or "").strip(),
        essai_expire_le=timezone.now() + timedelta(days=7))
    user = Utilisateur.objects.create(
        eglise=eglise, nom_complet=responsable, email=email,
        telephone=(d.get("telephone") or "").strip(),
        mot_de_passe=hasher(mot_de_passe), is_admin_principal=True)
    tracer(user, "parametres", "inscription_eglise",
           f"Création de l'espace « {eglise.nom} » (admin principal)", eglise,
           ip_depuis(request))
    token = nouvelle_session(user, request.headers.get("User-Agent", ""))
    return ok({"token": token, "eglise": _eglise_json(eglise),
               "utilisateur": _user_json(user),
               "avertissement_doublons": proches})


@csrf_exempt
def login(request):
    d = corps(request)
    email = (d.get("email") or "").strip().lower()
    mot_de_passe = d.get("mot_de_passe") or ""
    try:
        user = Utilisateur.objects.select_related("eglise").get(email=email)
    except Utilisateur.DoesNotExist:
        return err("Identifiants incorrects.", 401)
    now = timezone.now()
    if user.verrouille_jusqua and user.verrouille_jusqua > now:
        minutes = int((user.verrouille_jusqua - now).total_seconds() // 60) + 1
        return err(f"Compte temporairement verrouillé. Réessayez dans {minutes} min.", 423)
    if not verifier(mot_de_passe, user.mot_de_passe) or user.statut == "revoque":
        user.tentatives_echec += 1
        if user.tentatives_echec >= 5:
            user.verrouille_jusqua = now + timedelta(minutes=15)
            user.tentatives_echec = 0
        user.save(update_fields=["tentatives_echec", "verrouille_jusqua"])
        tracer(None, "auth", "echec_connexion", f"Tentative échouée : {email}",
               user.eglise, ip_depuis(request))
        return err("Identifiants incorrects.", 401)
    if user.statut == "suspendu":
        return err("Ce compte est suspendu. Contactez l'administrateur principal.", 403)
    if user.eglise and user.eglise.statut == "suspendu":
        return err("L'espace de votre Église est suspendu.", 403)
    if user.eglise and user.eglise.essai_expire_le and user.eglise.essai_expire_le < now \
            and not user.is_super_admin:
        return err("La période d'essai de votre Église est expirée.", 402)
    user.tentatives_echec = 0
    user.verrouille_jusqua = None
    user.dernier_login = now
    user.save()
    token = nouvelle_session(user, request.headers.get("User-Agent", ""))
    tracer(user, "auth", "connexion", "Connexion réussie", user.eglise, ip_depuis(request))
    return ok({"token": token, "utilisateur": _user_json(user),
               "eglise": _eglise_json(user.eglise) if user.eglise else None})


@csrf_exempt
@auth_requise()
def logout(request):
    request.headers  # noqa
    tok = request.headers.get("X-Auth-Token", "")
    TokenSession.objects.filter(token=tok).update(actif=False)
    return ok()


@csrf_exempt
@auth_requise()
def moi(request):
    u = request.utilisateur
    sessions = [{"id": s.id, "appareil": s.appareil, "created_at": s.created_at.isoformat(),
                 "actuelle": s.token == request.headers.get("X-Auth-Token", "")}
                for s in u.sessions.filter(actif=True).order_by("-created_at")]
    return ok({"utilisateur": _user_json(u),
               "eglise": _eglise_json(u.eglise) if u.eglise else None,
               "modules": MODULES, "actions": ACTIONS, "sessions": sessions})


# ───────────────────────── Paramètres de l'Église ─────────────────────────

@csrf_exempt
@auth_requise()
def parametres_eglise(request):
    u = request.utilisateur
    if not u.eglise:
        return err("Aucun espace d'Église associé.", 403)
    if request.method == "GET":
        return ok({"eglise": _eglise_json(u.eglise)})
    d = corps(request)
    champs = ["nom", "pays", "ville", "adresse", "denomination", "annee_fondation",
              "email", "telephone", "logo_url", "couleur_primaire", "couleur_accent", "langue"]
    e = u.eglise
    modifs = []
    for c in champs:
        if c in d and d[c] is not None:
            val = d[c]
            if c == "annee_fondation":
                try:
                    val = int(val)
                except (TypeError, ValueError):
                    continue
            setattr(e, c, val)
            modifs.append(c)
    e.save()
    tracer(u, "parametres", "modification", f"Champs modifiés : {', '.join(modifs)}",
           e, ip_depuis(request))
    return ok({"eglise": _eglise_json(e)})


# ───────────────────────── Utilisateurs & rôles ─────────────────────────

@csrf_exempt
@permission_requise("utilisateurs", "consulter")
def utilisateurs_liste(request):
    u = request.utilisateur
    qs = Utilisateur.objects.filter(eglise=u.eglise).order_by("-created_at") \
        if u.eglise else Utilisateur.objects.filter(is_super_admin=True)
    return ok({"utilisateurs": [_user_json(x) for x in qs]})


@csrf_exempt
@permission_requise("utilisateurs", "creer")
def utilisateur_creer(request):
    """Seul l'administrateur principal crée des comptes manuellement."""
    u = request.utilisateur
    if not u.is_admin_principal or not u.eglise:
        return err("Seul l'administrateur principal peut créer des comptes.", 403)
    d = corps(request)
    email = (d.get("email") or "").strip().lower()
    if not email or not (d.get("nom_complet") or "").strip():
        return err("Nom complet et e-mail requis.")
    if Utilisateur.objects.filter(email=email).exists():
        return err("Cet e-mail est déjà utilisé.")
    mdp = d.get("mot_de_passe") or secrets.token_urlsafe(10)
    nouveau = Utilisateur.objects.create(
        eglise=u.eglise, nom_complet=d["nom_complet"].strip(), email=email,
        telephone=(d.get("telephone") or "").strip(), mot_de_passe=hasher(mdp))
    role_id = d.get("role_id")
    if role_id:
        role = Role.objects.filter(id=role_id).filter(Q(eglise=u.eglise) | Q(systeme=True)).first()
        if role:
            UserRole.objects.create(utilisateur=nouveau, role=role, accorde_par=u)
    tracer(u, "utilisateurs", "creation", f"Compte créé : {email}", u.eglise, ip_depuis(request))
    return ok({"utilisateur": _user_json(nouveau), "mot_de_passe_initial": mdp})


@csrf_exempt
@permission_requise("utilisateurs", "modifier")
def utilisateur_modifier(request):
    u = request.utilisateur
    d = corps(request)
    cible = Utilisateur.objects.filter(id=d.get("id"), eglise=u.eglise).first()
    if not cible:
        return err("Utilisateur introuvable dans votre Église.", 404)
    if cible.is_admin_principal and cible.id != u.id and not u.is_super_admin:
        return err("Le compte de l'administrateur principal ne peut être modifié que par lui-même.", 403)
    for c in ["nom_complet", "telephone", "langue"]:
        if d.get(c):
            setattr(cible, c, d[c].strip() if isinstance(d[c], str) else d[c])
    if d.get("mot_de_passe"):
        if len(d["mot_de_passe"]) < 8:
            return err("Mot de passe : 8 caractères minimum.")
        cible.mot_de_passe = hasher(d["mot_de_passe"])
    if d.get("statut") in ("actif", "suspendu") and not cible.is_admin_principal:
        cible.statut = d["statut"]
        if d["statut"] == "suspendu":
            cible.sessions.update(actif=False)
    cible.save()
    tracer(u, "utilisateurs", "modification",
           f"{cible.email} : {', '.join(k for k in d if k != 'id')}", u.eglise, ip_depuis(request))
    return ok({"utilisateur": _user_json(cible)})


@csrf_exempt
@permission_requise("utilisateurs", "supprimer")
def utilisateur_supprimer(request):
    u = request.utilisateur
    d = corps(request)
    cible = Utilisateur.objects.filter(id=d.get("id"), eglise=u.eglise).first()
    if not cible:
        return err("Utilisateur introuvable dans votre Église.", 404)
    if cible.is_admin_principal:
        return err("L'administrateur principal ne peut pas être révoqué.", 403)
    cible.statut = "revoque"
    cible.sessions.update(actif=False)
    cible.save()
    tracer(u, "utilisateurs", "revocation", f"Compte révoqué : {cible.email}",
           u.eglise, ip_depuis(request))
    return ok()


@csrf_exempt
@permission_requise("utilisateurs", "consulter")
def roles_liste(request):
    u = request.utilisateur
    qs = Role.objects.filter(Q(systeme=True) | Q(eglise=u.eglise)).order_by("id")
    return ok({"roles": [{"id": r.id, "nom": r.nom, "description": r.description,
                          "permissions": r.permissions, "systeme": r.systeme} for r in qs],
               "modules": MODULES, "actions": ACTIONS})


@csrf_exempt
@permission_requise("utilisateurs", "creer")
def role_creer(request):
    u = request.utilisateur
    d = corps(request)
    nom = (d.get("nom") or "").strip()
    if not nom:
        return err("Nom du rôle requis.")
    perms = d.get("permissions") or {}
    propres = {m: [a for a in acts if a in ACTIONS] for m, acts in perms.items()
               if m in MODULES and isinstance(acts, list)}
    role = Role.objects.create(eglise=u.eglise, nom=nom,
                               description=(d.get("description") or "")[:300],
                               permissions=propres)
    tracer(u, "utilisateurs", "role_cree", f"Rôle « {nom} »", u.eglise, ip_depuis(request))
    return ok({"role": {"id": role.id, "nom": role.nom, "description": role.description,
                        "permissions": role.permissions, "systeme": False}})


@csrf_exempt
@permission_requise("utilisateurs", "supprimer")
def role_supprimer(request):
    u = request.utilisateur
    d = corps(request)
    role = Role.objects.filter(id=d.get("id"), eglise=u.eglise, systeme=False).first()
    if not role:
        return err("Rôle introuvable ou système (non supprimable).", 404)
    role.delete()
    tracer(u, "utilisateurs", "role_supprime", f"Rôle « {role.nom} »", u.eglise, ip_depuis(request))
    return ok()


@csrf_exempt
@permission_requise("utilisateurs", "modifier")
def role_attribuer(request):
    """Attribution ou retrait de rôle (délégation éventuellement temporaire)."""
    u = request.utilisateur
    d = corps(request)
    cible = Utilisateur.objects.filter(id=d.get("utilisateur_id"), eglise=u.eglise).first()
    role = Role.objects.filter(id=d.get("role_id")).filter(
        Q(eglise=u.eglise) | Q(systeme=True)).first()
    if not cible or not role:
        return err("Utilisateur ou rôle introuvable dans votre Église.", 404)
    if cible.is_admin_principal:
        return err("L'administrateur principal possède déjà toutes les permissions.", 400)
    if d.get("retirer"):
        suppr, _ = UserRole.objects.filter(utilisateur=cible, role=role).delete()
        tracer(u, "utilisateurs", "role_retire", f"{role.nom} retiré à {cible.email}",
               u.eglise, ip_depuis(request))
        return ok({"supprime": suppr})
    date_fin = None
    if d.get("date_fin"):
        try:
            date_fin = timezone.make_aware(
                timezone.datetime.fromisoformat(str(d["date_fin"])))
        except ValueError:
            return err("Format de date de fin invalide.")
    UserRole.objects.update_or_create(utilisateur=cible, role=role,
                                      defaults={"accorde_par": u, "date_fin": date_fin})
    tracer(u, "utilisateurs", "role_attribue",
           f"{role.nom} attribué à {cible.email}" + (f" jusqu'au {date_fin:%d/%m/%Y}" if date_fin else ""),
           u.eglise, ip_depuis(request))
    return ok({"utilisateur": _user_json(cible)})


@csrf_exempt
@auth_requise()
def invitation_creer(request):
    """Invitation à usage unique — réservée à l'administrateur principal."""
    u = request.utilisateur
    if not u.is_admin_principal or not u.eglise:
        return err("Seul l'administrateur principal peut envoyer des invitations.", 403)
    d = corps(request)
    email = (d.get("email") or "").strip().lower()
    if not email:
        return err("E-mail requis.")
    role = None
    if d.get("role_id"):
        role = Role.objects.filter(id=d["role_id"]).filter(
            Q(eglise=u.eglise) | Q(systeme=True)).first()
    inv = Invitation.objects.create(
        eglise=u.eglise, email=email, nom_complet=(d.get("nom_complet") or "").strip(),
        role=role, expire_le=timezone.now() + timedelta(days=7), cree_par=u)
    tracer(u, "utilisateurs", "invitation_creee", f"Invitation pour {email}",
           u.eglise, ip_depuis(request))
    return ok({"invitation": {"id": inv.id, "email": inv.email, "token": inv.token,
                               "expire_le": inv.expire_le.isoformat(),
                               "role": role.nom if role else None}})


@csrf_exempt
@auth_requise()
def invitations_liste(request):
    u = request.utilisateur
    invs = u.eglise.invitations.order_by("-created_at") if u.eglise else Invitation.objects.none()
    return ok({"invitations": [{"id": i.id, "email": i.email, "nom_complet": i.nom_complet,
                                "expire_le": i.expire_le.isoformat() if i.expire_le else None,
                                "utilise_le": i.utilise_le.isoformat() if i.utilise_le else None,
                                "role": i.role.nom if i.role else None,
                                "expiree": bool(i.expire_le and i.expire_le < timezone.now())}
                               for i in invs]})


@csrf_exempt
def invitation_accepter(request):
    """Acceptation d'une invitation : crée le compte lié à l'Église émettrice."""
    d = corps(request)
    inv = Invitation.objects.select_related("eglise").filter(
        token=d.get("token"), utilise_le__isnull=True).first()
    now = timezone.now()
    if not inv or (inv.expire_le and inv.expire_le < now):
        return err("Invitation invalide, expirée ou déjà utilisée.", 404)
    email = (d.get("email") or inv.email).strip().lower()
    if Utilisateur.objects.filter(email=email).exists():
        return err("Un compte existe déjà avec cet e-mail. Connectez-vous.")
    if len(d.get("mot_de_passe") or "") < 8:
        return err("Mot de passe : 8 caractères minimum.")
    user = Utilisateur.objects.create(
        eglise=inv.eglise, nom_complet=(d.get("nom_complet") or inv.nom_complet or email),
        email=email, mot_de_passe=hasher(d["mot_de_passe"]))
    if inv.role:
        UserRole.objects.create(utilisateur=user, role=inv.role)
    inv.utilise_le = now
    inv.save()
    tracer(user, "utilisateurs", "invitation_acceptee", f"{email} a rejoint {inv.eglise.nom}",
           inv.eglise, ip_depuis(request))
    token = nouvelle_session(user, request.headers.get("User-Agent", ""))
    return ok({"token": token, "utilisateur": _user_json(user),
               "eglise": _eglise_json(inv.eglise)})


# ───────────────────────── Sessions & audit ─────────────────────────

@csrf_exempt
@auth_requise()
def sessions_revoquer(request):
    u = request.utilisateur
    d = corps(request)
    if d.get("id") == "autres":
        u.sessions.exclude(token=request.headers.get("X-Auth-Token", "")).update(actif=False)
    elif d.get("id"):
        u.sessions.filter(id=d["id"]).update(actif=False)
    tracer(u, "auth", "sessions_revoquees", "Sessions révoquées", u.eglise, ip_depuis(request))
    return ok()


@csrf_exempt
@permission_requise("parametres", "consulter")
def audit_liste(request):
    u = request.utilisateur
    qs = JournalAudit.objects.filter(eglise=u.eglise).order_by("-created_at")[:300]
    module = (request.GET.get("module") or "").strip()
    if module:
        qs = qs.filter(module=module)
    return ok({"audits": [{"id": a.id, "module": a.module, "action": a.action,
                           "details": a.details, "ip": a.ip,
                           "utilisateur": a.utilisateur.email if a.utilisateur else "système",
                           "created_at": a.created_at.isoformat()} for a in qs]})


@csrf_exempt
@auth_requise()
def tableau_bord(request):
    u = request.utilisateur
    if not u.eglise:
        nb = Eglise.objects.count()
        return ok({"super": True, "eglises_total": nb,
                   "en_attente": Eglise.objects.filter(statut="a_completer").count()})
    e = u.eglise
    return ok({
        "super": False,
        "membres_avec_dossier": 0,  # module Membres : Phase 2
        "utilisateurs": e.utilisateurs.filter(statut="actif").count(),
        "invitations_en_attente": e.invitations.filter(utilise_le__isnull=True).count(),
        "roles": Role.objects.filter(Q(systeme=True) | Q(eglise=e)).count(),
        "essai_expire_le": e.essai_expire_le.isoformat() if e.essai_expire_le else None,
        "statut": e.statut,
        "audit_recent": [{"module": a.module, "action": a.action,
                          "created_at": a.created_at.isoformat()}
                         for a in JournalAudit.objects.filter(eglise=e)[:8]],
    })


# ───────────────────────── Super-administration ─────────────────────────

@csrf_exempt
@auth_requise(super_admin=True)
def super_eglises(request):
    d = corps(request)
    if request.method == "GET" or not d:
        eglises = [{"id": e.id, "nom": e.nom, "slug": e.slug, "pays": e.pays,
                    "ville": e.ville, "email": e.email, "statut": e.statut,
                    "utilisateurs": e.utilisateurs.count(),
                    "essai_expire_le": e.essai_expire_le.isoformat() if e.essai_expire_le else None,
                    "created_at": e.created_at.isoformat()}
                   for e in Eglise.objects.order_by("-created_at")]
        return ok({"eglises": eglises})
    action, cible_id = d.get("action"), d.get("eglise_id")
    e = Eglise.objects.filter(id=cible_id).first()
    if not e:
        return err("Église introuvable.", 404)
    transitions = {"approuver": "approuve", "refuser": "refuse", "suspendre": "suspendu",
                   "reactiver": "approuve", "prolonger_essai": None}
    if action not in transitions:
        return err("Action inconnue.")
    if action == "prolonger_essai":
        e.essai_expire_le = timezone.now() + timedelta(days=7)
    else:
        e.statut = transitions[action]
        if action == "refuser":
            e.motif = (d.get("motif") or "")[:500]
    e.save()
    tracer(request.utilisateur, "plateforme", f"eglise_{action}", f"{e.nom} → {e.statut}",
           e, ip_depuis(request))
    return ok({"eglise": _eglise_json(e)})
