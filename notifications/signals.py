from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.forms.models import model_to_dict
from django.conf import settings
from django.core.mail import send_mail

from .utils import send_notification, recipients_for
from .models import Notification
from core.middleware import get_current_user

# Observed models
from core.models import Project, Event
from staff.models import Mission, MissionSignup, VolunteerApplication
from accounts.models import UserDocument


WATCHED_FIELDS = {
    Project: ["title", "status", "start_date", "end_date", "location"],
    Event: ["title", "status", "start_date", "end_date", "location"],
    Mission: ["title", "status", "start_date", "end_date", "location"],
    MissionSignup: ["status"],
    UserDocument: ["status"],
    VolunteerApplication: ["status"],
}


def _snapshot(instance):
    fields = WATCHED_FIELDS.get(instance.__class__, [])
    data = model_to_dict(instance, fields=fields)
    return {k: (str(v) if v is not None else "") for k, v in data.items()}


@receiver(pre_save, sender=Project)
@receiver(pre_save, sender=Event)
@receiver(pre_save, sender=Mission)
@receiver(pre_save, sender=MissionSignup)
@receiver(pre_save, sender=UserDocument)
@receiver(pre_save, sender=VolunteerApplication)
def _capture_changes(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            old_snap = _snapshot(old)
            new_snap = _snapshot(instance)
            diff = {k: {"old": old_snap[k], "new": new_snap[k]} for k in new_snap if old_snap.get(k) != new_snap.get(k)}
            setattr(instance, "_pending_changes", diff)
        except sender.DoesNotExist:
            setattr(instance, "_pending_changes", {})
    else:
        setattr(instance, "_pending_changes", {})


@receiver(post_save, sender=Project)
@receiver(post_save, sender=Event)
@receiver(post_save, sender=Mission)
def _notify_create_update(sender, instance, created, **kwargs):
    actor = get_current_user()
    recipients = list(recipients_for(instance))

    if created:
        title = f"{sender.__name__} créé"
        message = getattr(instance, "title", str(instance)) or str(instance)
        send_notification(
            recipients=recipients,
            actor=actor,
            verb=Notification.Verb.CREATED,
            target=instance,
            title=title,
            message=message,
        )
    else:
        changes = getattr(instance, "_pending_changes", {}) or {}
        if changes:
            changed_keys = ", ".join(changes.keys())
            title = f"{sender.__name__} modifié"
            message = f"Changements: {changed_keys}"
            send_notification(
                recipients=recipients,
                actor=actor,
                verb=Notification.Verb.UPDATED,
                target=instance,
                title=title,
                message=message,
            )


@receiver(post_save, sender=MissionSignup)
def _notify_signup(sender, instance: MissionSignup, created, **kwargs):
    actor = get_current_user()
    u = getattr(getattr(instance, "volunteer", None), "user", None)
    if not u:
        return
    title = getattr(getattr(instance, "mission", None), "title", "Mission") or "Mission"
    if created:
        msg = f"Invitation à la mission: {title}" if getattr(instance, "status", None) == getattr(MissionSignup.Status, "INVITED", "invited") else f"Inscription créée: {title}"
        send_notification(
            recipients=[u],
            actor=actor,
            verb=Notification.Verb.CREATED,
            target=getattr(instance, "mission", instance),
            title=msg,
            message="",
        )
        # Notify staff if the action was initiated by a volunteer (not staff)
        if not getattr(actor, "is_staff", False):
            staff = list(recipients_for(getattr(instance, "mission", instance)))
            if staff:
                send_notification(
                    recipients=staff,
                    actor=actor,
                    verb=Notification.Verb.CREATED,
                    target=getattr(instance, "mission", instance),
                    title="Nouvelle inscription a une mission",
                    message=f"{getattr(u, 'get_full_name', lambda: u.username)()} sur '{title}'",
                )
    else:
        changes = getattr(instance, "_pending_changes", {}) or {}
        if "status" in changes:
            new = changes["status"].get("new")
            labels = {
                getattr(MissionSignup.Status, "ACCEPTED", "accepted"): "acceptée",
                getattr(MissionSignup.Status, "DECLINED", "declined"): "refusée",
                getattr(MissionSignup.Status, "CANCELLED", "cancelled"): "annulée",
                getattr(MissionSignup.Status, "PENDING", "pending"): "en attente",
                getattr(MissionSignup.Status, "INVITED", "invited"): "invitée",
            }
            label = labels.get(new, str(new))
            msg = f"Votre statut de mission a changé: {label}"
            send_notification(
                recipients=[u],
                actor=actor,
                verb=Notification.Verb.UPDATED,
                target=getattr(instance, "mission", instance),
                title=msg,
                message="",
            )
            if not getattr(actor, "is_staff", False):
                staff = list(recipients_for(getattr(instance, "mission", instance)))
                if staff:
                    send_notification(
                        recipients=staff,
                        actor=actor,
                        verb=Notification.Verb.UPDATED,
                        target=getattr(instance, "mission", instance),
                        title=f"Statut d'inscription modifie ({label})",
                        message=f"{getattr(u, 'get_full_name', lambda: u.username)()} sur '{title}'",
                    )


@receiver(post_save, sender=UserDocument)
def _notify_document(sender, instance: UserDocument, created, **kwargs):
    actor = get_current_user()
    if created:
        # Volunteer uploaded a new document -> notify staff
        if not getattr(actor, "is_staff", False):
            staff = list(recipients_for(instance))
            if staff:
                send_notification(
                    recipients=staff,
                    actor=actor,
                    verb=Notification.Verb.CREATED,
                    target=instance,
                    title="Nouveau document utilisateur",
                    message=getattr(instance, "name", ""),
                )
        return
    u = getattr(instance, "user", None)
    if not u:
        return
    changes = getattr(instance, "_pending_changes", {}) or {}
    if "status" in changes:
        new = changes["status"].get("new")
        labels = {"verified": "vérifié", "rejected": "refusé", "under_review": "en vérification", "submitted": "soumis", "draft": "brouillon"}
        title = f"Document {labels.get(new, str(new))}"
        send_notification(
            recipients=[u],
            actor=actor,
            verb=Notification.Verb.UPDATED,
            target=instance,
            title=title,
            message=getattr(instance, "name", ""),
        )


@receiver(post_save, sender=VolunteerApplication)
def _notify_application(sender, instance: VolunteerApplication, created, **kwargs):
    actor = get_current_user()
    if created:
        # New application submitted by a candidate -> notify staff (in‑app + email)
        staff = list(recipients_for(instance))
        if staff:
            try:
                u = getattr(instance, "user", None)
                full_name = u.get_full_name() if u and hasattr(u, "get_full_name") else (u.username if u else "")
            except Exception:
                full_name = ""
            send_notification(
                recipients=staff,
                actor=actor,
                verb=Notification.Verb.CREATED,
                target=instance,
                title="Nouvelle candidature",
                message=full_name,
            )
            # Optional email alert to SUPPORT_EMAIL
            support_email = getattr(settings, "SUPPORT_EMAIL", "")
            if support_email:
                try:
                    subj = "[BWF] Nouvelle candidature bénévole"
                    body = f"Candidat: {full_name}\nID: {getattr(instance, 'pk', '')}"
                    send_mail(subj, body, getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@localhost"), [support_email], fail_silently=True)
                except Exception:
                    pass
        return
    u = getattr(instance, "user", None)
    if not u:
        return
    changes = getattr(instance, "_pending_changes", {}) or {}
    if "status" in changes:
        new = changes["status"].get("new")
        labels = {"approved": "approuvée", "rejected": "refusée", "needs_changes": "à corriger", "pending": "en attente"}
        title = f"Candidature {labels.get(new, str(new))}"
        send_notification(
            recipients=[u],
            actor=actor,
            verb=Notification.Verb.UPDATED,
            target=instance,
            title=title,
            message="",
        )
        # If candidate updated (not staff), also alert staff
        if not getattr(actor, "is_staff", False):
            staff = list(recipients_for(instance))
            if staff:
                try:
                    full_name2 = u.get_full_name() if hasattr(u, "get_full_name") else u.username
                except Exception:
                    full_name2 = ""
                send_notification(
                    recipients=staff,
                    actor=actor,
                    verb=Notification.Verb.UPDATED,
                    target=instance,
                    title=f"Candidature mise a jour ({labels.get(new, str(new))})",
                    message=full_name2,
                )


@receiver(post_delete, sender=Project)
@receiver(post_delete, sender=Event)
@receiver(post_delete, sender=Mission)
def _notify_delete(sender, instance, **kwargs):
    actor = get_current_user()
    recipients = list(recipients_for(instance))
    title = f"{sender.__name__} supprimé"
    message = getattr(instance, "title", str(instance)) or str(instance)
    send_notification(
        recipients=recipients,
        actor=actor,
        verb=Notification.Verb.DELETED,
        target=instance,
        title=title,
        message=message,
    )


