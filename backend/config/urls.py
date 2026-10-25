from pathlib import Path
from django.http import FileResponse, Http404
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.conf import settings

def serv_file(request, name):
    base = Path(settings.BASE_DIR) / "frontend"
    cible = (base / name).resolve()
    if not str(cible).startswith(str(base)) or not cible.is_file():
        raise Http404
    return FileResponse(open(cible, "rb"))

urlpatterns = [
    path("api/", include("core.urls")),
    re_path(r"^(?P<name>style\.css|logo\.png|manifest\.json)$", serv_file),
    path("app/", TemplateView.as_view(template_name="app.html")),
    path("", TemplateView.as_view(template_name="index.html")),
]
