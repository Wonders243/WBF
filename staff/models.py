# staff/models.py
import os
from django.db import transaction
from django.conf import settings
from django.db import models
from django.utils import timezone
from core.models import Event  # ton modèle d’événement public
from django.urls import reverse
from django.db.models import Q
from core.models import City

class Mission(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)

    city = models.ForeignKey(City, null=True, blank=True, on_delete=models.SET_NULL, related_name="missions")
    # --------------------------------
    event = models.ForeignKey(
        Event, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="missions"
    )

    start_date = models.DateTimeField(null=True, blank=True)
    end_date   = models.DateTimeField(null=True, blank=True)

    capacity = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[("draft","Brouillon"),("published","Publié"),("archived","Archivé")],
        default="published",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_date", "id"]

    def __str__(self):
        return self.title


class MissionSignup(models.Model):
    class Status(models.TextChoices):
        INVITED   = "invited",  "Invité"
        PENDING   = "pending",  "En attente"
        ACCEPTED  = "accepted", "Accepté"
        DECLINED  = "declined", "Refusé"
        CANCELLED = "cancelled","Annulé"

    mission   = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="signups")
    volunteer = models.ForeignKey("accounts.Volunteer", on_delete=models.CASCADE, related_name="mission_signups")
    status    = models.CharField(max_length=16, choices=Status.choices, default=Status.INVITED)

    invited_by   = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="mission_invitations_sent")
    note         = models.CharField(max_length=255, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("mission", "volunteer")]
        indexes = [
            models.Index(fields=["volunteer", "status"]),
            models.Index(fields=["mission", "status"]),
        ]
    def __str__(self):
        return f"{self.volunteer} → {self.mission} [{self.get_status_display()}]"


def application_upload_to(instance, filename):
    # Ex: applications/2025/08/user_12/ID_front_abcdef.pdf
    return f"applications/{timezone.now():%Y/%m}/user_{instance.application.user_id}/{instance.doc_type}_{filename}"

def _is_image_fieldfile(field_file) -> bool:
    try:
        name = getattr(field_file, "name", None) or str(field_file)
    except Exception:
        name = str(field_file)
    name = name.split("?")[0].split("#")[0]
    ext = os.path.splitext(name)[1].lower()
    return ext in {".png", ".jpg", ".jpeg", ".webp", ".gif"}


class ApplicationStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    NEEDS_CHANGES = "needs_changes", "À corriger"
    APPROVED = "approved", "Approuvée"
    REJECTED = "rejected", "Refusée"

def application_upload_to(instance, filename):
    return f"applications/{timezone.now():%Y/%m}/user_{instance.application.user_id}/{instance.doc_type}_{filename}"

