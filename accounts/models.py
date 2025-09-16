# accounts/models.py
import os
from decimal import Decimal
import mimetypes
from django.db import models
from django.conf import settings
from django.urls import reverse
from django.db.models import Sum, Q, CheckConstraint
from django.utils import timezone
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.core.exceptions import ValidationError
from datetime import timedelta
from core.models import City
import random


from django.apps import apps
from core.models import Event
import secrets

# ---------- Helpers ----------
def user_document_path(instance, filename):
    uid = instance.user_id or "anon"
    ts = timezone.now().strftime("%Y%m%d-%H%M%S")
    name, ext = os.path.splitext(filename)
    return f"user_documents/{uid}/{ts}{ext.lower()}"

ALLOWED_DOC_EXTS = ["pdf", "jpg", "jpeg", "png", "webp"]

# ---------- Document utilisateur ----------
class UserDocument(models.Model):
    STATUS_CHOICES = [
        ("draft", "Brouillon"),
        ("submitted", "Soumis"),
        ("under_review", "En vérification"),
        ("verified", "Vérifié"),
        ("rejected", "Refusé"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(upload_to=user_document_path,
                            validators=[FileExtensionValidator(allowed_extensions=ALLOWED_DOC_EXTS)])
    name = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    size = models.PositiveBigIntegerField(default=0)
    mime = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Document utilisateur"
        verbose_name_plural = "Documents utilisateur"

    def __str__(self):
        return self.name or os.path.basename(self.file.name)

    def save(self, *args, **kwargs):
        if self.file and hasattr(self.file, "size"):
            self.size = self.file.size
        mime, _ = mimetypes.guess_type(self.file.name)
        self.mime = mime or "application/octet-stream"
        super().save(*args, **kwargs)

    @property
    def extension(self) -> str:
        return os.path.splitext(self.file.name)[1].lower().lstrip(".") or "file"

    @property
    def type(self) -> str:
        mime, _ = mimetypes.guess_type(self.file.name)
        return (mime or "application/octet-stream").split("/")[-1].upper()

# ---------- Profil bénévole ----------
class Volunteer(models.Model):
    STATUS = [
        ("approved", "Approuvé"),
        ("inactive", "Inactif"),
        ("suspended", "Suspendu"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="volunteer")
    name = models.CharField(max_length=150, blank=True)
    # Date du dernier changement de nom (pour verrou 6 mois)
    name_last_changed = models.DateTimeField(null=True, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    motivation = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS, default="approved")  # nouveau
    city = models.ForeignKey(City, null=True, blank=True, on_delete=models.SET_NULL, related_name="volunteers")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Volontaire"
        verbose_name_plural = "Volontaires"

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.name or self.user.get_full_name() or self.user.get_username()

    @property
    def documents(self):
        # suppose un modèle UserDocument (optionnel). Sinon supprime cette prop.
        return getattr(self.user, "documents", None).all() if hasattr(self.user, "documents") else []

    def get_stats(self):
        hours = self.hours_entries.aggregate(total=Sum("hours"))["total"] or 0
        missions = self.hours_entries.filter(mission__isnull=False).values("mission").distinct().count()
        events = self.hours_entries.filter(event__isnull=False).values("event").distinct().count()
        return {"hours": hours, "missions": missions, "events": events}

    def update_from_application(self, application, *, overwrite: bool = False,
                                avatar_file=None, commit: bool = True) -> list[str]:
        """
        Met à jour le profil Volunteer à partir d'une VolunteerApplication.
        - overwrite=False : ne remplace que les champs vides (comportement par défaut)
        - avatar_file : File/Image à utiliser comme avatar si fourni
        - commit=True : sauvegarde immédiatement les changements
        Retourne la liste des champs modifiés (ex: ["name", "phone", "user.first_name"]).
        """
        changed: list[str] = []

        def set_vol(field: str, value):
            if value in (None, "", []):
                return
            current = getattr(self, field, None)
            if overwrite or current in (None, "", []):
                setattr(self, field, value)
                changed.append(field)

        # 1) Nom & user.{first_name,last_name} à partir de full_name
        full_name = getattr(application, "full_name", "") or ""
        if full_name:
            # Volunteer.name
            set_vol("name", full_name)

            # Découpage basique pour l'utilisateur lié
            if hasattr(self, "user") and self.user:
                parts = full_name.strip().split()
                if parts:
                    first = parts[0]
                    last = " ".join(parts[1:]) if len(parts) > 1 else ""
                    if overwrite or not self.user.first_name:
                        self.user.first_name = first
                        changed.append("user.first_name")
                    if last and (overwrite or not self.user.last_name):
                        self.user.last_name = last
                        changed.append("user.last_name")

        # 2) Téléphone
        set_vol("phone", getattr(application, "phone", None))

        # 3) Motivation
        set_vol("motivation", getattr(application, "motivation", None))

        # 4) Email (priorité éventuelle application.email sinon user.email)
        app_email = getattr(application, "email", None) if hasattr(application, "email") else None
        user_email = getattr(application.user, "email", None) if hasattr(application, "user") else None
        email = app_email or user_email
        if email:
            set_vol("email", email)
            if hasattr(self, "user") and self.user and (overwrite or not self.user.email):
                self.user.email = email
                changed.append("user.email")

        # 5) Avatar (si fourni et que celui du Volunteer est vide, ou overwrite)
        if avatar_file is not None:
            name = (getattr(avatar_file, "name", "") or "").lower()
            is_image = name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
            if is_image and (overwrite or not getattr(self, "avatar", None)):
                self.avatar = avatar_file
                changed.append("avatar")

        # 6) Commit
        if commit:
            # D'abord l'utilisateur si changé
            if hasattr(self, "user") and self.user:
                user_fields = [c.split(".", 1)[1] for c in changed if c.startswith("user.")]
                if user_fields:
                    # on déduplique pour éviter ValueError
                    self.user.save(update_fields=sorted(set(user_fields)))
            # Puis le Volunteer
            vol_fields = [c for c in changed if not c.startswith("user.")]
            if vol_fields:
                self.save(update_fields=sorted(set(vol_fields)))

        return changed
    
    def save(self, *args, **kwargs):
        # Verrou: le nom complet ne peut changer que tous les ~6 mois
        try:
            if self.pk:
                prev = Volunteer.objects.get(pk=self.pk)
                old_name = (prev.name or "").strip()
                new_name = (self.name or "").strip()
                if new_name != old_name:
                    last = getattr(prev, "name_last_changed", None)
                    now = timezone.now()
                    from datetime import timedelta
                    if last and last + timedelta(days=182) > now:
                        # Refuser le changement: restaurer
                        self.name = prev.name
                    else:
                        self.name_last_changed = now
        except Exception:
            pass
        return super().save(*args, **kwargs)

# ... tes imports et modèles existants (Volunteer, Availability, etc.)

class PhoneVerification(models.Model):
    volunteer = models.ForeignKey('accounts.Volunteer', on_delete=models.CASCADE, related_name="phone_verifications")
    phone = models.CharField(max_length=30)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["volunteer", "expires_at"]),
        ]

    def __str__(self):
        return f"PhoneVerification({self.volunteer_id}, {self.phone}, used={bool(self.used_at)})"

    @classmethod
    def create_or_replace(cls, volunteer, phone, *, ttl_minutes=10):
        # on supprime les anciennes en attente
        cls.objects.filter(volunteer=volunteer, used_at__isnull=True).delete()
        code = f"{random.randint(0, 999999):06d}"
        obj = cls.objects.create(
            volunteer=volunteer,
            phone=phone,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
        )
        obj.send_sms()
        return obj

    def is_expired(self):
        return timezone.now() > self.expires_at

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    # ---- À brancher sur ton provider (Twilio, OVH, etc.)
    def send_sms(self):
        # TODO: branchement réel SMS. Pour dev:
        # print(f"[DEV] OTP pour {self.phone}: {self.code}")
        pass

class EmailChangeRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_change_requests")
    new_email = models.EmailField()
    token = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=3)
        return super().save(*args, **kwargs)

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and timezone.now() < self.expires_at

    # ---- helper : remplir depuis une candidature ----
    def update_from_application(self, app, *, overwrite=False, avatar_file=None):
        if overwrite or not self.name:
            self.name = app.full_name or self.name
        if overwrite or not self.email:
            self.email = getattr(self.user, "email", "") or self.email
        if overwrite or not self.phone:
            self.phone = app.phone or self.phone
        if overwrite or not self.motivation:
            self.motivation = app.motivation or self.motivation
        if avatar_file:
            self.avatar = avatar_file
        self.status = "approved"
        self.save()

