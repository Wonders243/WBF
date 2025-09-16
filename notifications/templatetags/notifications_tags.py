# Crée le dossier templatetags si besoin + __init__.py vide
from django import template
from django.contrib.auth.models import AnonymousUser
from ..models import Notification

register = template.Library()

@register.inclusion_tag("notifications/_menu.html", takes_context=True)
def notifications_menu(context, limit=8):
    request = context.get("request")
    if not request or isinstance(request.user, AnonymousUser) or not request.user.is_authenticated:
        return {"items": [], "unread_count": 0, "request": request}
    qs = (Notification.objects
          .filter(recipient=request.user)
          .select_related("actor")
          .order_by("-created_at")[:limit])
    unread = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return {"items": qs, "unread_count": unread, "request": request}
