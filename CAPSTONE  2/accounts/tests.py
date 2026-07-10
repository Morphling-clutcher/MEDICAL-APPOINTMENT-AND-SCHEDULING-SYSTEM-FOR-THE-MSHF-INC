import sys
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

# Django 4.2's BaseContext.__copy__ relies on copy(super()), which Python
# 3.13+ removed support for (Django 4.2 predates those Pythons and never got
# the fix backported). The test client copies the template context on every
# rendered response, so without this shim ANY test that renders a template
# crashes with "AttributeError: 'super' object has no attribute 'dicts'".
# This replicates the fix Django 5.x shipped; it's a no-op on Python <= 3.12.
if sys.version_info >= (3, 13):
    from django.template.context import BaseContext

    def _base_context_copy(self):
        duplicate = self.__class__.__new__(self.__class__)
        duplicate.__dict__ = self.__dict__.copy()
        duplicate.dicts = self.dicts[:]
        return duplicate

    BaseContext.__copy__ = _base_context_copy

from .models import CustomUser, PatientProfile, SocialAccount
from .social_views import STATE_SESSION_KEY
from notifications.models import Notification

# Every callback test overrides these so the Google provider counts as
# configured regardless of what's in the developer's local .env.
GOOGLE_CONFIGURED = {
    'GOOGLE_OAUTH_CLIENT_ID': 'test-client-id',
    'GOOGLE_OAUTH_CLIENT_SECRET': 'test-client-secret',
}

# What accounts.social_auth.fetch_user_profile would return for a normal
# Google account. Individual tests override fields as needed.
GOOGLE_PROFILE = {
    'provider_user_id': '108234567890',
    'email': 'juan.delacruz@gmail.com',
    'email_verified': True,
    'first_name': 'Juan',
    'last_name': 'Dela Cruz',
}


class SocialLoginTestBase(TestCase):
    def setUp(self):
        self.client = Client()
        self.start_url = reverse('accounts:social_start', args=['google'])
        self.callback_url = reverse('accounts:social_callback', args=['google'])

    def _prime_state(self, provider='google', value='teststate123'):
        session = self.client.session
        session[STATE_SESSION_KEY] = {'provider': provider, 'value': value}
        session.save()
        return value

    def _callback(self, profile=None, state='teststate123', code='authcode'):
        """Primes session state and hits the callback with fetch_user_profile
        mocked out — the only network-touching piece of the flow."""
        self._prime_state(value=state)
        with patch('accounts.social_views.fetch_user_profile', return_value=dict(profile or GOOGLE_PROFILE)):
            return self.client.get(self.callback_url, {'state': state, 'code': code})

    def _logged_in_user(self):
        session = self.client.session
        user_id = session.get('_auth_user_id')
        return CustomUser.objects.get(pk=user_id) if user_id else None


