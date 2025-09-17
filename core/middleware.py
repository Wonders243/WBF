


import threading
_local = threading.local()

def get_current_user():
    return getattr(_local, "user", None)

class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.user = getattr(request, "user", None)
        try:
            return self.get_response(request)
        finally:
            _local.user = None

class LastUrlMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            if (
                request.method == "GET"
                and response.status_code == 200
                and str(response.get("Content-Type", "")).startswith("text/html")
            ):
                p = request.path
                if not (
                    p.startswith("/static/")
                    or p.startswith("/media/")
                    or p.startswith("/admin/")
                    or p.startswith("/accounts/")
                ):
                    request.session["last_url"] = request.get_full_path()
        except Exception:
            pass

        return response

# -- SEO canonical host redirect & noindex staging --

from django.http import HttpResponsePermanentRedirect

PRIMARY_HOST = "bamuwellbeing.org"  # ou "www.bamuwellbeing.org" si tu préfères avec www

class SeoHostRedirectMiddleware:
    """301 vers le domaine canonique (laisse passer cleverapps.io & localhost)."""
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        host = request.get_host().split(":")[0]
        if host not in (PRIMARY_HOST, "localhost", "127.0.0.1") and not host.endswith("cleverapps.io"):
            return HttpResponsePermanentRedirect(f"https://{PRIMARY_HOST}{request.get_full_path()}")
        return self.get_response(request)

class NoIndexOnStagingMiddleware:
    """Empêche l’indexation si on visite via cleverapps.io / localhost."""
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        response = self.get_response(request)
        host = request.get_host().split(":")[0]
        if host.endswith("cleverapps.io") or host in {"localhost","127.0.0.1"}:
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response
# -- Fin SEO --