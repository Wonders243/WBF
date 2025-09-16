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
ACCOUNT_EMAIL_VERIFICATION = "none"             # dev: pas de vérif email
##ACCOUNT_EMAIL_VERIFICATION = "mandatory"
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

# Support DATABASE_URL if provided (Heroku/Render). Falls back to
# SQLite in DEBUG or manual PG* env vars in production.
DATABASES = {}
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL:
    try:
        import dj_database_url  # type: ignore
        DATABASES["default"] = dj_database_url.parse(DATABASE_URL, conn_max_age=600)
        # Enforce SSL when HTTPS is enabled
        if USE_HTTPS:
            DATABASES["default"].setdefault("OPTIONS", {}).update({"sslmode": "require"})
    except Exception as e:
        print("[settings] Failed to parse DATABASE_URL:", e, file=sys.stderr)
        # soft-fallback below

if not DATABASES.get("default"):
    if DEBUG:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }
    else:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": os.getenv("PGDATABASE"),
                "USER": os.getenv("PGUSER"),
                "PASSWORD": os.getenv("PGPASSWORD"),
                "HOST": os.getenv("PGHOST", "localhost"),
                "PORT": os.getenv("PGPORT", "5432"),
            }
        }

# ────────────────────────────────
# SECURITY (prod)
# ────────────────────────────────
# Active par défaut en production; peut être forçé via DJANGO_USE_HTTPS
USE_HTTPS = env_bool("DJANGO_USE_HTTPS", not DEBUG)

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
