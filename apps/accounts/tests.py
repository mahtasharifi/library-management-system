from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.books.models import UserNotification
from . import mfa
from .models import MfaCredential


class AccountPageTests(TestCase):
    def setUp(self):
        self.password = 'A-secure-pass-123'
        self.user = User.objects.create_user(
            username='reader',
            email='reader@example.com',
            password=self.password,
            first_name='کاربر',
            last_name='آزمایشی',
        )

    def test_login_and_signup_pages_render(self):
        login_response = self.client.get(reverse('accounts:login'))
        signup_response = self.client.get(reverse('accounts:signup'))

        self.assertEqual(login_response.status_code, 200)
        self.assertContains(login_response, 'ورود به حساب کاربری')
        self.assertEqual(signup_response.status_code, 200)
        self.assertContains(signup_response, 'ایجاد حساب کاربری')

    def test_profile_edit_updates_user_and_profile(self):
        self.client.login(username=self.user.username, password=self.password)
        response = self.client.post(
            reverse('accounts:profile_edit'),
            {
                'first_name': 'مهتا',
                'last_name': 'شریفی',
                'email': 'mahta@example.com',
                'phone_number': '09121234567',
            },
        )

        self.assertRedirects(response, reverse('accounts:profile'))
        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, 'مهتا')
        self.assertEqual(self.user.profile.phone_number, '09121234567')

    def test_password_change_keeps_user_logged_in(self):
        self.client.login(username=self.user.username, password=self.password)
        response = self.client.post(
            reverse('accounts:change_password'),
            {
                'old_password': self.password,
                'new_password1': 'Another-secure-pass-456',
                'new_password2': 'Another-secure-pass-456',
            },
        )

        self.assertRedirects(response, reverse('accounts:profile'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_notifications_have_a_separate_page_and_can_be_marked_read(self):
        notification = UserNotification.objects.create(
            user=self.user,
            kind='answered',
            title='پاسخ کتابخانه',
            message='کتاب پیشنهادی شما بررسی شد.',
        )
        self.client.login(username=self.user.username, password=self.password)
        profile = self.client.get(reverse('accounts:profile'))
        notifications = self.client.get(reverse('accounts:notifications'))

        self.assertNotContains(profile, 'کتاب پیشنهادی شما بررسی شد.')
        self.assertContains(notifications, 'کتاب پیشنهادی شما بررسی شد.')
        self.assertContains(notifications, 'notifications-page')

        response = self.client.post(reverse('accounts:notification_read', args=[notification.id]))
        self.assertRedirects(response, reverse('accounts:notifications'))
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_recent_notifications_api_returns_only_latest_five(self):
        for number in range(7):
            UserNotification.objects.create(
                user=self.user,
                kind='answered',
                title=f'اعلان {number}',
                message=f'متن اعلان {number}',
            )
        self.client.login(username=self.user.username, password=self.password)

        response = self.client.get(reverse('accounts:notifications_recent'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertEqual(len(payload['items']), 5)
        self.assertEqual(payload['unread_count'], 7)
        self.assertEqual(payload['items'][0]['title'], 'اعلان 6')

    def test_profile_does_not_expose_dedicated_account_security_section(self):
        self.client.login(username=self.user.username, password=self.password)

        response = self.client.get(reverse('accounts:profile'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse('accounts:mfa_security'))
        self.assertNotContains(response, 'امنیت حساب')

    def test_legacy_mfa_security_url_redirects_to_profile(self):
        self.client.login(username=self.user.username, password=self.password)

        response = self.client.get(reverse('accounts:mfa_security'))

        self.assertRedirects(response, reverse('accounts:profile'))

    def test_profile_uses_compact_layout_and_persian_date_hooks(self):
        self.client.login(username=self.user.username, password=self.password)

        response = self.client.get(reverse('accounts:profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'profile-overview')
        self.assertContains(response, 'profile-history-accordions')
        self.assertContains(response, 'profile-history-disclosure', count=2)
        self.assertContains(response, 'data-persian-date="date"')
        self.assertContains(response, 'data-notification-toggle')


class MultiFactorAuthenticationTests(TestCase):
    def setUp(self):
        self.password = 'A-secure-pass-123'
        self.staff = User.objects.create_user(
            username='mfa-manager', email='manager@example.com',
            password=self.password, is_staff=True,
        )

    @override_settings(MFA_ENFORCEMENT_ENABLED=True)
    def test_staff_password_login_stays_anonymous_until_mfa_finishes(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': self.staff.username, 'password': self.password, 'remember_me': 'on',
        })
        self.assertRedirects(response, reverse('accounts:mfa_setup'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.session.get('mfa_pending_user_id'), self.staff.pk)

        setup_page = self.client.get(reverse('accounts:mfa_setup'))
        self.assertEqual(setup_page.status_code, 200)
        secret = mfa.pending_secret(self.staff)
        self.assertTrue(secret)
        response = self.client.post(reverse('accounts:mfa_setup'), {'code': mfa.totp_code(secret)})
        self.assertRedirects(response, reverse('accounts:mfa_recovery_codes'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.staff.pk)
        credential = MfaCredential.objects.get(user=self.staff)
        self.assertTrue(credential.is_enabled)
        self.assertNotEqual(credential.encrypted_secret, secret)

    def test_totp_replay_is_rejected(self):
        _, secret = mfa.start_enrollment(self.staff)
        initial = mfa.totp_code(secret)
        self.assertIsNotNone(mfa.enable_enrollment(self.staff, initial))
        self.assertFalse(mfa.verify_second_factor(self.staff, initial).accepted)

    def test_recovery_code_is_one_time(self):
        _, secret = mfa.start_enrollment(self.staff)
        codes = mfa.enable_enrollment(self.staff, mfa.totp_code(secret))
        code = codes[0]
        self.assertTrue(mfa.verify_second_factor(self.staff, code).accepted)
        self.assertFalse(mfa.verify_second_factor(self.staff, code).accepted)

    def test_mfa_encryption_key_ring_supports_rotation(self):
        old_key = mfa.generate_encryption_key()
        new_key = mfa.generate_encryption_key()
        with override_settings(MFA_ENCRYPTION_KEYS=[old_key], MFA_ENCRYPTION_KEY=old_key):
            _, secret = mfa.start_enrollment(self.staff)
            old_ciphertext = MfaCredential.objects.get(user=self.staff).encrypted_secret

        with override_settings(MFA_ENCRYPTION_KEYS=[new_key, old_key], MFA_ENCRYPTION_KEY=new_key):
            self.assertEqual(mfa.decrypt_secret(old_ciphertext), secret)
            call_command('rotate_mfa_encryption', verbosity=0)
            rotated = MfaCredential.objects.get(user=self.staff).encrypted_secret
            self.assertNotEqual(rotated, old_ciphertext)

        with override_settings(MFA_ENCRYPTION_KEYS=[new_key], MFA_ENCRYPTION_KEY=new_key):
            self.assertEqual(mfa.decrypt_secret(rotated), secret)

    @override_settings(MFA_ENFORCEMENT_ENABLED=True)
    def test_staff_session_without_second_factor_cannot_open_admin_dashboard(self):
        self.client.login(username=self.staff.username, password=self.password)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('accounts:mfa_setup'))
        self.assertNotIn('_auth_user_id', self.client.session)
