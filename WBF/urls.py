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
    return HttpResponseRedirect(f"{settings.MEDIA_URL}{prefix}/{path}")

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

# Servez les médias depuis le FS Bucket monté.
# En prod, c’est acceptable sur Clever pour un volume modéré.
if getattr(settings, "SERVE_MEDIA", False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)