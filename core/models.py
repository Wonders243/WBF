# core/models.py
from django.db import models
from django.utils.text import slugify
from django.conf import settings

# =======================
# Equipe / Partenaires
# =======================
# app/models.py
from django.db import models
from django.utils.text import slugify
from django.urls import reverse
from django.utils import timezone
import secrets



class TeamMemberInvite(models.Model):
    member = models.ForeignKey("core.TeamMember", on_delete=models.CASCADE, related_name="invites")
    token = models.CharField(max_length=64, unique=True, editable=False)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(blank=True, null=True)
    # Invitee response recorded at completion: "accepted" or "declined"
    response = models.CharField(max_length=16, blank=True, choices=[("accepted", "Accepted"), ("declined", "Declined")])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="team_invites_created")
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=14)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        return self.used_at is None and timezone.now() < self.expires_at





# --- Helpers ---------------------------------------------------------------
def _unique_slug(instance, value, slug_field="slug", max_length=80):
    base = slugify(value)[:max_length] or "item"
    Model = instance.__class__
    slug = base
    i = 2
    while Model.objects.filter(**{slug_field: slug}).exclude(pk=instance.pk).exists():
        suffix = f"-{i}"
        slug = (base[: max_length - len(suffix)] + suffix)
        i += 1
    return slug

class ActiveQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

# --- Team ------------------------------------------------------------------
class TeamMember(models.Model):
    class Seniority(models.TextChoices):
        EXEC   = "exec",   "Direction"
        LEAD   = "lead",   "Lead"
        SENIOR = "senior", "Senior"
        MID    = "mid",    "Confirmé·e"
        JUNIOR = "junior", "Junior"
        OTHER  = "other",  "Autre"

    # 🔗 Lien (optionnel) vers le compte utilisateur
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name="team_member",
        help_text="Associer à un compte utilisateur (facultatif)"
    )

    name        = models.CharField(max_length=120)
    slug        = models.SlugField(max_length=120, unique=True, blank=True)
    role        = models.CharField(max_length=120, help_text="Intitulé du poste affiché")
    seniority   = models.CharField(max_length=12, choices=Seniority.choices, blank=True)
    department  = models.CharField(max_length=120, blank=True)
    bio         = models.TextField(blank=True)
    image       = models.ImageField(upload_to="team_images/", blank=True, null=True)

    # Contact & profils
    email       = models.EmailField(blank=True)
    phone       = models.CharField(max_length=32, blank=True)
    website     = models.URLField(blank=True)
    linkedin    = models.URLField(blank=True)
    twitter     = models.URLField(blank=True)
    github      = models.URLField(blank=True)

    # Infos additionnelles
    pronouns    = models.CharField(max_length=40, blank=True, help_text="Ex: elle/il")
    location    = models.CharField(max_length=120, blank=True)
    languages   = models.CharField(max_length=200, blank=True, help_text="Ex: fr, en")
    expertise   = models.TextField(blank=True, help_text="Domaines d’expertise, mots-clés")

    # Meta
    is_active   = models.BooleanField(default=True)
    sort_order  = models.PositiveIntegerField(default=0)
    joined_on   = models.DateField(blank=True, null=True)
    left_on     = models.DateField(blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    objects = ActiveQuerySet.as_manager()

    class Meta:
        ordering = ("sort_order", "name")
        indexes  = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active", "sort_order"]),
        ]
    def _synced_full_name(self):
        if not self.user:
            return (self.name or "").strip()
        full = (self.user.get_full_name() or "").strip()
        return full or self.user.get_username()

    def apply_user_sync(self):
        """Forcer la cohérence avec User quand il est lié."""
        if self.user_id:
            # 🔒 verrou logique : on prend toujours les infos du User
            self.name = self._synced_full_name()
            self.email = self.user.email or ""

    def save(self, *args, **kwargs):
        # slug uniquement auto si vide (ne pas le régénérer après)
        if self.user_id:
            self.apply_user_sync()
        if not self.slug and (self.name or self.user_id):
            base = self.name or self._synced_full_name()
            if base:
                self.slug = _unique_slug(self, base)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    

    def get_absolute_url(self):
        return reverse("staff:member_detail", kwargs={"slug": self.slug})

    # Utilitaire pratique pour les templates
    @property
    def display_name(self):
        if self.name:
            return self.name
        if self.user:
            full = (self.user.get_full_name() or "").strip()
            return full or self.user.get_username()
        return ""

    @property
    def display_email(self):
        return self.email or (self.user.email if self.user_id else "")

