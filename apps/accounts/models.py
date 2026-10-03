"""Persistent models owned by the accounts domain."""

from __future__ import annotations

import uuid
from pathlib import Path

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from common.i18n import translate as t


def avatar_upload_path(instance, filename: str) -> str:
    """Generate a server-controlled avatar filename."""
    extension = Path(filename).suffix.lower()
    return f"avatars/{uuid.uuid4().hex}{extension}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone_number = models.CharField(max_length=15, blank=True, null=True, verbose_name=t("common.labels.phone"))
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True, verbose_name=t("accounts.profile.avatar"))

    class Meta:
        db_table = "user_profiles"
        verbose_name = t("accounts.profile.model.single")
        verbose_name_plural = t("accounts.profile.model.plural")

    def __str__(self) -> str:
        return t("accounts.profile.display", username=self.user.username)


class MfaCredential(models.Model):
    """Encrypted TOTP enrollment state and one-time recovery-code hashes."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="mfa_credential")
    encrypted_secret = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=False)
    last_counter = models.BigIntegerField(blank=True, null=True)
    recovery_code_hashes = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=1)
    verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mfa_credentials"
        verbose_name = t("accounts.mfa.model.single")
        verbose_name_plural = t("accounts.mfa.model.plural")

    def __str__(self) -> str:
        state = t("accounts.mfa.state.enabled") if self.is_enabled else t("accounts.mfa.state.disabled")
        return f"MFA {self.user.username} ({state})"


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    """Keep the profile relation available for every newly created user."""
    if created:
        UserProfile.objects.get_or_create(user=instance)
