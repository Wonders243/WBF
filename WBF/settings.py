# WBF/settings.py
from pathlib import Path
from dotenv import load_dotenv
import os
import sys

# ────────────────────────────────
# BASE / ENV
# ────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent


BASE_DIR = Path(__file__).resolve().parent.parent
DOTENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=str(DOTENV_PATH), override=False)


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key")  # ⚠️ remplace en prod
DEBUG = env_bool("DJANGO_DEBUG", True)
USE_HTTPS = env_bool("DJANGO_USE_HTTPS", not DEBUG)

ALLOWED_HOSTS = [h for h in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if h] if not DEBUG else []

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

    # Tiers
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "widget_tweaks",          # pour customiser les widgets dans les templates
    "django_cleanup.apps.CleanupConfig",

# Projet
    "core.apps.CoreConfig",
    "accounts.apps.AccountsConfig",
    "staff.apps.StaffConfig",
    "notifications",
    "legal",
    "payments",
]

ACCOUNT_FORMS = {
    "reset_password": "accounts.forms.StyledResetPasswordForm",
    "signup": "accounts.forms.TermsSignupForm",
}

import os

PAYMENT_MAINTENANCE = os.getenv("PAYMENT_MAINTENANCE", "False").lower() == "true"
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "")
SUPPORT_PHONE = os.getenv("SUPPORT_PHONE", "")
SUPPORT_WHATSAPP = os.getenv("SUPPORT_WHATSAPP", "")
SUPPORT_URL = os.getenv("SUPPORT_URL", "")



# Reload auto uniquement en dev
if DEBUG:
    INSTALLED_APPS += ["django_browser_reload"]

SITE_ID = int(os.getenv("DJANGO_SITE_ID", 1))

# ────────────────────────────────
# MIDDLEWARE
# ────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "core.middleware.LastUrlMiddleware",

    # i18n : doit venir APRÈS Session et AVANT Common
    "django.middleware.locale.LocaleMiddleware",

    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    # Allauth (après AuthenticationMiddleware)
    "allauth.account.middleware.AccountMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if DEBUG:
    MIDDLEWARE += ["django_browser_reload.middleware.BrowserReloadMiddleware"]

# Optionnel: WhiteNoise (servir les fichiers statiques en prod)
# Active via env DJANGO_USE_WHITENOISE=1 et installe le paquet "whitenoise"
if env_bool("DJANGO_USE_WHITENOISE", False):
    try:
        idx = next((i for i, x in enumerate(MIDDLEWARE) if x.endswith("SecurityMiddleware")), 0)
    except Exception:
        idx = 0
    if "whitenoise.middleware.WhiteNoiseMiddleware" not in MIDDLEWARE:
        MIDDLEWARE.insert(idx + 1, "whitenoise.middleware.WhiteNoiseMiddleware")


# ────────────────────────────────
INSTALLED_APPS += ["crispy_forms", "crispy_tailwind"]
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"
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
                "core.context_processors.flags",
                "core.context_processors.volunteer_cta",
                "core.context_processors.latest_news",
                "notifications.context_processors.notifications_badge",
                "legal.context_processors.legal_outdated",
               # "accounts.context_processors.unread_notifications",  # ton CP
                "django.template.context_processors.debug",
                "django.template.context_processors.request",  # requis par allauth
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]




# ────────────────────────────────
# AUTHENTIFICATION / ALLAUTH
# ────────────────────────────────
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/accounts/redirect/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"


# Allauth moderne
ACCOUNT_LOGIN_METHODS = {"username", "email"}   # login par email OU username
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
#ACCOUNT_EMAIL_VERIFICATION = "none"             # dev: pas de vérif email
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
# Providers (Google) — ⚠️ mets tes secrets dans l’env
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

# ────────────────────────────────
# DATABASE
# ────────────────────────────────
import dj_database_url

DATABASES = {}
# Prefer DB URL in production; in dev, only if explicitly enabled
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
    # Fallback sur les variables unitaires Clever Cloud
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRESQL_ADDON_DB"),
        "USER": os.getenv("POSTGRESQL_ADDON_USER"),
        "PASSWORD": os.getenv("POSTGRESQL_ADDON_PASSWORD"),
        "HOST": os.getenv("POSTGRESQL_ADDON_HOST", "localhost"),
        "PORT": os.getenv("POSTGRESQL_ADDON_PORT", "5432"),
        "OPTIONS": {"sslmode": "require"} if USE_HTTPS else {},
    }


