# WBF/core/sitemaps.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from core.models import Event, Project

class StaticViewSitemap(Sitemap):
    changefreq, priority = "monthly", 0.6
    def items(self):
        return [
            "core:accueil",
            "core:nous",
            "core:project",           # liste projets
            "core:events_list",       # liste événements
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

class ProjectSitemap(Sitemap):
    changefreq, priority = "weekly", 0.7
    def items(self):
        return Project.objects.all()
    def location(self, obj):
        return obj.get_absolute_url()

class EventSitemap(Sitemap):
    changefreq, priority = "weekly", 0.7
    def items(self):
        return Event.objects.all()
    def location(self, obj):
        return obj.get_absolute_url()

def get_sitemaps():
    return {"static": StaticViewSitemap, "projects": ProjectSitemap, "events": EventSitemap}
