


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