# --- Partners --------------------------------------------------------------
class Partenaire(models.Model):
    class Category(models.TextChoices):
        NGO       = "ngo",       "Association / ONG"
        PUBLIC    = "public",    "Institution publique"
        COMPANY   = "company",   "Entreprise"
        MEDIA     = "media",     "Média"
        UNIVERSITY= "univ",      "Université"
        OTHER     = "other",     "Autre"

    class Tier(models.TextChoices):
        PLATINUM = "platinum", "Platine"
        GOLD     = "gold",     "Or"
        SILVER   = "silver",   "Argent"
        BRONZE   = "bronze",   "Bronze"
        STANDARD = "standard", "Standard"

    name         = models.CharField(max_length=150)
    slug         = models.SlugField(max_length=160, unique=True, blank=True)
    description  = models.TextField(blank=True)
    logo         = models.ImageField(upload_to="partenaires/", blank=True, null=True)
    website      = models.URLField(blank=True, null=True)

    # Catégorisation & niveau
    category     = models.CharField(max_length=12, choices=Category.choices, default=Category.OTHER)
    tier         = models.CharField(max_length=10, choices=Tier.choices, blank=True)

    # Contact référent
    contact_name  = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)

    # Coordonnées & réseaux
    address      = models.TextField(blank=True)
    linkedin     = models.URLField(blank=True)
    twitter      = models.URLField(blank=True)
    facebook     = models.URLField(blank=True)
    instagram    = models.URLField(blank=True)

    # Contrat / période / contributions
    start_date   = models.DateField(blank=True, null=True)
    end_date     = models.DateField(blank=True, null=True)
    contribution = models.TextField(blank=True, help_text="Financement, dons en nature, bénévolat d’entreprise…")

    # Meta
    is_active    = models.BooleanField(default=True)
    sort_order   = models.PositiveIntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    objects = ActiveQuerySet.as_manager()

    class Meta:
        ordering = ("sort_order", "name")
        indexes  = [
            models.Index(fields=["slug"]),
            models.Index(fields=["category", "tier"]),
            models.Index(fields=["is_active", "sort_order"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            self.slug = _unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("partners:partner_detail", kwargs={"slug": self.slug})


# =======================
# Projets / Evénements (public)
# =======================
class Project(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()
    partners = models.ManyToManyField(Partenaire, related_name="projects", blank=True)
    image = models.ImageField(upload_to="project_images/")
    link = models.URLField(blank=True, null=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:220]
        super().save(*args, **kwargs)
    def get_absolute_url(self):
        try:
            return reverse("project_detail", kwargs={"slug": self.slug})
        except Exception:
            return reverse("core:project_detail", kwargs={"slug": self.slug})


class Event(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    date = models.DateField()
    description = models.TextField()
    image = models.ImageField(upload_to="event_images/", blank=True, null=True)

    location = models.CharField(max_length=255, blank=True)
    projects = models.ManyToManyField(Project, related_name="events", blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:220]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        try:
            return reverse("event_detail", kwargs={"slug": self.slug})
        except Exception:
            # si ton app est "core:" namespacée quelque part
            return reverse("core:event_detail", kwargs={"slug": self.slug})


# =======================
# Témoignages / Actus / Dons
# =======================
class Testimonial(models.Model):
    author = models.CharField(max_length=100)
    content = models.TextField()
    image = models.ImageField(upload_to="testimonial_images/", blank=True, null=True)

    def __str__(self):
        return f"Témoignage de {self.author}"


class News(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    date = models.DateField(auto_now_add=True)
    image = models.ImageField(upload_to="news_images/", blank=True, null=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return self.title


class Donation(models.Model):
    donor_name = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Donation de {self.amount} par {self.donor_name or 'Anonyme'}"


class PaymentTransaction(models.Model):
    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiée"
        PENDING = "pending", "En attente"
        SUCCESS = "success", "Réussie"
        FAILED = "failed", "Échec"
        CANCELLED = "cancelled", "Annulée"

    provider = models.CharField(max_length=40, default="flutterwave")
    tx_ref = models.CharField(max_length=100, unique=True)
    provider_tx_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.INITIATED)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=6, default="KES")

    donor_name = models.CharField(max_length=120, blank=True)
    message = models.TextField(blank=True)

    return_url = models.URLField(blank=True)
    webhook_seen = models.BooleanField(default=False)

    donation = models.ForeignKey(Donation, null=True, blank=True, on_delete=models.SET_NULL, related_name="payments")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tx_ref"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Payment {self.provider} {self.tx_ref} ({self.status})"


# =======================
# Contact
# =======================
class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    date_sent = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_sent"]

    def __str__(self):
        return f"Message de {self.name} – {self.subject}"

# --- Référentiel des villes RDC ---
class City(models.Model):
    country_code = models.CharField(max_length=2, default="CD", editable=False)
    name = models.CharField(max_length=120, unique=True)
    province = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        ordering = ["name"]
        verbose_name = "Ville"
        verbose_name_plural = "Villes"

    def __str__(self):
        return f"{self.name}" + (f" · {self.province}" if self.province else "")

class SiteStats(models.Model):
    updated_at = models.DateTimeField(auto_now=True)
    total_users = models.PositiveIntegerField(default=0)
    total_volunteers = models.PositiveIntegerField(default=0)
    total_staff = models.PositiveIntegerField(default=0)
    total_missions = models.PositiveIntegerField(default=0)
    total_signups = models.PositiveIntegerField(default=0)
    total_hours_entries = models.PositiveIntegerField(default=0)

    def __str__(self):
        return "Statistiques globales"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

# core/models.py
from django.db import models
from core.models import City  # si tu as déjà City; sinon adapte l'import

class EducationStory(models.Model):
    class Category(models.TextChoices):
        EDUCATION = "education", "Éducation"
        SANTE = "sante", "Santé"
        PSY = "psy", "Soutien psychologique"
        AUTRE = "autre", "Autre"

    title = models.CharField(max_length=200, default="Appui scolaire")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.EDUCATION)
    beneficiary_name = models.CharField(max_length=150, blank=True)
    city = models.ForeignKey("core.City", null=True, blank=True, on_delete=models.SET_NULL, related_name="education_stories")
    cover = models.ImageField(upload_to="stories/education/%Y/%m/", blank=True, null=True)
    consent_file = models.FileField(upload_to="stories/education/consents/%Y/%m/", blank=True, null=True)
    quote = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "is_published", "created_at"]),
        ]

    def __str__(self):
        return self.title

class EducationStoryImage(models.Model):
    story = models.ForeignKey(EducationStory, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="stories/education/%Y/%m/")
    caption = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"Image {self.id} · {self.story}"
