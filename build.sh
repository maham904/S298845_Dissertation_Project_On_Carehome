#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies
poetry install

# Convert poetry.lock to requirements.txt
poetry export -f requirements.txt --output requirements.txt

# Install Python dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Apply database migrations
python manage.py migrate