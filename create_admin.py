from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = "Create a superuser with manager role"

    def handle(self, *args, **options):
        email = "admin@example.com"
        password = "Admin123!"

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING("Superuser already exists"))
            return

        user = User.objects.create_superuser(
            email=email,
            password=password,
            first_name="Admin",
            last_name="User",
            role=User.Manager,   # IMPORTANT
        )

        self.stdout.write(self.style.SUCCESS(
            f"Superuser created successfully: {email}"
        ))