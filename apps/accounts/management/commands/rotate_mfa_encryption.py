"""Re-encrypt stored MFA secrets with the primary configured key."""

from django.core.management import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.mfa import decrypt_secret, encrypt_secret
from apps.accounts.models import MfaCredential


class Command(BaseCommand):
    help = (
        "Re-encrypt all enrolled MFA secrets with the first key in MFA_ENCRYPTION_KEYS. "
        "Keep the previous key(s) in the key ring until this command succeeds."
    )

    def handle(self, *args, **options):
        updated = 0
        try:
            with transaction.atomic():
                credentials = MfaCredential.objects.select_for_update().exclude(encrypted_secret="")
                for credential in credentials.iterator():
                    plaintext = decrypt_secret(credential.encrypted_secret)
                    credential.encrypted_secret = encrypt_secret(plaintext)
                    credential.save(update_fields=["encrypted_secret", "updated_at"])
                    updated += 1
        except Exception as exc:
            raise CommandError(
                "MFA key rotation failed. No partial rotation was committed; verify the configured key ring."
            ) from exc
        self.stdout.write(self.style.SUCCESS(f"Re-encrypted {updated} MFA credential(s) with the primary key."))
