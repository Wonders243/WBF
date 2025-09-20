from django.db import migrations


def set_site_name(apps, schema_editor):
    # Update django.contrib.sites Site to use brand name/domain
    Site = apps.get_model("sites", "Site")
    try:
        from django.conf import settings
    except Exception:  # pragma: no cover
        settings = None

    import os

    # Determine desired domain
    domain = None
    if settings is not None:
        try:
            hosts = getattr(settings, "ALLOWED_HOSTS", []) or []
            # Prefer a real hostname
            domain = next((h for h in hosts if h and "." in h and h not in {"127.0.0.1", "localhost"}), None)
            if not domain and hosts:
                domain = hosts[0]
        except Exception:
            domain = None
    # Fallbacks from env
    if not domain:
        domain = (os.getenv("PRIMARY_DOMAIN") or os.getenv("DJANGO_PRIMARY_DOMAIN") or "").strip()
    if not domain:
        domain = (os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")[0] or "").strip()
    if not domain:
        domain = "localhost"

    # Site display name (brand)
    site_name = os.getenv("SITE_NAME", "Bamu Wellbeing Foundation").strip()

    site_id = 1
    if settings is not None:
        try:
            site_id = int(getattr(settings, "SITE_ID", 1))
        except Exception:
            site_id = 1

    site, _ = Site.objects.get_or_create(id=site_id, defaults={"domain": domain, "name": site_name})
    site.domain = domain
    site.name = site_name
    site.save(update_fields=["domain", "name"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.RunPython(set_site_name, migrations.RunPython.noop),
    ]

