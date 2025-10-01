# WBF/core/sitemaps.py
from django.contrib.sitemaps import Sitemap
from django.conf import settings

from django.urls import reverse
from core.models import Event, Project

DEFAULT_PROTOCOL = "https" if getattr(settings, "USE_HTTPS", False) else "http"


class BaseWBFSitemap(Sitemap):
    """Common sitemap defaults (protocol, etc.)."""
    protocol = DEFAULT_PROTOCOL


class StaticViewSitemap(BaseWBFSitemap):
    changefreq, priority = "monthly", 0.6
    def items(self):
        return [
            "core:accueil",
            "core:nous",
            "core:project",           # liste projets
            "core:events_list",       # liste evenements
            "core:don",
            "core:contact",
            "core:service_education_orphelins",
            "core:service_sante",
            "core:service_psy",
            "legal:privacy",
            "legal:terms",
            "legal:cookies",
            "legal:imprint",
        ]
    def location(self, item):
        return reverse(item)

class ProjectSitemap(BaseWBFSitemap):
    changefreq, priority = "weekly", 0.7
    def items(self):
        return Project.objects.order_by("title")
    def location(self, obj):
        return obj.get_absolute_url()

class EventSitemap(BaseWBFSitemap):
    changefreq, priority = "weekly", 0.7
    def items(self):
        return Event.objects.order_by("-date")
    def location(self, obj):
        return obj.get_absolute_url()



def get_sitemaps():
    """Return the sitemap registry used by the project-level URLconf."""
    return {
        "static": StaticViewSitemap,
        "projects": ProjectSitemap,
        "events": EventSitemap,
    }