# ---------- Heures + justificatifs ----------
class HoursEntry(models.Model):
    volunteer = models.ForeignKey("accounts.Volunteer", on_delete=models.CASCADE, related_name="hours_entries")
    # mission obligatoire + PROTECT pour éviter des heures orphelines si on supprime une mission
    mission   = models.ForeignKey("staff.Mission", null=False, blank=False, on_delete=models.PROTECT, related_name="hours_entries")
    event     = models.ForeignKey(Event, null=True, blank=True, on_delete=models.SET_NULL, related_name="hours_entries")
    date      = models.DateField()
    hours     = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    note      = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            CheckConstraint(check=Q(hours__gt=0), name="hours_positive"),
            models.UniqueConstraint(
                fields=["volunteer", "mission", "date"],
                name="uniq_hours_by_volunteer_mission_date",
            ),
        ]

    def clean(self):
        super().clean()

        # Mission acceptée par ce bénévole
        if not self.mission_id:
            raise ValidationError("Une mission est requise pour déclarer des heures.")

        if not self.volunteer_id:
            raise ValidationError("Bénévole manquant sur la déclaration d’heures.")

        MissionSignup = apps.get_model("staff", "MissionSignup")
        accepted = MissionSignup.Status.ACCEPTED
        ok = MissionSignup.objects.filter(
            mission_id=self.mission_id, volunteer_id=self.volunteer_id, status=accepted
        ).exists()
        if not ok:
            raise ValidationError("Vous devez avoir été 'accepté' sur la mission pour déclarer des heures.")

        # Date logique
        if self.date and self.date > timezone.localdate():
            raise ValidationError("La date ne peut pas être dans le futur.")
        if self.mission.start_date and self.date and self.date < self.mission.start_date.date():
            raise ValidationError("La date est avant le début de la mission.")
        if self.mission.end_date and self.date and self.date > self.mission.end_date.date():
            raise ValidationError("La date est après la fin de la mission.")

    def save(self, *args, **kwargs):
        # Auto-renseigne l'événement si non défini
        if self.mission_id and not getattr(self, "event_id", None):
            self.event = self.mission.event
        # Sécurité globale (même hors ModelForm)
        self.full_clean()
        return super().save(*args, **kwargs)
    

