
from django.apps import AppConfig

class StaffConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "staff"
    verbose_name = "Gestion Staff"

    def ready(self):
        # s'assurer que les modèles security sont enregistrés
        from .security import models  # noqa
