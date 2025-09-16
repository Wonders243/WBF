from django.conf import settings
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

class Notification(models.Model):
    class Verb(models.TextChoices):
        CREATED = "created", "créé"
        UPDATED = "updated", "modifié"
        DELETED = "deleted", "supprimé"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="actions"
    )

    verb = models.CharField(max_length=20, choices=Verb.choices)

    # Cible polymorphique (projet, event, mission, ...)
    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_object_id = models.PositiveIntegerField()
    target = GenericForeignKey("target_content_type", "target_object_id")

    title = models.CharField(max_length=200, blank=True)   # ex: "Nouvelle mission"
    message = models.TextField(blank=True)                 # ex: "Mission X publiée"
    url = models.CharField(max_length=500, blank=True)     # lien vers la page

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.verb} • {self.title or self.target}"
