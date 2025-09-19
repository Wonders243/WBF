# WBF/settings.py
from pathlib import Path
from dotenv import load_dotenv
import os
import sys
import dj_database_url

# ────────────────────────────────
# BASE / ENV
# ────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DOTENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=str(DOTENV_PATH), override=False)

def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key")  # ⚠️ à remplacer en prod
DEBUG = env_bool("DJANGO_DEBUG", True)
USE_HTTPS = env_bool("DJANGO_USE_HTTPS", not DEBUG)

# ALLOWED_HOSTS + défauts sains pour ta prod
_raw_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", "")
if DEBUG:
    ALLOWED_HOSTS = []
else:
    ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()] or [
        "bamuwellbeing.org",
        "www.bamuwellbeing.org",
    ]

SITE_ID = int(os.getenv("DJANGO_SITE_ID", 1))

# ────────────────────────────────
# APPS
# ────────────────────────────────
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
    "django.contrib.sitemaps",  # SEO: sitemap

    # Tiers
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "widget_tweaks",
    "django_cleanup.apps.CleanupConfig",
    "crispy_forms",
    "crispy_tailwind",

    # Projet
    "core.apps.CoreConfig",
    "accounts.apps.AccountsConfig",
    "staff.apps.StaffConfig",
    "notifications",
    "legal",
    "payments",
]

# Reload auto uniquement en dev
if DEBUG:
    INSTALLED_APPS += ["django_browser_reload"]

# Crispy
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# Allauth
ACCOUNT_FORMS = {
    "reset_password": "accounts.forms.StyledResetPasswordForm",
    "signup": "accounts.forms.TermsSignupForm",
}
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = os.getenv("ACCOUNT_EMAIL_VERIFICATION", "none")
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}

# Support (affichage/contact)
PAYMENT_MAINTENANCE = os.getenv("PAYMENT_MAINTENANCE", "False").lower() == "true"
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "")
SUPPORT_PHONE = os.getenv("SUPPORT_PHONE", "")
SUPPORT_WHATSAPP = os.getenv("SUPPORT_WHATSAPP", "")
SUPPORT_URL = os.getenv("SUPPORT_URL", "")

# ────────────────────────────────
# MIDDLEWARE
# ────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise sera inséré juste après si activé (voir plus bas)
    "django.contrib.sessions.middleware.SessionMiddleware",
    "core.middleware.LastUrlMiddleware",

    # i18n : APRÈS Session et AVANT Common
    "django.middleware.locale.LocaleMiddleware",

    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    # Allauth (après AuthenticationMiddleware)
    "allauth.account.middleware.AccountMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Optionnel: WhiteNoise (servir les fichiers statiques en prod)
# Active via env DJANGO_USE_WHITENOISE=1 (défaut: True en prod)
_use_whitenoise = env_bool("DJANGO_USE_WHITENOISE", not DEBUG)
if _use_whitenoise:
    # insérer juste après SecurityMiddleware
    try:
        idx = next((i for i, x in enumerate(MIDDLEWARE) if x.endswith("SecurityMiddleware")))
    except StopIteration:
        idx = 0
    if "whitenoise.middleware.WhiteNoiseMiddleware" not in MIDDLEWARE:
        MIDDLEWARE.insert(idx + 1, "whitenoise.middleware.WhiteNoiseMiddleware")

# Middlewares SEO (ajoute-les seulement si présents dans ton code)
# Active si DJANGO_ENABLE_CANONICAL_REDIRECT=1 et/ou DJANGO_ENABLE_NOINDEX_STAGING=1
if env_bool("DJANGO_ENABLE_CANONICAL_REDIRECT", False):
    MIDDLEWARE.insert(1, "core.middleware.SeoHostRedirectMiddleware")
if env_bool("DJANGO_ENABLE_NOINDEX_STAGING", False):
    MIDDLEWARE += ["core.middleware.NoIndexOnStagingMiddleware"]

if DEBUG:
    MIDDLEWARE += ["django_browser_reload.middleware.BrowserReloadMiddleware"]

# ────────────────────────────────
# URLS / WSGI
# ────────────────────────────────
ROOT_URLCONF = "WBF.urls"
WSGI_APPLICATION = "WBF.wsgi.application"

# ────────────────────────────────
# TEMPLATES
# ────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                # Tes CP projet
                "core.context_processors.flags",
                "core.context_processors.volunteer_cta",
                "core.context_processors.latest_news",
                "notifications.context_processors.notifications_badge",
                "legal.context_processors.legal_outdated",
                # Django
                "django.template.context_processors.debug",
                "django.template.context_processors.request",  # requis par allauth
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ────────────────────────────────
# AUTH / ALLAUTH
# ────────────────────────────────
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/accounts/redirect/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"

# ────────────────────────────────
# DATABASE
# ────────────────────────────────
DATABASES = {}
DB_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRESQL_ADDON_URI")
USE_DB_URL = env_bool("DJANGO_USE_DB_URL", not DEBUG)

if USE_DB_URL and DB_URL:
    DATABASES["default"] = dj_database_url.parse(DB_URL, conn_max_age=600)
    if USE_HTTPS:
        DATABASES["default"].setdefault("OPTIONS", {}).update({"sslmode": "require"})
