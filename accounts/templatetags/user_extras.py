# yourapp/templatetags/user_extras.py
from django import template

register = template.Library()

@register.filter
def has_group(user, group_name):
    return user.is_authenticated and user.groups.filter(name__iexact=group_name).exists()

@register.simple_tag(takes_context=True)
def is_volunteer(context):
    """
    True si l'utilisateur est bénévole.
    Critères :
      - appartient au groupe 'Volunteers' (à adapter)
      - OU a une candidature approuvée (status='approved', à adapter à tes valeurs)
    """
    user = context['request'].user
    if not user.is_authenticated:
        return False
    # Option groupe
    in_group = user.groups.filter(name__iexact='Volunteers').exists()
    # Option candidature approuvée (si tu utilises ce workflow)
    try:
        from staff.models import VolunteerApplication
        approved = VolunteerApplication.objects.filter(user=user, status='approved').exists()
    except Exception:
        approved = False
    return in_group or approved
