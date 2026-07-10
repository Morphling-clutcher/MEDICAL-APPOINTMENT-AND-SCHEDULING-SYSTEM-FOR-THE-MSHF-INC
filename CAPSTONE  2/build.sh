#!/usr/bin/env bash
# Render build script: installs Python + JS deps, builds the Vite bundle,
# collects static files, and runs migrations.
set -o errexit

pip install -r requirements.txt

npm ci
npm run build

python manage.py collectstatic --no-input
python manage.py migrate

# Optionally create the first admin account. Set DJANGO_SUPERUSER_USERNAME,
# DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD in Render's env vars;
# the "|| true" keeps re-deploys from failing once the account exists.
if [[ -n "${DJANGO_SUPERUSER_USERNAME:-}" ]]; then
    python manage.py createsuperuser --no-input || true
fi
