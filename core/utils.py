# core/utils.py
from django.contrib.auth.models import Group

def grant_team_access(user):
    """
    Donne l'accès à l'espace staff:
    - active user.is_staff (pour @staff_member_required),
    - si le booléen custom 'team_member' existe sur le User, le passe à True,
    - ajoute l'utilisateur au groupe 'Team' (créé si besoin).
    """
    changed = []

    # (optionnel) ton booléen custom si présent
    if hasattr(user, "team_member") and not getattr(user, "team_member"):
        setattr(user, "team_member", True)
        changed.append("team_member")

    # requis par @staff_member_required
    if not user.is_staff:
        user.is_staff = True
        changed.append("is_staff")

    if changed:
        user.save(update_fields=changed)

    # Groupe "Team" (permet d'attacher des permissions spécifiques)
    team_group, _ = Group.objects.get_or_create(name="Team")
    user.groups.add(team_group)


from urllib.parse import urlparse
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.shortcuts import redirect, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme

def redirect_back(request, fallback="core:accueil"):
    allowed = {request.get_host(), request.get_host().split(":")[0]}
    allowed.update(getattr(settings, "ALLOWED_HOSTS", []))

    def is_safe(u: str) -> bool:
        return bool(u) and url_has_allowed_host_and_scheme(
            u,
            allowed_hosts=allowed,
            require_https=request.is_secure(),
        )

    # 1) ?next=...
    next_url = request.POST.get(REDIRECT_FIELD_NAME) or request.GET.get(REDIRECT_FIELD_NAME)
    if is_safe(next_url):
        return redirect(next_url)

    # 2) Referer
    referer = request.META.get("HTTP_REFERER")
    if is_safe(referer) and urlparse(referer).path != request.path:
        return redirect(referer)

    # 3) Dernière page HTML 200 visitée (cf. middleware)
    last_url = request.session.get("last_url")
    if is_safe(last_url) and urlparse(last_url).path != request.path:
        return redirect(last_url)

    # 4) Fallback
    return redirect(resolve_url(fallback))
