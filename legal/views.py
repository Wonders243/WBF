from django.http import Http404, JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import LegalDocument, LegalVersion, LegalAcceptance

def _doc_by(key, locale="fr"):
    doc = get_object_or_404(LegalDocument, key=key, locale=locale)
    ver = doc.current_version()
    if not ver:
        raise Http404("Aucune version publiée.")
    return doc, ver

def privacy(request):  return detail(request, "privacy")
def terms(request):    return detail(request, "terms")
def cookies(request):  return detail(request, "cookies")
def imprint(request):  return detail(request, "imprint")

def detail(request, key, locale="fr"):
    doc, ver = _doc_by(key, locale)
    # Dernières versions (historique court)
    history = doc.versions.filter(status="published").order_by("-effective_date","-published_at")[:5]
    accepted = False
    if request.user.is_authenticated:
        accepted = LegalAcceptance.objects.filter(user=request.user, document=doc, version=ver).exists()
    return render(request, "legal/detail.html", {"doc": doc, "ver": ver, "history": history, "accepted": accepted})

def history(request, key, locale="fr"):
    doc = get_object_or_404(LegalDocument, key=key, locale=locale)
    versions = doc.versions.all()
    return render(request, "legal/history.html", {"doc": doc, "versions": versions})

def api_current(request, key, locale="fr"):
    doc, ver = _doc_by(key, locale)
    return JsonResponse({
        "key": doc.key,
        "locale": doc.locale,
        "title": doc.title,
        "version": ver.version,
        "effective_date": ver.effective_date.isoformat() if ver.effective_date else None,
        "published_at": ver.published_at.isoformat() if ver.published_at else None,
        "change_log": ver.change_log,
        "body_html": ver.body_html,  # utile pour client mobile ou CMS externe
    })

@login_required
@require_POST
def accept(request, key, locale="fr"):
    doc, ver = _doc_by(key, locale)
    ip = request.META.get("REMOTE_ADDR")
    ua = request.META.get("HTTP_USER_AGENT", "")
    LegalAcceptance.objects.get_or_create(user=request.user, document=doc, version=ver,
                                          defaults={"ip": ip, "user_agent": ua})
    return JsonResponse({"ok": True, "accepted_version": ver.version, "ts": timezone.now().isoformat()})

def preview_version(request, key, version, locale="fr"):
    doc = get_object_or_404(LegalDocument, key=key, locale=locale)
    ver = get_object_or_404(LegalVersion, document=doc, version=version)
    if not request.user.is_staff:
        raise Http404()
    return render(request, "legal/detail.html", {"doc": doc, "ver": ver, "history": [], "accepted": False})