def hours_proof_path(instance, filename):
    ts = timezone.now().strftime("%Y/%m/%d")
    name, ext = os.path.splitext(filename)
    return f"hours_proofs/{ts}/{instance.hours_entry_id}-{timezone.now().timestamp():.0f}{ext.lower()}"

class HoursEntryProof(models.Model):
    hours_entry = models.ForeignKey(HoursEntry, on_delete=models.CASCADE, related_name="proofs")
    file = models.FileField(upload_to=hours_proof_path,
                            validators=[FileExtensionValidator(allowed_extensions=ALLOWED_DOC_EXTS)])
    original_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name or os.path.basename(self.file.name)

    def save(self, *args, **kwargs):
        if self.file:
            self.original_name = self.original_name or os.path.basename(self.file.name)
            self.size = getattr(self.file, "size", 0)
            mime, _ = mimetypes.guess_type(self.original_name)
            self.content_type = mime or "application/octet-stream"
        super().save(*args, **kwargs)


# ---------- Activité simple ----------
class ActivityItem(models.Model):
    volunteer = models.ForeignKey(Volunteer, on_delete=models.CASCADE, related_name="activities")
    title = models.CharField(max_length=200)
    date = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return self.title


# ---------- Disponibilités & Compétences ----------
class Availability(models.Model):
    class Day(models.IntegerChoices):
        MONDAY = 0, "Lundi"
        TUESDAY = 1, "Mardi"
        WEDNESDAY = 2, "Mercredi"
        THURSDAY = 3, "Jeudi"
        FRIDAY = 4, "Vendredi"
        SATURDAY = 5, "Samedi"
        SUNDAY = 6, "Dimanche"

    class Slot(models.TextChoices):
        MORNING = "morning", "Matin"
        AFTERNOON = "afternoon", "Après-midi"
        EVENING = "evening", "Soir"
        FULLDAY = "fullday", "Journée"

    volunteer = models.ForeignKey(Volunteer, on_delete=models.CASCADE, related_name="availabilities")
    day = models.IntegerField(choices=Day.choices)
    slot = models.CharField(max_length=20, choices=Slot.choices)

    class Meta:
        unique_together = ("volunteer", "day", "slot")
        ordering = ["day", "slot"]

    def __str__(self):
        return f"{self.get_day_display()} – {self.get_slot_display()}"


class Skill(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class VolunteerSkill(models.Model):
    class Level(models.IntegerChoices):
        BEGINNER = 1, "Débutant"
        INTERMEDIATE = 2, "Intermédiaire"
        ADVANCED = 3, "Avancé"
        EXPERT = 4, "Expert"

    volunteer = models.ForeignKey(Volunteer, on_delete=models.CASCADE, related_name="volunteer_skills")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="assignments")
    level = models.IntegerField(choices=Level.choices, default=Level.BEGINNER)
    # Preuve facultative (image/PDF)
    proof = models.FileField(upload_to="skill_proofs/", blank=True, null=True,
                             validators=[FileExtensionValidator(allowed_extensions=ALLOWED_DOC_EXTS)])

    class Meta:
        unique_together = ("volunteer", "skill")
        ordering = ["-level", "skill__name"]

    def __str__(self):
        return f"{self.skill} — {self.get_level_display()}"
