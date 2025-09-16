from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator

# ── Document (clé/locale) ─────────────────────────────────────────────────────
class LegalDocument(models.Model):
    KEY_CHOICES = [
        ("privacy", "Politique de confidentialité"),
        ("terms",   "Conditions d’utilisation"),
        ("cookies", "Politique cookies"),
        ("imprint", "Mentions légales"),
    ]
    key    = models.CharField(max_length=24, choices=KEY_CHOICES)
    locale = models.CharField(max_length=8, default="fr",
                              validators=[RegexValidator(r"^[a-z]{2}(-[A-Z]{2})?$")])
    title  = models.CharField(max_length=200)
    slug   = models.SlugField(max_length=200, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("key", "locale")]
        ordering = ["key", "locale"]

    def __str__(self):
        return f"{self.get_key_display()} [{self.locale}]"

    def current_version(self):
        today = timezone.localdate()
        return (self.versions.filter(status="published")
                .filter(models.Q(effective_date__isnull=True) | models.Q(effective_date__lte=today))
                .order_by("-effective_date", "-published_at", "-id").first())

# ── Version (brouillon / publiée, date d’effet) ──────────────────────────────
class LegalVersion(models.Model):
    STATUS = [("draft","Brouillon"), ("published","Publié")]

    document       = models.ForeignKey(LegalDocument, related_name="versions", on_delete=models.CASCADE)
    version        = models.CharField(max_length=40, help_text="ex: v1.0-2025-08-27")
    status         = models.CharField(max_length=12, choices=STATUS, default="draft")
    effective_date = models.DateField(null=True, blank=True, help_text="Date d’entrée en vigueur")
    published_at   = models.DateTimeField(null=True, blank=True, editable=False)

    # Contenus : on stocke Markdown + rendu HTML (sanitisé) pour performance
    body_md   = models.TextField(blank=True, help_text="Contenu en Markdown (recommandé)")
    body_html = models.TextField(blank=True, help_text="Rendu HTML (généré)")

    change_log = models.TextField(blank=True, help_text="Résumé des changements (public)")

    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="updated_legal_versions")
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("document", "version")]
        ordering = ["-effective_date", "-published_at", "-id"]

    def __str__(self):
        return f"{self.document.title} — {self.version} ({self.status})"

    def render_markdown(self):
        """Convertit body_md -> body_html (optionnel: nécessite 'markdown' & 'bleach')."""
        try:
            import markdown as md
            html = md.markdown(self.body_md or "", extensions=["extra","sane_lists","toc"])
        except Exception:
            html = self.body_md  # fallback brut si lib absente
        # Sanitize (si bleach dispo)
        try:
            import bleach
            # ALLOWED_TAGS est souvent un frozenset; le convertir avant extension évite TypeError
            base_tags = list(getattr(bleach.sanitizer, "ALLOWED_TAGS", []))
            extra_tags = [
                "p","h1","h2","h3","h4","h5","h6",
                "table","thead","tbody","tr","td","th",
                "ul","ol","li","pre","code","blockquote","hr",
                "a","strong","em"
            ]
            allowed_tags = list(dict.fromkeys(base_tags + extra_tags))
            html = bleach.clean(
                html,
                tags=allowed_tags,
                attributes={
                    "a": ["href","title","name","id","target","rel"],
                },
                strip=True,
            )
        except Exception:
            pass
        self.body_html = html

    def publish(self, user=None):
        if not self.body_html:
            self.render_markdown()
        self.status = "published"
        self.published_at = timezone.now()
        if user:
            self.updated_by = user
        self.save()

    @property
    def is_effective(self):
        return (self.status == "published" and
                (self.effective_date is None or self.effective_date <= timezone.localdate()))

# ── Acceptation par utilisateur (qui a accepté quelle version, quand) ────────
class LegalAcceptance(models.Model):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="legal_acceptances")
    document   = models.ForeignKey(LegalDocument, on_delete=models.CASCADE, related_name="acceptances")
    version    = models.ForeignKey(LegalVersion, on_delete=models.CASCADE, related_name="acceptances")
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip          = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.TextField(blank=True)

    class Meta:
        unique_together = [("user", "version")]
        ordering = ["-accepted_at"]

    def __str__(self):
        return f"{self.user} → {self.document.key} {self.version.version}"
