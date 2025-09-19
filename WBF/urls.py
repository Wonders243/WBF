"""
URL configuration for WBF project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponseRedirect
from django.views.generic import TemplateView
from accounts.views import post_login_redirect

# SEO: sitemap.xml
from django.contrib.sitemaps.views import sitemap
try:
    # Utilise la fabrique proposée (core/sitemaps.py -> get_sitemaps)
    from core.sitemaps import get_sitemaps
    sitemaps = get_sitemaps()
except Exception:
    # Fallback si le module n'est pas encore créé
    sitemaps = {}


def _legacy_media_redirect(request, prefix: str, path: str):
    """
    Redirect old media paths without MEDIA_URL prefix to the correct URL.

    Example: /user_documents/... -> /media/user_documents/...
             /applications/...   -> /media/applications/...
    """
    base = (settings.MEDIA_URL or "/media/").rstrip("/")
    return HttpResponseRedirect(f"{base}/{prefix}/{path}")


urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Auth / comptes
    path("accounts/", include("allauth.urls")),
    path("accounts/", include(("accounts.urls", "benevoles"), namespace="benevoles")),
    path("accounts/redirect/", post_login_redirect, name="post_login_redirect"),

    # Apps projet
    path("notifications/", include(("notifications.urls", "notifications"), namespace="notifications")),
    path("", include(("core.urls", "core"), namespace="core")),
    path("staff/", include(("staff.urls", "staff"), namespace="staff")),
    path("", include(("legal.urls", "legal"), namespace="legal")),
    path("pay/", include(("payments.urls", "payments"), namespace="payments")),

    # SEO
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
        name="robots",
    ),
]

# Outils dev
if settings.DEBUG:
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]

# ── Redirects Legacy (ACTIVÉS) ────────────────────────────────────────────────
# Ex : anciens liens "/user_documents/xyz.jpg" → redirigent vers "/media/user_documents/xyz.jpg"
urlpatterns += [
    re_path(r"^user_documents/(?P<path>.+)$",
            lambda r, path: _legacy_media_redirect(r, "user_documents", path)),
    re_path(r"^applications/(?P<path>.+)$",
            lambda r, path: _legacy_media_redirect(r, "applications", path)),
]

# ── Service des médias depuis FS Bucket monté ────────────────────────────────
# Acceptable en prod pour volumétrie modérée ; sinon, prévoir un frontal/CDN plus tard.
if getattr(settings, "SERVE_MEDIA", False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# ➜ Autoriser Django à servir /media/ en production quand on le demande
if settings.DEBUG or getattr(settings, "SERVE_MEDIA", False):
    from django.views.static import serve
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]

from core.views_media_test import media_write_test, media_ls
urlpatterns += [
    path("__media_test__/write", media_write_test),
    path("__media_test__/ls", media_ls),
]
# Permet de tester que l'écriture dans MEDIA_ROOT fonctionne (FS Bucket monté)
