import os
import django

# 1️⃣ Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carehome_project.settings')

# 2️⃣ Initialize Django
django.setup()

# 3️⃣ Import your CustomUser model
from core.models import CustomUser

# 4️⃣ Superuser credentials — change as needed
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin123!")
ADMIN_FIRST_NAME = os.environ.get("ADMIN_FIRST_NAME", "Admin")
ADMIN_LAST_NAME = os.environ.get("ADMIN_LAST_NAME", "User")
ADMIN_ROLE = CustomUser.Manager  # Only managers can access admin panel

# 5️⃣ Create superuser if it doesn’t exist
try:
    user = CustomUser.objects.get(email=ADMIN_EMAIL)
    print(f"⚠️ Superuser '{ADMIN_EMAIL}' already exists. Skipping creation.")
except CustomUser.DoesNotExist:
    user = CustomUser.objects.create_superuser(
        email=ADMIN_EMAIL,
        password=ADMIN_PASSWORD,
        first_name=ADMIN_FIRST_NAME,
        last_name=ADMIN_LAST_NAME,
        role=ADMIN_ROLE
    )
    print(f"✅ Superuser '{ADMIN_EMAIL}' created successfully with role '{ADMIN_ROLE}'.")