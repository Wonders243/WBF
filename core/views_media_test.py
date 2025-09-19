# core/views_media_test.py
from django.http import JsonResponse, Http404
from django.conf import settings
from pathlib import Path
import uuid

def media_write_test(request):
    p = Path(settings.MEDIA_ROOT)
    p.mkdir(parents=True, exist_ok=True)
    name = f"health_{uuid.uuid4().hex}.txt"
    (p / name).write_text("ok")
    return JsonResponse({"ok": True, "url": f"{settings.MEDIA_URL}{name}"})

def media_ls(request):
    """List files under MEDIA_ROOT (optionally a subpath via ?path=...)."""
    base = Path(settings.MEDIA_ROOT)
    sub = request.GET.get("path", "").strip().lstrip("/\\")
    target = (base / sub).resolve()
    try:
        # prevent path traversal
        target.relative_to(base.resolve())
    except Exception:
        raise Http404("Invalid path")
    if not target.exists():
        return JsonResponse({"exists": False, "path": str(target)})
    if target.is_file():
        return JsonResponse({
            "exists": True,
            "type": "file",
            "path": str(target),
            "url": settings.MEDIA_URL.rstrip('/') + '/' + sub
        })
    items = []
    for child in sorted(target.iterdir()):
        items.append({
            "name": child.name,
            "is_dir": child.is_dir(),
            "size": (child.stat().st_size if child.is_file() else None),
        })
    return JsonResponse({"exists": True, "type": "dir", "path": str(target), "items": items})
