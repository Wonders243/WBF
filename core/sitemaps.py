from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from core.models import Event  # adapte si modèle différent

class StaticViewSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6
    def items(self):
        return ["core:home", "core:about", "core:services", "core:events_list"]
    def location(self, item):
        return reverse(item)

class EventSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7
    def items(self):
        return Event.objects.filter(published=True)  # adapte
    def lastmod(self, obj):
        return getattr(obj, "updated_at", None)
