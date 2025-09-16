"""
Staff security services: auth keys verification and decorator.
This version improves token extraction, error detail, and UX hints.
"""
from functools import wraps
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib import messages
from .models import AuthorizationKey, AuthorizationKeyUse


def _get_token_from_request(request) -> str | None:
    """Extract token from request.
    Priority: POST 'auth_key' > 'Authorization: Key <token>' > 'X-Auth-Key' header > GET 'auth_key'.
    Also accepts 'Authorization: Bearer <token>' as fallback.
    """
    tok = request.POST.get("auth_key")
    if tok:
        return tok
    auth = request.META.get("HTTP_AUTHORIZATION") or ""
    if auth:
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() in {"key", "bearer"}:
            return parts[1]
    tok = request.META.get("HTTP_X_AUTH_KEY")
    if tok:
        return tok
    return request.GET.get("auth_key")


def _log_use(
    *,
    key,
    user,
    request,
    action: str,
    ok: bool,
    reason: str | None = None,
    object_pk: str = "",
    object_repr: str = "",
    extra_meta: dict | None = None,
):
    meta: dict = {}
    if isinstance(extra_meta, dict):
        meta.update(extra_meta)
    if reason:
        meta["reason"] = reason

    return AuthorizationKeyUse.objects.create(
        key=key,  # can be None if superuser bypass
        used_by=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        object_pk=str(object_pk or ""),
        object_repr=str(object_repr or "")[:200],
        ip=request.META.get("REMOTE_ADDR"),
        user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:400],
        success=ok,
        meta=meta,
    )


_LEVEL_NAME = {
    AuthorizationKey.Level.LOW: "Low",
    AuthorizationKey.Level.MEDIUM: "Medium",
    AuthorizationKey.Level.HIGH: "High",
    AuthorizationKey.Level.CRITICAL: "Critical",
}


def verify_and_consume_key(
    request,
    *,
    action: str,
    required_level: int = AuthorizationKey.Level.MEDIUM,
    object_pk: str = "",
    object_repr: str = "",
    meta: dict | None = None,
    superuser_bypass: bool = True,
) -> tuple[bool, dict]:
    """
    Verify provided key and consume one use if OK.
    Returns (ok, info) and logs the attempt.
    info contains: {reason, key, required_level}.
    """
    user = getattr(request, "user", None)

    # superuser bypass
    if superuser_bypass and user and user.is_authenticated and user.is_superuser:
        _log_use(
            key=None,
            user=user,
            request=request,
            action=action,
            ok=True,
            reason=None,
            object_pk=object_pk,
            object_repr=object_repr,
            extra_meta={"bypass": "superuser"},
        )
        return True, {"reason": None, "key": None, "required_level": required_level}

    raw_token = _get_token_from_request(request)
    key = AuthorizationKey.find_valid_by_token(raw_token) if raw_token else None

    ok = False
    reason = None
    if not key:
        reason = "missing_or_invalid"
    elif key.has_expired():
        reason = "expired"
    elif not key.has_uses_left():
        reason = "exhausted"
    elif key.level < required_level:
        reason = "insufficient_level"
    elif not key.permits_action(action):
        reason = "action_not_allowed"
    else:
        ok = True

    _log_use(
        key=key,
        user=user,
        request=request,
        action=action,
        ok=ok,
        reason=reason,
        object_pk=object_pk,
        object_repr=object_repr,
        extra_meta=meta if isinstance(meta, dict) else None,
    )

    if ok:
        key.consume()
    return ok, {"reason": reason, "key": key, "required_level": required_level}


def require_auth_key(
    action: str,
    *,
    level: int = AuthorizationKey.Level.MEDIUM,
    superuser_bypass: bool = True,
    forbidden_message: str = "Cl� d'autorisation requise ou invalide.",
    return_403: bool = False,
    methods: tuple[str, ...] = ("POST", "PUT", "PATCH", "DELETE"),
):
    """
    Decorator for sensitive views.
    - Enforces a key only on methods listed in `methods`
    - Returns JSON 403 for AJAX (X-Requested-With or X-Auth-Request) or if return_403=True
    """
    def outer(viewfunc):
        @wraps(viewfunc)
        def _wrapped(request, *args, **kwargs):
            # Allow methods outside the protected list
            if methods and request.method.upper() not in {m.upper() for m in methods}:
                return viewfunc(request, *args, **kwargs)

            ok, info = verify_and_consume_key(
                request,
                action=action,
                required_level=level,
                superuser_bypass=superuser_bypass,
                object_pk=str(kwargs.get("pk") or kwargs.get("id") or ""),
                object_repr=viewfunc.__name__,
            )
            if not ok:
                reason = info.get("reason") if isinstance(info, dict) else None
                key = info.get("key") if isinstance(info, dict) else None
                req_level = info.get("required_level", level) if isinstance(info, dict) else level
                req_name = _LEVEL_NAME.get(req_level, str(req_level))
                key_level = getattr(key, "level", None)
                key_name = _LEVEL_NAME.get(key_level, str(key_level)) if key_level is not None else None

                msg = forbidden_message
                if reason == "insufficient_level":
                    msg = f"Cl� insuffisante (requis: {req_name}, obtenu: {key_name})."
                elif reason == "expired":
                    msg = "Cl� expir�e."
                elif reason == "exhausted":
                    msg = "Cl� �puis�e (quota atteint)."
                elif reason == "action_not_allowed":
                    msg = "Cl� non autoris�e pour cette action."
                elif reason == "missing_or_invalid":
                    msg = forbidden_message

                xrw = (request.headers.get("x-requested-with") or "").lower()
                is_ajax = xrw == "xmlhttprequest" or request.headers.get("x-auth-request") == "1"
                if is_ajax or return_403:
                    data = {"ok": False, "error": reason or "forbidden", "message": msg,
                            "required_level": req_level, "required_level_name": req_name}
                    if key_level is not None:
                        data.update({"key_level": key_level, "key_level_name": key_name})
                    resp = JsonResponse(data, status=403)
                    resp["WWW-Authenticate"] = f"Key realm=staff, required_level={req_name}"
                    return resp
                if hasattr(messages, "error"):
                    messages.error(request, msg)
                resp = HttpResponseForbidden(msg)
                resp["WWW-Authenticate"] = f"Key realm=staff, required_level={req_name}"
                return resp
            return viewfunc(request, *args, **kwargs)

        return _wrapped

    return outer

