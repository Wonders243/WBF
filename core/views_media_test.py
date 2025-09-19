# core/views_media_test.py
from django.http import JsonResponse
from django.conf import settings
from pathlib import Path
import uuid

def media_write_test(request):
    p = Path(settings.MEDIA_ROOT)
    p.mkdir(parents=True, exist_ok=True)
    name = f"health_{uuid.uuid4().hex}.txt"
    (p / name).write_text("ok")
    return JsonResponse({"ok": True, "url": f"{settings.MEDIA_URL}{name}"})
