"""Coverage for the self-service "Forgot Password" flow.

Two public, unauthenticated endpoints: ``forgot_password`` (request a reset
link by username or email) and ``reset_password`` (spend a token to set a
new password). The critical property under test throughout is that
``forgot_password`` never reveals - via its response, not just its wording -
whether a given username/email belongs to a real, emailable account; that is
a genuine enumeration vector, not a hypothetical one.
"""
import json
import re
from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from api.models import PasswordResetToken, Role, User
from api.views import hash_password, verify_password


def _extract_token(email_body: str) -> str:
    match = re.search(r'reset-password\?token=([A-Za-z0-9_\-]+)', email_body)
    assert match, f'no reset link found in email body: {email_body!r}'
    return match.group(1)


class ForgotPasswordEnumerationTests(TestCase):
    """The response must be identical whether or not the account exists."""

    def setUp(self):
        role = Role.objects.get_or_create(name='buyer')[0]
        self.user = User.objects.create(
            username='realuser', password_hash=hash_password('OldPass123!'),
            email='realuser@example.com', role=role, is_active=True,
        )

    def _post(self, identifier):
        return self.client.post(
            '/api/forgot-password/',
            data=json.dumps({'username_or_email': identifier}),
            content_type='application/json',
        )

    def test_known_and_unknown_identifiers_get_byte_identical_responses(self):
        known_response = self._post('realuser')
        mail.outbox.clear()
        unknown_response = self._post('no-such-user-at-all')

        self.assertEqual(known_response.status_code, unknown_response.status_code)
        self.assertEqual(known_response.content, unknown_response.content)

    def test_known_email_and_unknown_email_get_byte_identical_responses(self):
        known_response = self._post('realuser@example.com')
        mail.outbox.clear()
        unknown_response = self._post('nobody@example.com')

        self.assertEqual(known_response.status_code, unknown_response.status_code)
        self.assertEqual(known_response.content, unknown_response.content)

    def test_account_with_no_email_on_file_gets_the_same_generic_response(self):
        role = Role.objects.get_or_create(name='buyer')[0]
        User.objects.create(username='noemailuser', password_hash='x', role=role, is_active=True)

        response = self._post('noemailuser')
        baseline = self._post('no-such-user-at-all')

        self.assertEqual(response.status_code, baseline.status_code)
        self.assertEqual(response.content, baseline.content)
        self.assertEqual(len(mail.outbox), 0)

    def test_inactive_account_gets_the_same_generic_response_and_no_email(self):
        role = Role.objects.get_or_create(name='buyer')[0]
        User.objects.create(
            username='inactiveuser', password_hash='x', email='inactive@example.com',
            role=role, is_active=False,
        )

        response = self._post('inactiveuser')
        baseline = self._post('no-such-user-at-all')

        self.assertEqual(response.status_code, baseline.status_code)
        self.assertEqual(response.content, baseline.content)
        self.assertEqual(len(mail.outbox), 0)

    def test_blank_identifier_gets_the_same_generic_response(self):
        response = self._post('')
        baseline = self._post('no-such-user-at-all')
        self.assertEqual(response.status_code, baseline.status_code)
        self.assertEqual(response.content, baseline.content)


class ForgotPasswordEmailTests(TestCase):
    def setUp(self):
        role = Role.objects.get_or_create(name='buyer')[0]
        self.user = User.objects.create(
            username='requestor1', password_hash=hash_password('OldPass123!'),
            email='requestor1@example.com', full_name='Req One',
            role=role, is_active=True,
        )

    def _post(self, identifier):
        return self.client.post(
            '/api/forgot-password/',
            data=json.dumps({'username_or_email': identifier}),
            content_type='application/json',
        )

    def test_valid_username_sends_one_email_with_a_working_link(self):
        response = self._post('requestor1')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['requestor1@example.com'])
        self.assertIn('reset-password?token=', email.body)

        self.assertEqual(PasswordResetToken.objects.filter(user=self.user, used=False).count(), 1)

    def test_valid_email_lookup_is_case_insensitive(self):
        response = self._post('REQUESTOR1@EXAMPLE.COM')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['requestor1@example.com'])

    def test_token_is_stored_hashed_not_raw(self):
        self._post('requestor1')
        raw_token = _extract_token(mail.outbox[0].body)
        stored = PasswordResetToken.objects.get(user=self.user)
        self.assertNotEqual(stored.token_hash, raw_token)

    def test_new_request_invalidates_the_previous_token(self):
        self._post('requestor1')
        first_token = _extract_token(mail.outbox[0].body)
        mail.outbox.clear()

        self._post('requestor1')
        second_token = _extract_token(mail.outbox[0].body)
        self.assertNotEqual(first_token, second_token)

        # The old link no longer works ...
        old_response = self.client.post(
            '/api/reset-password/',
            data=json.dumps({'token': first_token, 'new_password': 'BrandNewPass1!'}),
            content_type='application/json',
        )
        self.assertEqual(old_response.status_code, 400)

        # ... but the newest one does.
        new_response = self.client.post(
            '/api/reset-password/',
            data=json.dumps({'token': second_token, 'new_password': 'BrandNewPass1!'}),
            content_type='application/json',
        )
        self.assertEqual(new_response.status_code, 200)


