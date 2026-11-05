"""Documents et actes officiels (section 17) : numérotation, versions, expiration, PDF."""
import csv
import io
from datetime import date, timedelta

from django.db.models import Q
from django.http import HttpResponse

from core.models import (Eglise, Membre, ModeleDocument, Document, DocumentVersion, Utilisateur)
from core.security import auth_requise, permission_requise, tracer
from core.views_api import ok, err, corps

PREFIXES = {
    "certificat_bapteme": "BAP", "certificat_mariage": "MAR", "attestation_ordination": "ORD",
    "certificat_consecration": "CON", "attestation_transfert": "TRA",
    "attestation_formation": "FOR", "carte_membre": "CAR", "attestation_presence": "PRE",
    "pv": "PV", "rapport": "RAP", "interne": "INT", "formulaire": "FRM",
}

CORPS_DEFAUT = {
    "certificat_bapteme": "Nous certifions que {{nom_complet}}, matricule {{matricule}}, membre de {{eglise}}, "
        "a reçu le baptême le {{date_emission}}, conformément à la doctrine de l'Église.",
    "certificat_mariage": "Nous certifions que {{nom_complet}}, matricule {{matricule}}, a contracté mariage "
        "devant l'Église {{eglise}} le {{date_emission}}.",
    "attestation_transfert": "Nous attestons que {{nom_complet}}, matricule {{matricule}}, est membre de {{eglise}} "
        "et qu'aucune objection ne s'oppose à son transfert.",
    "attestation_formation": "Nous attestons que {{nom_complet}} a suivi et achevé la formation dispensée par {{eglise}}.",
    "pv": "Procès-verbal de la réunion tenue le {{date_emission}} à {{eglise}}.",
}


def _eglise(request):
    return request.utilisateur.eglise


def _date(v):
    if not v:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _numero(e, type_doc):
    prefixe = PREFIXES.get(type_doc, "DOC")
    annee = date.today().year
    debut = f"{prefixe}-{annee}-"
    n = 1
    while Document.objects.filter(eglise=e, numero=f"{debut}{n:05d}").exists():
        n += 1
    return f"{debut}{n:05d}"


def _rendre(corps_texte, enfant_doc, user):
    """Remplace les variables du modèle par les données réelles."""
    m = enfant_doc.membre
    valeurs = {
        "nom_complet": " ".join(x for x in [m.nom, m.postnom, m.prenom] if x) if m else "—",
        "nom": m.nom if m else "—", "prenom": m.prenom if m else "",
        "matricule": (m.matricule if m else "") or "—",
        "eglise": enfant_doc.eglise.nom, "ville": enfant_doc.eglise.ville,
        "date_emission": (enfant_doc.date_emission or date.today()).strftime("%d/%m/%Y"),
        "date_expiration": enfant_doc.date_expiration.strftime("%d/%m/%Y") if enfant_doc.date_expiration else "—",
        "numero": enfant_doc.numero, "titre": enfant_doc.titre,
        "auteur": user.nom_complet if user else "",
    }
    texte = corps_texte or ""
    for cle, val in valeurs.items():
        texte = texte.replace("{{" + cle + "}}", str(val))
    return texte


def _json_doc(d):
    return {"id": d.id, "numero": d.numero, "type": d.type, "titre": d.titre,
            "statut": d.statut, "version": d.version,
            "membre": f"{d.membre.nom} {d.membre.prenom or ''}".strip() if d.membre_id else "",
            "membre_id": d.membre_id,
            "date_emission": d.date_emission.isoformat() if d.date_emission else None,
            "date_expiration": d.date_expiration.isoformat() if d.date_expiration else None,
            "expire_bientot": d.expire_bientot(),
            "fichier_url": d.fichier_url, "created_at": d.created_at.isoformat()[:10]}


# ─────────────── modèles ───────────────

