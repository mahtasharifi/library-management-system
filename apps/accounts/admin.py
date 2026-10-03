"""
Custom Django admin for User & UserProfile.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import UserProfile
from common.i18n import translate as t


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = t("accounts.admin.profile_section")


class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_phone_number')

    def get_phone_number(self, obj):
        """Return the profile phone number when available."""
        try:
            return obj.profile.phone_number
        except UserProfile.DoesNotExist:
            return '-'
    get_phone_number.short_description = t("common.labels.phone")


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number']
    search_fields = ['user__username', 'user__email', 'phone_number']