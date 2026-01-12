#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install --use-deprecated=legacy-resolver -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate

# Create superuser once (only if it doesn't exist)
python manage.py shell -c "
from django.contrib.auth import get_user_model
import os
User = get_user_model()
email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
pwd = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
fn = os.environ.get('DJANGO_SUPERUSER_FIRST_NAME', 'Admin')
ln = os.environ.get('DJANGO_SUPERUSER_LAST_NAME', 'User')

if email and pwd and not User.objects.filter(email=email).exists():
    User.objects.create_superuser(email=email, password=pwd, first_name=fn, last_name=ln)
    print('✅ Superuser created:', email)
else:
    print('ℹ️ Superuser exists already, or env vars missing.')
"
