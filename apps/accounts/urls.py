from django.urls import path

from .views import (
    CustomLoginView,
    CustomLogoutView,
    change_password_view,
    mfa_recovery_codes_view,
    mfa_rotate_view,
    mfa_security_view,
    mfa_setup_view,
    mfa_verify_view,
    notification_read_view,
    notifications_read_view,
    notifications_recent_view,
    notifications_view,
    profile_edit_view,
    profile_view,
    signup_view,
)

app_name = "accounts"

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("signup/", signup_view, name="signup"),
    path("mfa/setup/", mfa_setup_view, name="mfa_setup"),
    path("mfa/verify/", mfa_verify_view, name="mfa_verify"),
    path("mfa/security/", mfa_security_view, name="mfa_security"),
    path("mfa/rotate/", mfa_rotate_view, name="mfa_rotate"),
    path("mfa/recovery-codes/", mfa_recovery_codes_view, name="mfa_recovery_codes"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),
    path("profile/", profile_view, name="profile"),
    path("notifications/", notifications_view, name="notifications"),
    path("notifications/recent/", notifications_recent_view, name="notifications_recent"),
    path("notifications/read/", notifications_read_view, name="notifications_read"),
    path("notifications/<int:notification_id>/read/", notification_read_view, name="notification_read"),
    path("profile/edit/", profile_edit_view, name="profile_edit"),
    path("profile/change-password/", change_password_view, name="change_password"),
]
