# benevoles/templatetags/doc_extras.py
import os
from django import template

register = template.Library()

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

@register.filter
def is_image(path_or_file) -> bool:
    """
    True si c'est un fichier image (détecté par extension).
    Gère FieldFile, URL, et enlève ?querystring/#hash.
    """
    try:
        name = getattr(path_or_file, "name", None) or str(path_or_file)
    except Exception:
        name = str(path_or_file)
    name = name.split("?")[0].split("#")[0]
    ext = os.path.splitext(name)[1].lower()
    return ext in IMAGE_EXTS
