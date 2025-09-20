# core/context_processors.py
from django.urls import reverse
from staff.models import VolunteerApplication, ApplicationStatus
from core.models import News

def volunteer_cta(request):
    if not request.user.is_authenticated:
        return {
            "volunteer_cta": {
                "label": "Devenir bénévole",
                "href": reverse("account_signup"),
                "variant": "primary",
                "badge": None,
            }
        }

    user = request.user
    # déjà bénévole ?
    try:
        v = user.volunteer
        if hasattr(v, "status"):
            if v.status == "approved":
                return {"volunteer_cta": {"label": "Espace bénévole", "href": reverse("benevoles:dashboard"), "variant": "muted", "badge": None}}
        else:
            return {"volunteer_cta": {"label": "Espace bénévole", "href": reverse("benevoles:dashboard"), "variant": "muted", "badge": None}}
    except Exception:
        pass

    last_app = VolunteerApplication.objects.filter(user=user).order_by("-submitted_at").first()
    if last_app and last_app.status in [ApplicationStatus.PENDING, ApplicationStatus.NEEDS_CHANGES]:
        return {
            "volunteer_cta": {
                "label": "Compléter ma candidature" if last_app.status == ApplicationStatus.NEEDS_CHANGES else "Voir ma candidature",
                "href": reverse("benevoles:application_detail", kwargs={"pk": last_app.pk}),
                "variant": "primary",
                "badge": "À corriger" if last_app.status == ApplicationStatus.NEEDS_CHANGES else "En attente",
            }
        }
    if last_app and last_app.status == ApplicationStatus.APPROVED:
        return {"volunteer_cta": {"label": "Espace bénévole", "href": reverse("benevoles:dashboard"), "variant": "muted", "badge": None}}

    return {"volunteer_cta": {"label": "Devenir bénévole", "href": reverse("staff:application_start"), "variant": "primary", "badge": None}}


from django.conf import settings

def flags(request):
    return {
        "PAYMENT_MAINTENANCE": getattr(settings, "PAYMENT_MAINTENANCE", False),
        "SUPPORT_EMAIL": getattr(settings, "SUPPORT_EMAIL", ""),
    }


def latest_news(request):
    """Expose a small list of recent news site-wide.

    Kept lightweight (max 6 items) and used by the public base template
    to render the small carousel of actualités.
    """
    try:
        items = list(News.objects.all()[:6])
    except Exception:
        items = []
    return {"latest_news": items}


def staff_counters(request):
    """Small counters for staff header/sidebar badges.

    Currently exposes pending volunteer applications count.
    Only computed for authenticated staff users.
    """
    try:
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated and user.is_staff):
            return {}
        pending_apps = VolunteerApplication.objects.filter(status=ApplicationStatus.PENDING).count()
        return {"staff_pending_applications": pending_apps}
    except Exception:
        return {}