@auth_requise()
@permission_requise("documents", "consulter")
def modeles_liste(request):
    e = _eglise(request)
    qs = ModeleDocument.objects.filter(Q(eglise=e) | Q(eglise__isnull=True), actif=True)
    return ok({"modeles": [{"id": m.id, "nom": m.nom, "type": m.type,
                            "jours_alerte": m.jours_alerte,
                            "systeme": m.eglise_id is None,
                            "apercu": (m.corps or "")[:160]} for m in qs],
               "types": [{"code": c, "libelle": l} for c, l in ModeleDocument.TYPES]})


@auth_requise()
@permission_requise("documents", "creer")
def modele_creer(request):
    e = _eglise(request)
    d = corps(request)
    if not (d.get("nom") or "").strip():
        return err("Le nom du modèle est obligatoire.")
    if d.get("type") not in dict(ModeleDocument.TYPES):
        return err("Type de document inconnu.")
    m = ModeleDocument.objects.create(eglise=e, nom=d["nom"].strip(), type=d["type"],
                                      corps=d.get("corps") or CORPS_DEFAUT.get(d["type"], ""),
                                      jours_alerte=int(d.get("jours_alerte") or 30))
    tracer(request.utilisateur, "documents", "creer_modele", f"Modèle créé : {m.nom}")
    return ok({"modele": {"id": m.id, "nom": m.nom}})


# ─────────────── documents ───────────────

@auth_requise()
@permission_requise("documents", "consulter")
def documents_liste(request):
    e = _eglise(request)
    d = corps(request)
    qs = Document.objects.filter(eglise=e).select_related("membre", "modele")
    if d.get("type"):
        qs = qs.filter(type=d["type"])
    if d.get("statut"):
        qs = qs.filter(statut=d["statut"])
    if d.get("membre_id"):
        qs = qs.filter(membre_id=d["membre_id"])
    if d.get("expirant"):
        limite = date.today() + timedelta(days=int(d.get("jours") or 30))
        qs = qs.filter(date_expiration__gte=date.today(), date_expiration__lte=limite)
    q = (d.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(numero__icontains=q) | Q(titre__icontains=q) | Q(contenu__icontains=q)
                       | Q(membre__nom__icontains=q))
    return ok({"documents": [_json_doc(x) for x in qs[:150]], "total": qs.count()})


@auth_requise()
@permission_requise("documents", "consulter")
def document_detail(request):
    e = _eglise(request)
    d = corps(request)
    doc = Document.objects.filter(eglise=e, id=d.get("id")).first()
    if not doc:
        return err("Document introuvable.", 404)
    base = _json_doc(doc)
    base["contenu"] = doc.contenu
    base["versions"] = [{"version": v.version, "motif": v.motif,
                         "date": v.created_at.isoformat()[:16],
                         "auteur": v.auteur.nom_complet if v.auteur_id else ""}
                        for v in doc.versions.all()[:20]]
    base["modele"] = doc.modele.nom if doc.modele_id else ""
    return ok({"document": base})


@auth_requise()
@permission_requise("documents", "creer")
def document_generer(request):
    e = _eglise(request)
    d = corps(request)
    type_doc = d.get("type")
    if type_doc not in dict(ModeleDocument.TYPES):
        return err("Type de document inconnu.")
    membre = None
    if d.get("membre_id"):
        membre = Membre.objects.filter(eglise=e, id=d["membre_id"]).first()
        if not membre:
            return err("Ce membre n'appartient pas à votre Église.")
    modele = None
    if d.get("modele_id"):
        modele = ModeleDocument.objects.filter(Q(eglise=e) | Q(eglise__isnull=True),
                                               id=d["modele_id"]).first()
        if not modele:
            return err("Modèle introuvable.")
    if not membre and type_doc in ("certificat_bapteme", "certificat_mariage", "attestation_ordination",
                                   "certificat_consecration", "attestation_transfert",
                                   "attestation_formation", "carte_membre"):
        return err("Indiquez le membre concerné : un acte nominatif ne peut pas être généré sans identité.")
    if not membre and not d.get("titre"):
        return err("Indiquez un membre ou un titre pour ce document.")
    doc = Document(eglise=e, numero=_numero(e, type_doc), type=type_doc, modele=modele,
                   membre=membre, titre=d.get("titre") or (modele.nom if modele else
                                                           dict(ModeleDocument.TYPES)[type_doc]),
                   date_emission=_date(d.get("date_emission")) or date.today(),
                   date_expiration=_date(d.get("date_expiration")),
                   auteur=request.utilisateur, fichier_url=d.get("fichier_url", ""))
    corps_texte = (modele.corps if modele else "") or CORPS_DEFAUT.get(type_doc, "")
    doc.contenu = _rendre(corps_texte, doc, request.utilisateur)
    doc.save()
    DocumentVersion.objects.create(document=doc, version=1, contenu=doc.contenu,
                                   motif="Création", auteur=request.utilisateur)
    tracer(request.utilisateur, "documents", "generer", f"Document {doc.numero} généré")
    return ok({"document": _json_doc(doc)})


