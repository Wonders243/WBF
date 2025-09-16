# security/models.py
import uuid
import secrets
from django.conf import settings
from django.db import models
from django.db.models import F
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password


class AuthorizationKey(models.Model):
    class Level(models.IntegerChoices):
        LOW = 10, "Low"
        MEDIUM = 20, "Medium"
        HIGH = 30, "High"
        CRITICAL = 40, "Critical"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    label = models.CharField(max_length=120, blank=True)
    token_prefix = models.CharField(max_length=16, db_index=True)        # pour lookup rapide
    token_hash = models.CharField(max_length=128)                         # hashé (pas de stockage en clair)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="authkeys_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    level = models.IntegerField(choices=Level.choices, default=Level.MEDIUM)
    allowed_actions = models.JSONField(default=list, blank=True)          # ex: ["mission.invite", "project.delete"] ou ["*"]

    max_uses = models.PositiveIntegerField(null=True, blank=True)         # None = illimité
    uses_count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.label or self.token_prefix} ({self.get_level_display()})"

    # --- règles ---
    def has_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())

    def has_uses_left(self) -> bool:
        return self.max_uses is None or self.uses_count < self.max_uses

    def permits_action(self, action: str) -> bool:
        actions = self.allowed_actions or []
        return actions == ["*"] or action in actions

    # --- fabrique / vérif ---
    @classmethod
    def create_with_token(
        cls,
        *,
        created_by,
        label: str = "",
        level: int | None = None,
        allowed_actions: list[str] | None = None,
        max_uses: int | None = None,
        expires_at=None,
        note: str = "",
    ):
        """
        Crée une clé et retourne (objet, token_en_clair) — le token ne sera plus accessible ensuite.
        """
        token = secrets.token_urlsafe(24)  # ~ 32+ chars
        obj = cls.objects.create(
            label=label,
            token_prefix=token[:10],
            token_hash=make_password(token),
            created_by=created_by,
            level=level or cls.Level.MEDIUM,
            allowed_actions=allowed_actions or ["*"],
            max_uses=max_uses,
            expires_at=expires_at,
            note=note,
        )
        return obj, token

    @classmethod
    def find_valid_by_token(cls, raw_token: str) -> "AuthorizationKey | None":
        if not raw_token:
            return None
        prefix = raw_token[:10]
        # Plusieurs candidats possibles sur le même prefix (rare) -> vérification hash
        for key in cls.objects.filter(token_prefix=prefix, is_active=True):
            if check_password(raw_token, key.token_hash):
                return key
        return None

    def consume(self):
        # incrément atomique
        type(self).objects.filter(pk=self.pk).update(uses_count=F("uses_count") + 1)


class AuthorizationKeyUse(models.Model):
    key = models.ForeignKey(
        AuthorizationKey,
        null=True, blank=True,                 # ✅ autorise les logs sans clé
        on_delete=models.SET_NULL,             # ✅ conserve la ligne même si la clé est supprimée
        related_name="uses",
    )
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    used_at = models.DateTimeField(auto_now_add=True)

    action = models.CharField(max_length=64)                # ex: "mission.invite"
    object_pk = models.CharField(max_length=64, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)

    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True)  # 👈 plus robuste qu’un TextField illimité

    success = models.BooleanField(default=False)  # valeur par défaut neutre
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["used_at", "action"])]
        ordering = ["-used_at"]