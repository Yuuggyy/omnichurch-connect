"""Tests intervenants et bibliothèque média (section 14)."""
import json, os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client
from core.models import (Eglise, Utilisateur, Role, UserRole, TokenSession, Membre,
                         Intervenant, DisponibiliteIntervenant, InvitationIntervenant, Media, MediaVu)
from core.security import hasher

c = Client(); res = []
def post(url, payload, **h):
    return c.post(url, data=json.dumps(payload), content_type="application/json", **h)
def check(nom, cond, detail=""):
    res.append((nom, bool(cond))); print(("  ✓ " if cond else "  ✗ ") + nom + (f" — {detail}" if detail and not cond else ""))

for slug in ("test-itv-a", "test-itv-b"):
    v = Eglise.objects.filter(slug=slug).first()
    if v:
        Media.objects.filter(eglise=v).delete(); InvitationIntervenant.objects.filter(eglise=v).delete()
        Intervenant.objects.filter(eglise=v).delete(); Membre.objects.filter(eglise=v).delete(); v.delete()

e1 = Eglise.objects.create(nom="Église Intervenants A", slug="test-itv-a", statut="approuve")
e2 = Eglise.objects.create(nom="Église Intervenants B", slug="test-itv-b", statut="approuve")
adm = Utilisateur.objects.create(eglise=e1, nom_complet="Admin ITV", email="itv1@test.cd",
                                 mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
vis = Utilisateur.objects.create(eglise=e1, nom_complet="Visiteur", email="vis@test.cd",
                                 mot_de_passe=hasher("Test!2026"))
adm2 = Utilisateur.objects.create(eglise=e2, nom_complet="Admin B", email="itv2@test.cd",
                                  mot_de_passe=hasher("Test!2026"), is_admin_principal=True)
role = Role.objects.create(eglise=e1, nom="Consultation médias", permissions={
    "intervenants": ["consulter"], "mediatheque": ["consulter"]})
UserRole.objects.create(utilisateur=vis, role=role)
T, TV, TB = [TokenSession.objects.create(utilisateur=u).token for u in (adm, vis, adm2)]
H = lambda t: {"HTTP_X_AUTH_TOKEN": t}

membre = Membre.objects.create(eglise=e1, nom="Ngoy", prenom="Daniel", statut="valide")

print("── Répertoire des intervenants")
d = post("/api/intervenant/creer/", {"nom": "Pasteur Ngoy", "type": "pasteur", "organisation": "CEPAC",
        "telephone": "+243810000111", "email": "ngoy@cepac.cd", "specialites": "Enseignement, prophétie",
        "tarif": 150, "membre_id": membre.id}, **H(T)).json()
check("intervenant créé", d.get("success") is True, d)
iid = d["data"]["intervenant"]["id"]
check("rattaché au dossier membre", d["data"]["intervenant"]["membre_id"] == membre.id)
d2 = post("/api/intervenant/creer/", {"nom": "Doublon", "membre_id": membre.id}, **H(T)).json()
check("pas de doublon pour un membre déjà relié", d2["data"].get("existant") is True and d2["data"]["intervenant"]["id"] == iid)
check("nom obligatoire", post("/api/intervenant/creer/", {"type": "orateur"}, **H(T)).status_code == 400)
d = post("/api/intervenants/", {}, **H(T)).json()
check("contact visible avec droit de validation", d["data"]["intervenants"][0].get("telephone") == "+243810000111")
d = post("/api/intervenants/", {}, **H(TV)).json()
check("contact masqué pour un simple consultant", d["data"]["intervenants"][0].get("contact_restreint") is True
      and "telephone" not in d["data"]["intervenants"][0])

print("── Disponibilités et invitations")
post("/api/intervenant/disponibilite/", {"intervenant_id": iid, "date": "2026-11-15", "disponible": True}, **H(T))
d = post("/api/intervenant/inviter/", {"intervenant_id": iid, "date": "2026-11-15", "objet": "Culte du dimanche",
        "theme": "La fidélité de Dieu"}, **H(T)).json()
check("invitation proposée", d.get("success") is True, d)
inv = d["data"]["invitation"]["id"]
post("/api/intervenant/disponibilite/", {"intervenant_id": iid, "date": "2026-11-22", "disponible": False}, **H(T))
d = post("/api/intervenant/inviter/", {"intervenant_id": iid, "date": "2026-11-22"}, **H(T)).json()
check("invitation refusée à une date d'indisponibilité", d.get("success") is False and "indisponible" in d.get("error",""))
d = post("/api/invitation/statut/", {"id": inv, "statut": "confirmee"}, **H(T)).json()
check("invitation confirmée", d["data"]["invitation"]["statut"] == "confirmee")
check("statut inconnu refusé", post("/api/invitation/statut/", {"id": inv, "statut": "peut_etre"}, **H(T)).status_code == 400)
d = post("/api/intervenants/invitations/", {}, **H(T)).json()
check("invitation listée", d["data"]["total"] == 1, d["data"])

print("── Bibliothèque média")
d = post("/api/media/creer/", {"titre": "La foi qui déplace", "type": "audio", "categorie": "predication",
        "intervenant_id": iid, "date": "2026-11-15", "serie": "Foi vivante", "reference_biblique": "Hébreux 11",
        "duree_minutes": 42, "url": "https://cdn.exemple.cd/foi.mp3"}, **H(T)).json()
check("média créé", d.get("success") is True, d)
mid = d["data"]["media"]["id"]
check("titre obligatoire", post("/api/media/creer/", {"url": "x"}, **H(T)).status_code == 400)
check("lien obligatoire", post("/api/media/creer/", {"titre": "Sans fichier"}, **H(T)).status_code == 400)
d = post("/api/mediatheque/", {}, **H(T)).json()
check("média listé avec série", d["data"]["medias"][0]["serie"] == "Foi vivante" and d["data"]["medias"][0]["intervenant"] == "Pasteur Ngoy")
d = post("/api/media/ecouter/", {"id": mid}, **H(T))
check("diffusion bloquée sans autorisation", d.status_code == 403, d.status_code)
post("/api/media/modifier/", {"id": mid, "diffusion_autorisee": True, "transcription": "Texte complet"},
     **H(T))
d = post("/api/media/ecouter/", {"id": mid}, **H(T)).json()
check("lecture autorisée après validation de licence", d.get("success") is True and d["data"]["url"].endswith("foi.mp3"), d)
check("écoute comptée", MediaVu.objects.filter(media_id=mid).count() == 1)
d = post("/api/mediatheque/", {"q": "Hébreux"}, **H(T)).json()
check("recherche par référence biblique", d["data"]["total"] == 1)
d = post("/api/mediatheque/", {"categorie": "chant"}, **H(T)).json()
check("filtre par catégorie", d["data"]["total"] == 0)

print("── Tableau de bord, isolation, permissions")
d = post("/api/intervenants/bord/", {}, **H(T)).json()["data"]
check("tableau de bord intervenants", d["intervenants"] == 1 and d["medias"] == 1, d)
check("médias sans licence comptés", d["sans_licence"] == 0, d)
check("Église B ne voit aucun intervenant", post("/api/intervenants/", {}, **H(TB)).json()["data"]["total"] == 0)
check("Église B ne voit aucun média", post("/api/mediatheque/", {}, **H(TB)).json()["data"]["total"] == 0)
check("Église B ne peut pas modifier", post("/api/intervenant/modifier/", {"id": iid, "nom": "X"}, **H(TB)).status_code == 404)
check("consultant ne crée pas de média", post("/api/media/creer/", {"titre": "X", "url": "y"}, **H(TV)).status_code == 403)
check("consultant lit les médias", post("/api/mediatheque/", {}, **H(TV)).json().get("success") is True)
check("sans jeton refusé", post("/api/intervenants/", {}).status_code == 401)

print("\n" + "=" * 54)
ok_n = sum(1 for _, v in res if v)
print(f"{ok_n}/{len(res)} tests réussis")
for n, v in res:
    if not v: print("  -", n)