@auth_requise()
@permission_requise("documents", "modifier")
def document_reediter(request):
    """Réédition : nouvelle version conservée dans l'historique, l'ancienne reste lisible."""
    e = _eglise(request)
    d = corps(request)
    doc = Document.objects.filter(eglise=e, id=d.get("id")).first()
    if not doc:
        return err("Document introuvable.", 404)
    if doc.statut == "archive":
        return err("Un document archivé ne peut plus être réédité.")
    doc.version += 1
    if "contenu" in d:
        doc.contenu = d["contenu"] or doc.contenu
    if "titre" in d:
        doc.titre = d["titre"]
    if "date_expiration" in d:
        doc.date_expiration = _date(d["date_expiration"])
    doc.statut = "brouillon" if doc.statut == "valide" else doc.statut
    doc.save()
    DocumentVersion.objects.create(document=doc, version=doc.version, contenu=doc.contenu,
                                   motif=d.get("motif") or "Réédition", auteur=request.utilisateur)
    tracer(request.utilisateur, "documents", "reediter", f"{doc.numero} réédité en v{doc.version}")
    return ok({"document": _json_doc(doc)})


@auth_requise()
@permission_requise("documents", "valider")
def document_statut(request):
    e = _eglise(request)
    d = corps(request)
    doc = Document.objects.filter(eglise=e, id=d.get("id")).first()
    if not doc:
        return err("Document introuvable.", 404)
    statut = d.get("statut")
    if statut not in dict(Document.STATUTS):
        return err("Statut inconnu.")
    doc.statut = statut
    doc.save(update_fields=["statut", "updated_at"])
    tracer(request.utilisateur, "documents", "statut", f"{doc.numero} : {statut}")
    return ok({"document": _json_doc(doc)})


