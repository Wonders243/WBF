Déploiement en production — WBF

Variables d’environnement (recommandé via un fichier `.env` ou le système d’hébergement):

- DJANGO_SECRET_KEY: clé secrète (obligatoire en prod)
- DJANGO_DEBUG=0: désactive le mode debug
- DJANGO_ALLOWED_HOSTS: domaines autorisés, séparés par des virgules (ex: exemple.com,www.exemple.com)
- DJANGO_CSRF_TRUSTED_ORIGINS: origines CSRF avec schéma, séparées par des virgules (ex: https://exemple.com,https://www.exemple.com)
- DJANGO_USE_HTTPS=1: force les réglages HTTPS (redir., cookies sécurisés, HSTS)
- DJANGO_SECURE_HSTS_SECONDS=31536000: durée HSTS (si HTTPS activé)
- DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=1: inclure sous-domaines (si applicable)
- DJANGO_SECURE_HSTS_PRELOAD=1: autoriser preload HSTS
- DJANGO_SECURE_PROXY_SSL_HEADER=1: si un proxy termine TLS (nginx/traefik), active `SECURE_PROXY_SSL_HEADER`

Base de données (PostgreSQL):

- PGDATABASE, PGUSER, PGPASSWORD, PGHOST, PGPORT (par défaut 5432)

Email:

- EMAIL_BACKEND (par défaut SMTP), EMAIL_HOST, EMAIL_PORT (587), EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_USE_TLS=1
- DEFAULT_FROM_EMAIL (ex: no-reply@exemple.org)

Static files:

- DJANGO_USE_WHITENOISE=1 (optionnel) si vous servez les assets via WhiteNoise. Installez `whitenoise` et ajoutez-le à requirements, puis exécutez `collectstatic`.

Étapes de déploiement typiques:

1. Appliquer les migrations: `python manage.py migrate`
2. Collecter les statiques: `python manage.py collectstatic --noinput`
3. Créer un superuser (si besoin): `python manage.py createsuperuser`
4. Démarrer via un serveur WSGI/ASGI (gunicorn/uvicorn) derrière un proxy HTTPS

Notes:

- En prod, `USE_HTTPS` s’active par défaut (si `DJANGO_DEBUG=0`). Réglez `DJANGO_USE_HTTPS=0` uniquement si vous n’avez pas encore de HTTPS en frontal.
- Pour CSRF Trusted Origins, inclure le schéma (ex: `https://mon-domaine.tld`).

