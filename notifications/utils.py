from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.urls import reverse

from .models import Notification


def safe_url_for(obj):
    # 1) Priorité au get_absolute_url (gère slug/PK selon ton URLconf)
    if hasattr(obj, "get_absolute_url"):
        try:
            return obj.get_absolute_url()
        except Exception:
            pass

    # 2) Fallbacks explicites si besoin (adaptés à tes names)
    try:
        from core.models import Project, Event
        from staff.models import Mission, VolunteerApplication
        if isinstance(obj, Event):
            try:
                return reverse("event_detail", kwargs={"slug": obj.slug})
            except Exception:
                return reverse("core:event_detail", kwargs={"slug": obj.slug})
        if isinstance(obj, Project):
            try:
                return reverse("project_detail", kwargs={"slug": obj.slug})
            except Exception:
                return reverse("core:project_detail", kwargs={"slug": obj.slug})
        if isinstance(obj, Mission):
            return reverse("staff:mission_detail", kwargs={"pk": obj.pk})
    except Exception:
        pass
    return ""


def url_for_recipient(target, user):
    """
    Construit un lien adapté au destinataire (staff vs bénévole).
    """
    # 1) Si l'objet a un get_absolute_url, l'utiliser
    if hasattr(target, "get_absolute_url"):
        try:
            return target.get_absolute_url()
        except Exception:
            pass

    # 2) Sinon, bascule selon le type + rôle
    try:
        from core.models import Project, Event
        from staff.models import Mission
        from accounts.models import UserDocument

        # Public: événements / projets
        if isinstance(target, Event):
            try:
                return reverse("event_detail", kwargs={"slug": target.slug})
            except Exception:
                return reverse("core:event_detail", kwargs={"slug": target.slug})
        if isinstance(target, Project):
            try:
                return reverse("project_detail", kwargs={"slug": target.slug})
            except Exception:
                return reverse("core:project_detail", kwargs={"slug": target.slug})

        # Missions: staff -> détail staff; bénévole -> page missions
        if isinstance(target, Mission):
            if getattr(user, "is_staff", False):
                return reverse("staff:mission_detail", kwargs={"pk": target.pk})
            return reverse("benevoles:missions_browse")

        # Documents utilisateur: page bénévole des documents
        if isinstance(target, UserDocument):
            return reverse("benevoles:UserDocuments_list")

        # Candidature bénévole: staff -> page de revue; bénévole -> get_absolute_url (déjà géré plus haut)
        if isinstance(target, VolunteerApplication) and getattr(user, "is_staff", False):
            return reverse("staff:application_review", kwargs={"pk": target.pk})
    except Exception:
        pass

    # 3) Fallback neutre
    return ""


def recipients_for(obj):
    """
    DǸtermine qui re��oit la notif. �? ajuster selon ta logique:
    - Staff (TeamMember) pour tout
    - + Ǹventuellement watchers, inscrits, etc.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # Exemple : tous les membres d�?TǸquipe actifs (via TeamMember.user)
    try:
        from core.models import TeamMember  # ou staff.models selon ton projet
        staff_user_ids = TeamMember.objects.values_list("user_id", flat=True)
        qs = User.objects.filter(id__in=staff_user_ids, is_active=True)
    except Exception:
        qs = User.objects.filter(is_staff=True, is_active=True)

    # TODO: Ǹtendre selon le type d�?Tobjet (ex: pour Mission publiǸe -> bǸnǸvoles, inscrits, watchers...)
    return qs.distinct()


def send_notification(*, recipients, actor, verb, target, title="", message=""):
    if not recipients:
        return
    ctype = ContentType.objects.get_for_model(target.__class__)
    payload = []
    for u in recipients:
        # Ǹvite d�?Tauto-notifier l�?Tauteur
        if actor is not None and u.pk == getattr(actor, "pk", None):
            continue
        url = url_for_recipient(target, u) or safe_url_for(target)
        payload.append(
            Notification(
                recipient=u,
                actor=actor,
                verb=verb,
                target_content_type=ctype,
                target_object_id=target.pk,
                title=title,
                message=message,
                url=url,
            )
        )
    # �%vite la notif avant commit DB :
    if payload:
        transaction.on_commit(lambda: Notification.objects.bulk_create(payload))
