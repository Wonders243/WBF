from django.contrib.auth.decorators import user_passes_test, login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from .models import AuthorizationKey
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string

User = get_user_model()


def is_superuser(u):
    return u.is_authenticated and u.is_superuser


@login_required
@user_passes_test(is_superuser)
def create_auth_key(request):
    # Branch: send an existing one-time token from session (after creation)
    if request.method == "POST" and request.POST.get("send_existing"):
        key_id = request.POST.get("key_id")
        key = get_object_or_404(AuthorizationKey, pk=key_id)
        token = request.session.get(f"key_plain_{key.id}")
        if not token:
            messages.warning(request, "Le token n'est plus disponible pour l'envoi.")
            return redirect("staff:key_list")

        staff_users = User.objects.filter(is_active=True, is_staff=True).order_by(
            "last_name", "first_name", "username"
        )
        ids = request.POST.getlist("recipients")
        recipients = list(
            User.objects.filter(id__in=ids, is_active=True, is_staff=True).values_list(
                "email", flat=True
            )
        )
        subject = request.POST.get("email_subject") or "Cle d'autorisation"
        body_txt = (
            request.POST.get("email_body") or "Voici votre cle d'autorisation."
        )

        ctx = {"token": token, "key": key}
        html = render_to_string("security/_email_key.html", ctx)
        from django.conf import settings as dj_settings
        from_email = (
            getattr(dj_settings, "DEFAULT_FROM_EMAIL", None) or "ne_pas_repondre@bamuwellbeing.org"
        )
        if recipients:
            try:
                send_mail(
                    subject, body_txt + f"\n\nToken: {token}", from_email, recipients, html_message=html
                )
                messages.success(
                    request, f"Cle envoyee a {len(recipients)} destinataire(s)."
                )
            except Exception:
                messages.error(request, "Echec d'envoi de l'email.")
        else:
            messages.info(request, "Aucun destinataire selectionne.")

        return render(
            request,
            "security/key_created.html",
            {"key": key, "token": token, "staff_users": staff_users},
        )

    # Branch: rotate from existing key (create a new one with same rules)
    if request.method == "POST" and request.POST.get("rotate_from"):
        old = get_object_or_404(AuthorizationKey, pk=request.POST.get("rotate_from"))
        label = (old.label or "") + " (rotation)"
        new_key, token = AuthorizationKey.create_with_token(
            created_by=request.user,
            label=label,
            level=old.level,
            allowed_actions=old.allowed_actions or ["*"],
            max_uses=old.max_uses,
            expires_at=old.expires_at,
            note=f"Rotation de {old.token_prefix}",
        )
        if request.POST.get("revoke_old"):
            old.is_active = False
            old.save(update_fields=["is_active"])
        request.session[f"key_plain_{new_key.id}"] = token

        staff_users = User.objects.filter(is_active=True, is_staff=True).order_by(
            "last_name", "first_name", "username"
        )
        return render(
            request,
            "security/key_created.html",
            {"key": new_key, "token": token, "staff_users": staff_users},
        )

    # Branch: create new key
    if request.method == "POST":
        label = request.POST.get("label") or ""
        level = int(request.POST.get("level") or AuthorizationKey.Level.MEDIUM)
        actions = request.POST.getlist("actions") or ["*"]
        max_uses = request.POST.get("max_uses") or None
        expires_at = request.POST.get("expires_at") or None

        if max_uses:
            max_uses = int(max_uses)
        if expires_at:
            # Expected format: YYYY-MM-DDTHH:MM
            expires_at = timezone.make_aware(
                timezone.datetime.fromisoformat(expires_at)
            )

        key_obj, token = AuthorizationKey.create_with_token(
            created_by=request.user,
            label=label,
            level=level,
            allowed_actions=actions or ["*"],
            max_uses=max_uses,
            expires_at=expires_at,
            note=request.POST.get("note") or "",
        )

        # Store raw token for the one-time display + email helper
        request.session[f"key_plain_{key_obj.id}"] = token
        staff_users = User.objects.filter(is_active=True, is_staff=True).order_by(
            "last_name", "first_name", "username"
        )
        return render(
            request,
            "security/key_created.html",
            {"key": key_obj, "token": token, "staff_users": staff_users},
        )

    staff_users = User.objects.filter(is_active=True, is_staff=True).order_by(
        "last_name", "first_name", "username"
    )
    return render(
        request,
        "security/create_key.html",
        {
            "levels": AuthorizationKey.Level.choices,
            "known_actions": [
                "mission.invite",
                "mission.cancel_invite",
                "project.update",
                "project.delete",
                "event.update",
                "event.delete",
            ],
            "staff_users": staff_users,
        },
    )


@login_required
@user_passes_test(is_superuser)
def key_list(request):
    keys = AuthorizationKey.objects.all()
    return render(request, "security/key_list.html", {"keys": keys})


@login_required
@user_passes_test(is_superuser)
def revoke_key(request, key_id):
    key = get_object_or_404(AuthorizationKey, pk=key_id)
    key.is_active = False
    key.save(update_fields=["is_active"])
    messages.info(request, "Cle revoquee.")
    return redirect("staff:key_list")


@login_required
@user_passes_test(is_superuser)
def key_created(request, key_id):
    key = get_object_or_404(AuthorizationKey, pk=key_id)
    token = request.session.get(f"key_plain_{key.id}")
    if not token:
        messages.warning(request, "Ce token n'est plus disponible (affichage unique).")
        return redirect("staff:key_list")

    staff_users = User.objects.filter(is_active=True, is_staff=True).order_by(
        "last_name", "first_name", "username"
    )

    if request.method == "POST":
        ids = request.POST.getlist("recipients")
        recipients = list(
            User.objects.filter(id__in=ids, is_active=True, is_staff=True).values_list(
                "email", flat=True
            )
        )
        subject = request.POST.get("email_subject") or "Cle d'autorisation"
        body_txt = (
            request.POST.get("email_body") or "Voici votre cle d'autorisation."
        )

        ctx = {"token": token, "key": key}
        html = render_to_string("security/_email_key.html", ctx)
        from django.conf import settings as dj_settings

        from_email = (
            getattr(dj_settings, "DEFAULT_FROM_EMAIL", None) or "ne_pas_repondre@bamuwellbeing.org"
        )
        if recipients:
            try:
                send_mail(
                    subject,
                    body_txt + f"\n\nToken: {token}",
                    from_email,
                    recipients,
                    html_message=html,
                )
                messages.success(
                    request, f"Cle envoyee a {len(recipients)} destinataire(s)."
                )
            except Exception:
                messages.error(request, "Echec d'envoi de l'email.")
        else:
            messages.info(request, "Aucun destinataire selectionne.")

    return render(
        request,
        "security/key_created.html",
        {"key": key, "token": token, "staff_users": staff_users},
    )


@login_required
@user_passes_test(is_superuser)
def rotate_key(request, key_id):
    old = get_object_or_404(AuthorizationKey, pk=key_id)
    label = (old.label or "") + " (rotation)"
    new_key, token = AuthorizationKey.create_with_token(
        created_by=request.user,
        label=label,
        level=old.level,
        allowed_actions=old.allowed_actions or ["*"],
        max_uses=old.max_uses,
        expires_at=old.expires_at,
        note=f"Rotation de {old.token_prefix}",
    )
    if request.POST.get("revoke_old"):
        old.is_active = False
        old.save(update_fields=["is_active"])
    request.session[f"key_plain_{new_key.id}"] = token
    messages.info(request, "Nouvelle cle generee. Copiez le token maintenant.")
    return redirect("staff:key_created", key_id=new_key.id)
