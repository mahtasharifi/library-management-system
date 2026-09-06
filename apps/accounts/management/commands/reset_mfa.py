"""Administrative MFA recovery command."""

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.mfa import reset_mfa


class Command(BaseCommand):
    help = "Reset MFA for one user and invalidate that user's active sessions."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=options["username"])
        except User.DoesNotExist as exc:
            raise CommandError("User not found.") from exc

        reset_mfa(user)
        now = timezone.now()
        for session in Session.objects.filter(expire_date__gte=now).iterator():
            data = session.get_decoded()
            if str(data.get("_auth_user_id")) == str(user.pk):
                session.delete()
        self.stdout.write(self.style.SUCCESS(f"MFA reset and active sessions invalidated for {user.username}."))