class VolunteerApplication(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="volunteer_applications")

    # Identité & contact
    full_name = models.CharField("Nom complet", max_length=200)
    phone = models.CharField("Téléphone", max_length=50)
    birth_date = models.DateField("Date de naissance", null=True, blank=True)

    # Adresse
    address_line1 = models.CharField("Adresse (ligne 1)", max_length=255)
    address_line2 = models.CharField("Complément d’adresse", max_length=255, blank=True)
    city = models.CharField("Ville", max_length=120)
    state = models.CharField("Région/État", max_length=120, blank=True)
    postal_code = models.CharField("Code postal", max_length=30, blank=True)
    country = models.CharField("Pays", max_length=120, default="")

    # Pièce d'identité
    ID_TYPES = [
        ("id_card", "Carte d’identité"),
        ("passport", "Passeport"),
        ("license", "Permis de conduire"),
    ]
    id_type = models.CharField("Type de pièce", max_length=20, choices=ID_TYPES)
    id_number = models.CharField("Numéro de la pièce", max_length=120)
    id_expiry = models.DateField("Date d’expiration", null=True, blank=True)

    # Divers
    motivation = models.TextField("Motivation", blank=True)
    emergency_contact = models.CharField("Contact d’urgence (nom & tél.)", max_length=255, blank=True)

    # Workflow
    status = models.CharField(max_length=20, choices=ApplicationStatus.choices, default=ApplicationStatus.PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reviewed_applications"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField("Note du reviewer", blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            # une seule candidature approuvée par user
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status=ApplicationStatus.APPROVED),
                name="uniq_approved_application_per_user",
            ),
            # une seule candidature ouverte par user
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status__in=[ApplicationStatus.PENDING, ApplicationStatus.NEEDS_CHANGES]),
                name="uniq_open_application_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["-submitted_at"]),
        ]

    def __str__(self):
        return f"Candidature bénévole #{self.id} — {self.user}"

    def get_absolute_url(self):
        return reverse("benevoles:application_detail", args=[self.pk])

    # ----- Actions workflow -----
    def approve(self, reviewer):
        from accounts.models import Volunteer
        self.status = ApplicationStatus.APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()

        # choisir un avatar : selfie > id_front > première image
        def is_image(field_file):
            name = (getattr(field_file, "name", None) or str(field_file)).split("?",1)[0].split("#",1)[0]
            return name.lower().endswith((".png",".jpg",".jpeg",".webp",".gif"))
        avatar_file = None
        ordered_docs = list(
            self.documents.all().order_by(
                models.Case(
                    models.When(doc_type="selfie", then=models.Value(0)),
                    models.When(doc_type="id_front", then=models.Value(1)),
                    default=models.Value(2),
                    output_field=models.IntegerField(),
                ),
                "-uploaded_at",
            )
        )
        for d in ordered_docs:
            if hasattr(d, "file") and getattr(d.file, "name", None) and is_image(d.file):
                avatar_file = d.file
                break

        with transaction.atomic():
            self.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])

            vol, _ = Volunteer.objects.get_or_create(user=self.user)
            vol.update_from_application(self, overwrite=False, avatar_file=avatar_file)

            # Promouvoir vers UserDocument si dispo (optionnel)
            try:
                from accounts.models import UserDocument
                for d in self.documents.all():
                    title = d.get_doc_type_display()
                    doc_status = "verified" if d.status == "approved" else "uploaded"
                    UserDocument.objects.get_or_create(
                        user=self.user,
                        title=title,
                        file=d.file,
                        defaults={"status": doc_status},
                    )
            except Exception:
                pass

            # Fermer les autres candidatures ouvertes
            VolunteerApplication.objects.filter(
                user=self.user, status__in=[ApplicationStatus.PENDING, ApplicationStatus.NEEDS_CHANGES]
            ).exclude(pk=self.pk).update(
                status=ApplicationStatus.REJECTED, reviewed_by=reviewer, reviewed_at=timezone.now()
            )
    
    def unapprove(self, reviewer, note: str = ""):
        """
        Annule une approbation : repasse la candidature en 'needs_changes',
        garde la note staff, et met le Volunteer en 'inactive' + enlève le groupe.
        """
        from accounts.models import Volunteer
        from django.contrib.auth.models import Group

        self.status = ApplicationStatus.NEEDS_CHANGES
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        if note:
            self.review_note = note

        with transaction.atomic():
            self.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])

            # 1) Mettre le profil Volunteer en inactif s'il existe
            try:
                vol = Volunteer.objects.get(user=self.user)
                if hasattr(vol, "status"):
                    vol.status = "inactive"
                    vol.save(update_fields=["status", "updated_at"])
            except Volunteer.DoesNotExist:
                pass

            # 2) Retirer du groupe "Bénévoles" si présent (optionnel)
            try:
                group = Group.objects.get(name="Bénévoles")
                group.user_set.remove(self.user)
            except Group.DoesNotExist:
                pass

    def reject(self, reviewer, note=""):
        self.status = ApplicationStatus.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        if note:
            self.review_note = note
        self.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])

    def request_changes(self, reviewer, note=""):
        self.status = ApplicationStatus.NEEDS_CHANGES
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        if note:
            self.review_note = note
        self.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])


class VolunteerApplicationDocument(models.Model):
    DOC_TYPES = [
        ("id_front", "Pièce d’identité — Recto"),
        ("id_back", "Pièce d’identité — Verso"),
        ("selfie", "Selfie avec la pièce"),
        ("proof_address", "Justificatif de domicile"),
        ("criminal_record", "Casier judiciaire / extrait"),
        ("other", "Autre document"),
    ]
    DOC_STATUS = [
        ("pending", "En attente"),
        ("approved", "Approuvé"),
        ("rejected", "Refusé"),
    ]

    application = models.ForeignKey(VolunteerApplication, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField("Type de document", max_length=30, choices=DOC_TYPES)
    file = models.FileField("Fichier", upload_to=application_upload_to)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=20, choices=DOC_STATUS, default="pending")
    reviewer_note = models.TextField("Note du reviewer", blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reviewed_documents"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"Doc {self.get_doc_type_display()} — App #{self.application_id}"