# ────────────────────────────────
# SECURITY (prod)
# ────────────────────────────────

# Redirection HTTPS et cookies sécurisés
SECURE_SSL_REDIRECT = USE_HTTPS
SESSION_COOKIE_SECURE = USE_HTTPS
CSRF_COOKIE_SECURE = USE_HTTPS

# HSTS (seulement si HTTPS est actif)
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000")) if USE_HTTPS else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True) if USE_HTTPS else False
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", True) if USE_HTTPS else False

# Autres en-têtes de sécurité
SECURE_REFERRER_POLICY = os.getenv("DJANGO_SECURE_REFERRER_POLICY", "same-origin")
X_FRAME_OPTIONS = os.getenv("DJANGO_X_FRAME_OPTIONS", "DENY")

# CSRF Trusted Origins (ex: https://exemple.com,https://www.exemple.com)
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

# Si l’appli tourne derrière un proxy qui termine TLS (nginx, traefik…)
if env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ────────────────────────────────
# PASSWORDS
# ────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
{"NAME": "accounts.validators_fr.UserAttributeSimilarityValidatorFR",
"OPTIONS": {"user_attributes": ("username", "email", "first_name", "last_name")}},
{"NAME": "accounts.validators_fr.MinimumLengthValidatorFR",
"OPTIONS": {"min_length": 8}},
{"NAME": "accounts.validators_fr.CommonPasswordValidatorFR"},
{"NAME": "accounts.validators_fr.NumericPasswordValidatorFR"},
]

# ────────────────────────────────
# I18N / L10N
# ────────────────────────────────
LANGUAGE_CODE = "fr"
LANGUAGES = [("fr", "Français")]                # FR uniquement
USE_I18N = True

TIME_ZONE = "Europe/Paris"
USE_TZ = True

# Si tu ajoutes des traductions custom: python manage.py makemessages
LOCALE_PATHS = [BASE_DIR / "locale"]

# ────────────────────────────────
# STATIC / MEDIA
# ────────────────────────────────
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]        # tes assets sources
STATIC_ROOT = BASE_DIR / "staticfiles"          # collectstatic (prod)
# ───────── S3 / Cellar pour les MEDIAS (uploads) ─────────
# Active si USE_S3_MEDIA=1 dans les variables d'env
if env_bool("USE_S3_MEDIA", False):
    INSTALLED_APPS += ["storages"]

    # On lit d'abord les variables standard AWS_* si tu les as créées,
    # sinon on retombe sur celles injectées par l'addon Cellar (CELLAR_ADDON_*)
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("CELLAR_ADDON_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY") or os.getenv("CELLAR_ADDON_KEY_SECRET", "")
    AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL") or (
        f"https://{os.getenv('CELLAR_ADDON_HOST', '')}"
    )
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "")  # ← ton bucket

    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_ADDRESSING_STYLE = "virtual"  # Cellar supporte le style virtual-host
    AWS_DEFAULT_ACL = None               # pas d'ACL implicite
    AWS_QUERYSTRING_AUTH = env_bool("AWS_QUERYSTRING_AUTH", False)  # False => URLs publiques

    # Tous les FileField/ImageField iront sur S3
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
else:
    # Stockage local (développement)
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"


# WhiteNoise storage (optionnel)
if env_bool("DJANGO_USE_WHITENOISE", False):
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ────────────────────────────────
# EMAIL
# ────────────────────────────────
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
    EMAIL_HOST = os.getenv("EMAIL_HOST", "")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@exemple.org")

# ────────────────────────────────
# LOGGING (console en prod)
# ────────────────────────────────
LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO" if not DEBUG else "DEBUG")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
}
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "contact@exemple.org")

# ────────────────────────────────
# AUTRES
# ────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Paiement (Flutterwave / Mobile Money Afrique)
FLW_PUBLIC_KEY = os.getenv("FLW_PUBLIC_KEY", "")
FLW_SECRET_KEY = os.getenv("FLW_SECRET_KEY", "")
FLW_WEBHOOK_SECRET = os.getenv("FLW_WEBHOOK_SECRET", "")  # 'verif-hash' header sur webhook
FLW_SANDBOX = env_bool("FLW_SANDBOX", True)