@auth_requise()
@permission_requise("documents", "consulter")
def document_pdf(request):
    """Acte officiel en PDF, avec l'identité visuelle de l'Église."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from core.views_membres import _pdf_entete

    e = _eglise(request)
    doc = Document.objects.filter(eglise=e, id=request.GET.get("id")).first()
    if not doc:
        return err("Document introuvable.", 404)
    bleu, or_ = _pdf_entete(e)
    tampon = io.BytesIO()
    c = canvas.Canvas(tampon, pagesize=A4)
    L, H = A4
    c.setFillColor(bleu)
    c.rect(0, H - 34 * mm, L, 34 * mm, stroke=0, fill=1)
    c.setFillColor(or_)
    c.rect(0, H - 36 * mm, L, 2 * mm, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, H - 17 * mm, e.nom[:58])
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, H - 23 * mm, f"{e.denomination or 'Église'} · {e.ville}")
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(L - 20 * mm, H - 17 * mm, dict(ModeleDocument.TYPES).get(doc.type, "DOCUMENT").upper()[:40])
    c.drawRightString(L - 20 * mm, H - 22 * mm, doc.numero)

    c.setFillColor(HexColor("#111111"))
    c.setFont("Helvetica-Bold", 15)
    c.drawString(20 * mm, H - 55 * mm, doc.titre[:70])
    c.setFont("Helvetica", 11)
    texte = doc.contenu or ""
    y = H - 70 * mm
    for ligne in texte.split("\n"):
        mots, courant = ligne.split(" "), ""
        for mot in mots:
            essai = (courant + " " + mot).strip()
            if c.stringWidth(essai, "Helvetica", 11) > L - 40 * mm:
                c.drawString(20 * mm, y, courant)
                y -= 6 * mm
                courant = mot
                if y < 40 * mm:
                    c.showPage()
                    y = H - 30 * mm
                    c.setFont("Helvetica", 11)
            else:
                courant = essai
        c.drawString(20 * mm, y, courant)
        y -= 7 * mm

    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#555555"))
    c.drawString(20 * mm, 30 * mm, f"Émis le {doc.date_emission.strftime('%d/%m/%Y') if doc.date_emission else '—'}"
                                   f" · version {doc.version}")
    if doc.date_expiration:
        c.drawString(20 * mm, 25 * mm, f"Valable jusqu'au {doc.date_expiration.strftime('%d/%m/%Y')}")
    c.setStrokeColor(HexColor("#999999"))
    c.line(L - 80 * mm, 30 * mm, L - 20 * mm, 30 * mm)
    c.drawCentredString(L - 50 * mm, 25 * mm, "Signature et sceau")
    c.showPage()
    c.save()
    reponse = HttpResponse(tampon.getvalue(), content_type="application/pdf")
    reponse["Content-Disposition"] = f'inline; filename="{doc.numero}.pdf"'
    tracer(request.utilisateur, "documents", "imprimer", f"PDF de {doc.numero}")
    return reponse


@auth_requise()
@permission_requise("documents", "exporter")
def documents_export(request):
    e = _eglise(request)
    reponse = HttpResponse(content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = 'attachment; filename="documents.csv"'
    reponse.write("\ufeff")
    w = csv.writer(reponse, delimiter=";")
    w.writerow(["Numéro", "Type", "Titre", "Membre", "Version", "Statut", "Émis le", "Expire le"])
    for doc in Document.objects.filter(eglise=e).select_related("membre"):
        w.writerow([doc.numero, doc.get_type_display(), doc.titre,
                    f"{doc.membre.nom} {doc.membre.prenom or ''}".strip() if doc.membre_id else "",
                    doc.version, doc.statut, doc.date_emission or "", doc.date_expiration or ""])
    tracer(request.utilisateur, "documents", "exporter", "Export CSV des documents")
    return reponse


@auth_requise()
@permission_requise("documents", "consulter")
def documents_bord(request):
    e = _eglise(request)
    qs = Document.objects.filter(eglise=e)
    limite = date.today() + timedelta(days=30)
    expirants = qs.filter(date_expiration__gte=date.today(), date_expiration__lte=limite)
    return ok({"total": qs.count(),
               "valides": qs.filter(statut="valide").count(),
               "brouillons": qs.filter(statut="brouillon").count(),
               "archives": qs.filter(statut="archive").count(),
               "expirant_30j": expirants.count(),
               "expires": qs.filter(date_expiration__lt=date.today()).exclude(statut="archive").count(),
               "par_type": list(qs.values("type").annotate(n=__import__("django.db.models", fromlist=["Count"]).Count("id")).order_by("-n")[:8]),
               "prochains": [_json_doc(x) for x in expirants.order_by("date_expiration")[:6]]})


@auth_requise()
@permission_requise("documents", "consulter")
def document_verifier(request):
    """Contrôle public d'authenticité d'un acte par son numéro."""
    numero = (corps(request).get("numero") or "").strip().upper()
    if not numero:
        return err("Indiquez un numéro de document.")
    doc = Document.objects.filter(numero=numero).select_related("eglise", "membre").first()
    if not doc:
        return ok({"trouve": False})
    return ok({"trouve": True, "numero": doc.numero, "type": doc.get_type_display(),
               "titre": doc.titre, "eglise": doc.eglise.nom, "statut": doc.statut,
               "version": doc.version,
               "date_emission": doc.date_emission.isoformat() if doc.date_emission else None})