class ResetPasswordTests(TestCase):
    def setUp(self):
        role = Role.objects.get_or_create(name='buyer')[0]
        self.user = User.objects.create(
            username='requestor1', password_hash=hash_password('OldPass123!'),
            email='requestor1@example.com', role=role, is_active=True,
        )

    def _request_token(self):
        self.client.post(
            '/api/forgot-password/',
            data=json.dumps({'username_or_email': 'requestor1'}),
            content_type='application/json',
        )
        return _extract_token(mail.outbox[-1].body)

    def _reset(self, token, new_password='BrandNewPass1!'):
        return self.client.post(
            '/api/reset-password/',
            data=json.dumps({'token': token, 'new_password': new_password}),
            content_type='application/json',
        )

    def test_valid_token_changes_the_password_end_to_end(self):
        token = self._request_token()

        response = self._reset(token, 'BrandNewPass1!')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        self.user.refresh_from_db()
        self.assertFalse(verify_password('OldPass123!', self.user.password_hash))
        self.assertTrue(verify_password('BrandNewPass1!', self.user.password_hash))

        # Full round trip through the real login endpoint: old password is
        # now rejected, new password logs in successfully.
        old_login = self.client.post(
            '/api/login/',
            data=json.dumps({'username': 'requestor1', 'password': 'OldPass123!', 'role': 'buyer'}),
            content_type='application/json',
        )
        self.assertEqual(old_login.status_code, 401)

        new_login = self.client.post(
            '/api/login/',
            data=json.dumps({'username': 'requestor1', 'password': 'BrandNewPass1!', 'role': 'buyer'}),
            content_type='application/json',
        )
        self.assertEqual(new_login.status_code, 200)

    def test_token_can_only_be_used_once(self):
        token = self._request_token()
        first = self._reset(token, 'BrandNewPass1!')
        self.assertEqual(first.status_code, 200)

        second = self._reset(token, 'AnotherPass2!')
        self.assertEqual(second.status_code, 400)

        # The password from the first (successful) reset is still the one in
        # effect - the rejected replay must not have touched it.
        self.user.refresh_from_db()
        self.assertTrue(verify_password('BrandNewPass1!', self.user.password_hash))

    def test_expired_token_is_rejected_and_password_is_unchanged(self):
        token = self._request_token()
        PasswordResetToken.objects.filter(user=self.user).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        response = self._reset(token, 'BrandNewPass1!')
        self.assertEqual(response.status_code, 400)

        self.user.refresh_from_db()
        self.assertTrue(verify_password('OldPass123!', self.user.password_hash))

    def test_already_used_token_is_rejected(self):
        token = self._request_token()
        PasswordResetToken.objects.filter(user=self.user).update(used=True)

        response = self._reset(token, 'BrandNewPass1!')
        self.assertEqual(response.status_code, 400)

        self.user.refresh_from_db()
        self.assertTrue(verify_password('OldPass123!', self.user.password_hash))

    def test_unknown_token_is_rejected(self):
        response = self._reset('not-a-real-token', 'BrandNewPass1!')
        self.assertEqual(response.status_code, 400)

    def test_missing_fields_are_rejected(self):
        token = self._request_token()
        self.assertEqual(self._reset(token, '').status_code, 400)
        self.assertEqual(self.client.post(
            '/api/reset-password/',
            data=json.dumps({'new_password': 'BrandNewPass1!'}),
            content_type='application/json',
        ).status_code, 400)

    def test_password_shorter_than_minimum_is_rejected(self):
        token = self._request_token()
        response = self._reset(token, 'short1')
        self.assertEqual(response.status_code, 400)

        self.user.refresh_from_db()
        self.assertTrue(verify_password('OldPass123!', self.user.password_hash))
