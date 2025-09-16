import csv
from pathlib import Path
from django.core.management.base import BaseCommand
from core.models import City

class Command(BaseCommand):
    help = "Importe les villes de RDC depuis data/cd_cities.csv (colonnes: name,province)."

    def handle(self, *args, **opts):
        path = Path("data/cd_cities.csv")
        if not path.exists():
            self.stderr.write("Fichier data/cd_cities.csv introuvable.")
            return
        created = 0
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get("name") or "").strip()
                province = (row.get("province") or "").strip()
                if not name:
                    continue
                obj, is_new = City.objects.get_or_create(
                    name=name,
                    defaults={"province": province, "country_code": "CD"},
                )
                if (not is_new) and province and obj.province != province:
                    obj.province = province
                    obj.save(update_fields=["province"])
                created += int(is_new)
        self.stdout.write(self.style.SUCCESS(f"Import terminé. Nouvelles villes: {created}"))
