from django.conf import settings
from django.db import models
from django.utils import timezone

class Payment(models.Model):
    class Provider(models.TextChoices):
        CINETPAY = "CINETPAY", "CinetPay"
        FLUTTERWAVE = "FLUTTERWAVE", "Flutterwave"

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        ACCEPTED = "ACCEPTED", "Accepté"
        REFUSED = "REFUSED", "Refusé"
        CANCELED = "CANCELED", "Annulé"
        ERROR = "ERROR", "Erreur"

    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="payments"
    )
    email = models.EmailField(blank=True, default="")
    phone_e164 = models.CharField(max_length=32, blank=True, default="")  # +243...
    name = models.CharField(max_length=120, blank=True, default="")

    provider = models.CharField(max_length=20, choices=Provider.choices)
    provider_tx_id = models.CharField(max_length=64, help_text="transaction_id envoyé au PSP")
    provider_ref = models.CharField(max_length=128, blank=True, default="", help_text="référence/numero PSP")

    amount = models.PositiveIntegerField(help_text="montant minoré dans la devise minimale (ex: CDF entiers)")
    currency = models.CharField(max_length=8, default="CDF")

    description = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)

    raw_request = models.JSONField(blank=True, null=True)
    raw_response = models.JSONField(blank=True, null=True)
    raw_check = models.JSONField(blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["provider", "provider_tx_id"]),
            models.Index(fields=["status", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["provider", "provider_tx_id"], name="uniq_provider_tx")
        ]

    def __str__(self):
        return f"{self.provider} {self.amount} {self.currency} [{self.status}] #{self.provider_tx_id}"
