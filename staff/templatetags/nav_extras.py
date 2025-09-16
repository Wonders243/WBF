# templatetags/nav_extras.py
from django import template
register = template.Library()

ACTIVE = "bg-slate-100 dark:bg-slate-800/60 text-slate-900 dark:text-slate-100 font-semibold"

@register.simple_tag(takes_context=True)
def nav_active(context, *prefixes):
    try:
        name = context["request"].resolver_match.url_name or ""
    except Exception:
        name = ""
    is_active = any(name.startswith(p) for p in prefixes if p)
    return ACTIVE if is_active else ""
