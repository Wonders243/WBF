from django import template

register = template.Library()

@register.filter
def add_class(field, css):
    """Ajoute des classes CSS à un champ de formulaire."""
    existing = field.field.widget.attrs.get("class", "")
    new = (existing + " " + css).strip()
    return field.as_widget(attrs={**field.field.widget.attrs, "class": new})

@register.filter
def attr(field, arg):
    """Définit un attribut:  {{ field|attr:"placeholder:Email" }}"""
    try:
        name, value = arg.split(":", 1)
    except ValueError:
        return field
    return field.as_widget(attrs={**field.field.widget.attrs, name: value})