class SocialButtonVisibilityTests(SocialLoginTestBase):
    @override_settings(GOOGLE_OAUTH_CLIENT_ID='', GOOGLE_OAUTH_CLIENT_SECRET='')
    def test_google_button_disabled_when_unconfigured(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertNotContains(response, self.start_url)
        self.assertContains(response, 'Coming soon')

    @override_settings(**GOOGLE_CONFIGURED)
    def test_google_button_links_when_configured_facebook_stays_disabled(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertContains(response, self.start_url)
        self.assertNotContains(response, reverse('accounts:social_start', args=['facebook']))
        # Facebook (and mobile OTP) remain "Coming soon" placeholders.
        self.assertContains(response, 'Coming soon')


class SocialStartTests(SocialLoginTestBase):
    @override_settings(**GOOGLE_CONFIGURED)
    def test_start_sets_state_and_redirects_to_google(self):
        response = self.client.get(self.start_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('https://accounts.google.com/o/oauth2/v2/auth?'))
        stored = self.client.session.get(STATE_SESSION_KEY)
        self.assertEqual(stored['provider'], 'google')
        self.assertIn(stored['value'], response['Location'])

    @override_settings(GOOGLE_OAUTH_CLIENT_ID='', GOOGLE_OAUTH_CLIENT_SECRET='')
    def test_start_refused_when_unconfigured(self):
        response = self.client.get(self.start_url)
        self.assertRedirects(response, reverse('accounts:login'))

    @override_settings(**GOOGLE_CONFIGURED)
    def test_facebook_start_rejected_while_deferred(self):
        response = self.client.get(reverse('accounts:social_start', args=['facebook']))
        self.assertRedirects(response, reverse('accounts:login'))
        self.assertIsNone(self.client.session.get(STATE_SESSION_KEY))


@override_settings(**GOOGLE_CONFIGURED)
class SocialCallbackTests(SocialLoginTestBase):
    def test_state_mismatch_rejected(self):
        self._prime_state(value='expected-state')
        with patch('accounts.social_views.fetch_user_profile') as fetch:
            response = self.client.get(self.callback_url, {'state': 'tampered-state', 'code': 'authcode'})
        fetch.assert_not_called()
        self.assertRedirects(response, reverse('accounts:login'))
        self.assertIsNone(self._logged_in_user())

    def test_missing_state_rejected(self):
        # No session state at all (e.g. replayed callback URL).
        with patch('accounts.social_views.fetch_user_profile') as fetch:
            response = self.client.get(self.callback_url, {'state': 'anything', 'code': 'authcode'})
        fetch.assert_not_called()
        self.assertRedirects(response, reverse('accounts:login'))
        self.assertIsNone(self._logged_in_user())

    def test_state_is_single_use(self):
        self._callback()
        self.client.logout()
        # Same state again — the first callback consumed it.
        with patch('accounts.social_views.fetch_user_profile') as fetch:
            response = self.client.get(self.callback_url, {'state': 'teststate123', 'code': 'authcode'})
        fetch.assert_not_called()
        self.assertRedirects(response, reverse('accounts:login'))

    def test_user_cancelled_consent_returns_gracefully(self):
        self._prime_state()
        response = self.client.get(self.callback_url, {'error': 'access_denied'})
        self.assertRedirects(response, reverse('accounts:login'))
        self.assertIsNone(self._logged_in_user())

    def test_new_user_created_as_patient(self):
        admin = CustomUser.objects.create_user(username='admin1', password='x', role='admin')
        response = self._callback()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/patient/')

        user = CustomUser.objects.get(username='google-juan-delacruz')
        self.assertEqual(user.role, 'patient')
        self.assertEqual(user.email, GOOGLE_PROFILE['email'])
        self.assertFalse(user.has_usable_password())
        self.assertEqual(self._logged_in_user(), user)

        profile = user.patient_profile
        self.assertEqual(profile.address, '')
        self.assertEqual(profile.place_of_birth, '')

        link = SocialAccount.objects.get(user=user)
        self.assertEqual(link.provider, 'google')
        self.assertEqual(link.provider_user_id, GOOGLE_PROFILE['provider_user_id'])
        self.assertEqual(link.email_at_link, GOOGLE_PROFILE['email'])

        self.assertTrue(
            Notification.objects.filter(user=admin, message__contains=user.username).exists()
        )

    def test_returning_user_logs_in_without_duplicates(self):
        self._callback()
        self.client.logout()
        response = self._callback(state='secondvisit')
        self.assertEqual(response['Location'], '/patient/')
        self.assertEqual(CustomUser.objects.filter(username__startswith='google-').count(), 1)
        self.assertEqual(SocialAccount.objects.count(), 1)
        self.assertIsNotNone(self._logged_in_user())

    def test_username_collision_gets_numeric_suffix(self):
        CustomUser.objects.create_user(username='google-juan-delacruz', password='x', role='patient')
        self._callback()
        self.assertTrue(CustomUser.objects.filter(username='google-juan-delacruz-2').exists())

    def test_staff_email_match_refused_not_linked(self):
        staff = CustomUser.objects.create_user(
            username='sec1', password='x', role='secretary', email=GOOGLE_PROFILE['email'],
        )
        response = self._callback()
        self.assertRedirects(response, reverse('accounts:login'))
        self.assertIsNone(self._logged_in_user())
        self.assertFalse(SocialAccount.objects.exists())
        # And no shadow patient account was created either.
        self.assertEqual(CustomUser.objects.count(), 1)

    def test_existing_patient_email_match_auto_linked(self):
        patient = CustomUser.objects.create_user(
            username='juan', password='x', role='patient', email=GOOGLE_PROFILE['email'].upper(),
        )
        PatientProfile.objects.create(user=patient)
        response = self._callback()
        self.assertEqual(response['Location'], '/patient/')
        self.assertEqual(self._logged_in_user(), patient)
        link = SocialAccount.objects.get(user=patient)
        self.assertEqual(link.provider_user_id, GOOGLE_PROFILE['provider_user_id'])
        # Linked, not duplicated.
        self.assertEqual(CustomUser.objects.count(), 1)

    def test_unverified_email_refused_toward_manual_register(self):
        profile = dict(GOOGLE_PROFILE, email_verified=False)
        response = self._callback(profile=profile)
        self.assertRedirects(response, reverse('accounts:register'))
        self.assertIsNone(self._logged_in_user())
        self.assertFalse(CustomUser.objects.exists())

    def test_missing_email_refused_toward_manual_register(self):
        profile = dict(GOOGLE_PROFILE, email='')
        response = self._callback(profile=profile)
        self.assertRedirects(response, reverse('accounts:register'))
        self.assertIsNone(self._logged_in_user())
        self.assertFalse(CustomUser.objects.exists())

    def test_deactivated_linked_patient_cannot_log_in(self):
        self._callback()
        user = self._logged_in_user()
        self.client.logout()
        user.is_active = False
        user.save()
        response = self._callback(state='afterdeactivation')
        self.assertRedirects(response, reverse('accounts:login'))
        self.assertIsNone(self._logged_in_user())


@override_settings(**GOOGLE_CONFIGURED)
class BookingProfileGateTests(SocialLoginTestBase):
    """A Google-created patient has an empty profile; booking must bounce
    them to profile edit until address and place of birth are filled in."""

    def setUp(self):
        super().setUp()
        self._callback()  # logs in a freshly created social patient
        self.user = self._logged_in_user()

    def test_booking_first_step_blocked_until_profile_completed(self):
        response = self.client.get(reverse('patient:book_step1'))
        self.assertRedirects(response, reverse('accounts:profile_edit'))

        profile = self.user.patient_profile
        profile.address = '123 Mabini St., Quezon City'
        profile.place_of_birth = 'Quezon City'
        profile.save()

        response = self.client.get(reverse('patient:book_step1'))
        self.assertEqual(response.status_code, 200)

    def test_final_confirm_post_backstop_blocked(self):
        response = self.client.post(reverse('patient:book_confirm'), {
            'doctor_id': '999', 'appointment_date': '2030-01-01',
        })
        self.assertRedirects(response, reverse('accounts:profile_edit'))