elif DEBUG:
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
else:
    # Fallback Clever Cloud (variables unitaires)
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRESQL_ADDON_DB"),
        "USER": os.getenv("POSTGRESQL_ADDON_USER"),
        "PASSWORD": os.getenv("POSTGRESQL_ADDON_PASSWORD"),
        "HOST": os.getenv("POSTGRESQL_ADDON_HOST", "localhost"),
        "PORT": os.getenv("POSTGRESQL_ADDON_PORT", "5432"),
        "OPTIONS": {"sslmode": "require"} if USE_HTTPS else {},
    }
DATABASES["default"]["CONN_MAX_AGE"] = int(os.getenv("DB_CONN_MAX_AGE", "0"))  # 0 = ferme après chaque requête
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# Utiliser des sessions en cookies signés (pas de hits DB pour les sessions)
SESSION_ENGINE = os.getenv(
    "DJANGO_SESSION_ENGINE",
    "django.contrib.sessions.backends.signed_cookies"
)
SESSION_COOKIE_AGE = int(os.getenv("DJANGO_SESSION_COOKIE_AGE", "1209600"))  # 14 jours
SESSION_SAVE_EVERY_REQUEST = False  # cookie pas regénéré à chaque hit


# ────────────────────────────────
# SÉCURITÉ (prod)
# ────────────────────────────────
# Redirection HTTPS et cookies sécurisés
SECURE_SSL_REDIRECT = USE_HTTPS
SESSION_COOKIE_SECURE = USE_HTTPS
CSRF_COOKIE_SECURE = USE_HTTPS

# HSTS (activé si HTTPS)
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000")) if USE_HTTPS else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True) if USE_HTTPS else False
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", True) if USE_HTTPS else False

# Autres en-têtes de sécurité
SECURE_REFERRER_POLICY = os.getenv("DJANGO_SECURE_REFERRER_POLICY", "same-origin")
X_FRAME_OPTIONS = os.getenv("DJANGO_X_FRAME_OPTIONS", "DENY")

# CSRF Trusted Origins (depuis env OU construit depuis ALLOWED_HOSTS)
_csrf_env = [o.strip() for o in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
CSRF_TRUSTED_ORIGINS = _csrf_env or [f"https://{h}" for h in ALLOWED_HOSTS if h]

# Si l’appli tourne derrière le proxy TLS (Clever Cloud envoie X-Forwarded-Proto)
if env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", not DEBUG):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ────────────────────────────────
# PASSWORDS
# ────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "accounts.validators_fr.UserAttributeSimilarityValidatorFR",
        "OPTIONS": {"user_attributes": ("username", "email", "first_name", "last_name")},
    },
    {"NAME": "accounts.validators_fr.MinimumLengthValidatorFR", "OPTIONS": {"min_length": 8}},
    {"NAME": "accounts.validators_fr.CommonPasswordValidatorFR"},
    {"NAME": "accounts.validators_fr.NumericPasswordValidatorFR"},
]

# ────────────────────────────────
# I18N / L10N
# ────────────────────────────────
LANGUAGE_CODE = "fr"
LANGUAGES = [("fr", "Français")]
USE_I18N = True
TIME_ZONE = "Europe/Paris"
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

# ────────────────────────────────
# STATIC / MEDIA
# ────────────────────────────────
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]        # sources
STATIC_ROOT = BASE_DIR / "staticfiles"          # collectstatic (prod)

# WhiteNoise storage (optionnel)
if _use_whitenoise:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


# === MEDIA (FS Bucket monté) ===
# Correspond exactement au point de montage défini dans CC_FS_BUCKET
MEDIA_ROOT = "/media"                      # ← le dossier monté par FS Bucket
MEDIA_URL = "/media/"                      # URL publique servie par Django

# Optionnel : activer un flag pour servir les médias par Django en prod
SERVE_MEDIA = os.getenv("DJANGO_SERVE_MEDIA", "1") == "1"

# ────────────────────────────────
# EMAIL
# ────────────────────────────────
import os

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))

# Supporte SSL et TLS (mais pas les deux à la fois)
def _env_bool(k, default=False):
    return os.getenv(k, str(default)).lower() in {"1", "true", "yes", "on"}

EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", False)
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", False)

# Si rien n'est précisé → TLS (587)
if not EMAIL_USE_SSL and not EMAIL_USE_TLS:
    EMAIL_USE_TLS = True
# Si les deux sont à True → privilégier SSL (on coupe TLS)
if EMAIL_USE_SSL and EMAIL_USE_TLS:
    EMAIL_USE_TLS = False

EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "ne-pas'repondre@bamuwellbeing.org")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# En dev, pas d'envoi réel (les mails s'affichent en console)
from django.conf import settings as _s
if _s.DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "bamu.wellbeing_foundation@bamuwellbeing.org")

# ────────────────────────────────
# LOGGING (console en prod)
# ────────────────────────────────
LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO" if not DEBUG else "DEBUG")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
}

# ────────────────────────────────
# AUTRES / PAIEMENT
# ────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

FLW_PUBLIC_KEY = os.getenv("FLW_PUBLIC_KEY", "")
FLW_SECRET_KEY = os.getenv("FLW_SECRET_KEY", "")
FLW_WEBHOOK_SECRET = os.getenv("FLW_WEBHOOK_SECRET", "")  # 'verif-hash' header sur webhook
FLW_SANDBOX = env_bool("FLW_SANDBOX", True)

