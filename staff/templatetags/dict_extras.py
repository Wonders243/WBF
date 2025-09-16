from django import template

register = template.Library()

@register.filter(name="get_item")
def get_item(mapping, key):
    """
    mapping: dict (ex: {volunteer_id: ["skill A", "skill B"], ...})
    key: clé dynamique (v.id dans le template)

    Retourne mapping[key] ou None si absent / non indexable.
    """
    try:
        # accepte int ou str
        if isinstance(mapping, dict):
            # si la clé est une str numérique, on tente int
            if isinstance(key, str) and key.isdigit():
                key_int = int(key)
                if key_int in mapping:
                    return mapping.get(key_int)
            return mapping.get(key)
    except Exception:
        pass
    return None
