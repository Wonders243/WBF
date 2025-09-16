from django import template

register = template.Library()

def _get_proofs_qs(entry):
    # essaie related_name="proofs", sinon manager par défaut
    if hasattr(entry, "proofs"):
        return entry.proofs.all()
    if hasattr(entry, "hoursentryproof_set"):
        return entry.hoursentryproof_set.all()
    # si rien… pas de proofs configurés (à corriger côté modèle)
    return None

def _file_field_and_value(obj):
    # retourne (nom_de_champ, fichier) pour le premier File/ImageField trouvé
    for f in obj._meta.get_fields():
        try:
            it = f.get_internal_type()
        except Exception:
            continue
        if it in ("FileField", "ImageField"):
            return f.name, getattr(obj, f.name)
    return None, None

@register.simple_tag
def hours_first_proof_url(entry):
    qs = _get_proofs_qs(entry)
    if not qs:
        return ""
    p = qs.first()
    if not p:
        return ""
    name, f = _file_field_and_value(p)
    if not f:
        return ""
    try:
        return f.url
    except Exception:
        return ""

@register.simple_tag
def hours_all_proofs(entry):
    """Renvoie une liste d'URLs des fichiers de preuve."""
    urls = []
    qs = _get_proofs_qs(entry)
    if not qs:
        return urls
    for p in qs:
        _, f = _file_field_and_value(p)
        if f:
            try:
                urls.append(f.url)
            except Exception:
                pass
    return urls
