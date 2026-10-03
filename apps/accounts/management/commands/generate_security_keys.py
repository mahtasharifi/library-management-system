"""Generate deployment secrets without persisting them."""

from django.core.management import BaseCommand
from django.core.management.utils import get_random_secret_key

from apps.accounts.mfa import generate_encryption_key


class Command(BaseCommand):
    help = "Generate fresh Django and MFA encryption keys for a secret manager."

    def handle(self, *args, **options):
        self.stdout.write(f"DJANGO_SECRET_KEY={get_random_secret_key()}")
        self.stdout.write(f"MFA_ENCRYPTION_KEYS={generate_encryption_key()}")
        self.stdout.write(self.style.WARNING("Store these values in the deployment secret manager; do not commit them."))
