"""Coverage for the PR status-change email notification to the submitting
End User (buyer), added as a side effect of pr_update_status and
pr_items_assign_categories - the proposal's "PR status notification system
supporting email for end users" commitment.

There is no FK from PurchaseRequest to User: the submitter is recorded as a
username string (``submitted_by``), resolved to an active User at send time.
Sending is best-effort - a missing/inactive user, a blank email, or an SMTP
failure must never block the status update itself.
"""
import json

from django.core import mail
from django.test import TestCase

from api.models import PRNotificationSettings, PurchaseRequest, PurchaseRequestItem, Role, User


def _login_as(client, role_name, *, user=None):
    if user is None:
        role = Role.objects.get_or_create(name=role_name)[0]
        user = User.objects.create(
            username=f'test-{role_name}-{User.objects.count()}',
            password_hash='x',
            role=role,
            is_active=True,
        )
    session = client.session
    session['user_id'] = user.id
    session['role'] = role_name
    session['username'] = user.username
    session.save()
    return user


class PrUpdateStatusNotificationTests(TestCase):
    def setUp(self):
        _login_as(self.client, 'admin')
        role = Role.objects.get_or_create(name='buyer')[0]
        self.buyer = User.objects.create(
            username='requestor1', password_hash='x', role=role, is_active=True,
            email='requestor1@ctu.edu.ph',
        )
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU-Tuburan Campus', pr_no='2026-09-001',
            submitted_by='requestor1', status=PurchaseRequest.STATUS_UPLOADED,
        )

    def _patch_status(self, status):
        return self.client.patch(
            f'/api/pr/{self.pr.id}/status/',
            data=json.dumps({'status': status}),
            content_type='application/json',
        )

    def test_status_change_sends_email_to_the_submitter(self):
        response = self._patch_status('in_review')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['requestor1@ctu.edu.ph'])
        self.assertIn('2026-09-001', email.subject)
        self.assertIn('Uploaded', email.body)
        self.assertIn('In Review', email.body)

    def test_rejected_status_mentions_contacting_bac(self):
        self._patch_status('rejected')

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Rejected', mail.outbox[0].body)
        self.assertIn('BAC Secretariat', mail.outbox[0].body)

    def test_setting_the_same_status_sends_no_email(self):
        response = self._patch_status('uploaded')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_unresolvable_submitter_sends_no_email_but_status_still_updates(self):
        self.pr.submitted_by = 'someone-who-does-not-exist'
        self.pr.save(update_fields=['submitted_by'])

        response = self._patch_status('in_review')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.status, 'in_review')

    def test_submitter_with_no_email_on_file_sends_no_email_but_status_still_updates(self):
        self.buyer.email = ''
        self.buyer.save(update_fields=['email'])

        response = self._patch_status('in_review')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.status, 'in_review')

    def test_inactive_submitter_account_sends_no_email_but_status_still_updates(self):
        self.buyer.is_active = False
        self.buyer.save(update_fields=['is_active'])

        response = self._patch_status('in_review')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.status, 'in_review')


class PrItemsAssignCategoriesNotificationTests(TestCase):
    """The automatic uploaded/in_review -> matched (or back to in_review)
    transition in pr_items_assign_categories must trigger the same email."""

    def setUp(self):
        _login_as(self.client, 'admin')
        role = Role.objects.get_or_create(name='buyer')[0]
        self.buyer = User.objects.create(
            username='requestor2', password_hash='x', role=role, is_active=True,
            email='requestor2@ctu.edu.ph',
        )
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU-Tuburan Campus', pr_no='2026-09-002',
            submitted_by='requestor2', status=PurchaseRequest.STATUS_UPLOADED,
        )
        self.item = PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description='Bond paper', quantity=10, unit_cost=250,
        )

    def _assign(self, category):
        return self.client.post(
            f'/api/pr/{self.pr.id}/items/categories/',
            data=json.dumps({'assignments': [{'item_id': self.item.id, 'category': category}]}),
            content_type='application/json',
        )

    def test_assigning_the_last_category_flips_to_matched_and_emails(self):
        response = self._assign('Office Supplies')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'matched')
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['requestor2@ctu.edu.ph'])
        self.assertIn('Matched', email.body)
        self.assertIn('Uploaded', email.body)

    def test_moving_from_matched_back_to_in_review_emails_again(self):
        self._assign('Office Supplies')
        mail.outbox.clear()

        second_item = PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description='Extra item', quantity=1, unit_cost=1,
        )
        response = self.client.post(
            f'/api/pr/{self.pr.id}/items/categories/',
            data=json.dumps({'assignments': [{'item_id': second_item.id, 'category': None}]}),
            content_type='application/json',
        )

        self.assertEqual(response.json()['status'], 'in_review')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('In Review', mail.outbox[0].body)
        self.assertIn('Matched', mail.outbox[0].body)

    def test_no_status_change_sends_no_email(self):
        # Uncategorized -> still uncategorized: status stays 'in_review' either
        # way, so this must not email.
        PurchaseRequestItem.objects.create(purchase_request=self.pr, item_description='Second item')
        self.pr.status = PurchaseRequest.STATUS_IN_REVIEW
        self.pr.save(update_fields=['status'])

        response = self._assign('Office Supplies')

        self.assertEqual(response.json()['status'], 'in_review')
        self.assertEqual(len(mail.outbox), 0)

    def test_unresolvable_submitter_sends_no_email_but_status_still_updates(self):
        self.pr.submitted_by = 'ghost-requestor'
        self.pr.save(update_fields=['submitted_by'])

        response = self._assign('Office Supplies')

        self.assertEqual(response.json()['status'], 'matched')
        self.assertEqual(len(mail.outbox), 0)


class PrNotificationSettingsGatingTests(TestCase):
    """PRNotificationSettings (enabled / per-status toggles /
    mute_automatic_transitions) gates _notify_pr_status_change on top of its
    existing no-op conditions (same-status, unresolvable buyer, blank email),
    which are covered above and must remain unaffected by this gating."""

    def setUp(self):
        _login_as(self.client, 'admin')
        role = Role.objects.get_or_create(name='buyer')[0]
        self.buyer = User.objects.create(
            username='requestor3', password_hash='x', role=role, is_active=True,
            email='requestor3@ctu.edu.ph',
        )
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU-Tuburan Campus', pr_no='2026-09-003',
            submitted_by='requestor3', status=PurchaseRequest.STATUS_UPLOADED,
        )
        self.item = PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description='Bond paper', quantity=10, unit_cost=250,
        )

    def _patch_status(self, status):
        return self.client.patch(
            f'/api/pr/{self.pr.id}/status/',
            data=json.dumps({'status': status}),
            content_type='application/json',
        )

    def _assign(self, category):
        return self.client.post(
            f'/api/pr/{self.pr.id}/items/categories/',
            data=json.dumps({'assignments': [{'item_id': self.item.id, 'category': category}]}),
            content_type='application/json',
        )

    def test_default_seeded_settings_reproduce_todays_unconditional_notify_behavior(self):
        settings_row = PRNotificationSettings.objects.get(key='global')
        self.assertTrue(settings_row.enabled)
        self.assertTrue(settings_row.notify_in_review)
        self.assertTrue(settings_row.notify_matched)
        self.assertTrue(settings_row.notify_approved)
        self.assertTrue(settings_row.notify_rejected)
        self.assertFalse(settings_row.mute_automatic_transitions)

        self._patch_status('in_review')
        self._patch_status('approved')
        response = self._assign('Office Supplies')

        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(response.json()['status'], 'matched')

    def test_master_switch_off_suppresses_every_pr_status_email(self):
        settings_row = PRNotificationSettings.objects.get(key='global')
        settings_row.enabled = False
        settings_row.save()

        self._patch_status('in_review')
        self._patch_status('rejected')
        response = self._assign('Office Supplies')

        self.assertEqual(len(mail.outbox), 0)
        # The status updates themselves must be unaffected by the mute.
        self.assertEqual(response.json()['status'], 'matched')

    def test_disabling_one_status_toggle_suppresses_only_that_transition(self):
        settings_row = PRNotificationSettings.objects.get(key='global')
        settings_row.notify_matched = False
        settings_row.save()

        self._patch_status('in_review')  # notify_in_review still True -> emails
        mail.outbox.clear()

        response = self._assign('Office Supplies')  # -> matched, muted

        self.assertEqual(response.json()['status'], 'matched')
        self.assertEqual(len(mail.outbox), 0)

        self._patch_status('rejected')  # a different status, still enabled -> emails
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Rejected', mail.outbox[0].body)

    def test_disabling_in_review_toggle_does_not_affect_matched(self):
        settings_row = PRNotificationSettings.objects.get(key='global')
        settings_row.notify_in_review = False
        settings_row.save()

        self._patch_status('in_review')
        self.assertEqual(len(mail.outbox), 0)

        response = self._assign('Office Supplies')
        self.assertEqual(response.json()['status'], 'matched')
        self.assertEqual(len(mail.outbox), 1)

    def test_mute_automatic_transitions_only_affects_the_automatic_path(self):
        settings_row = PRNotificationSettings.objects.get(key='global')
        settings_row.mute_automatic_transitions = True
        settings_row.save()

        # Automatic transition (pr_items_assign_categories): muted.
        response = self._assign('Office Supplies')
        self.assertEqual(response.json()['status'], 'matched')
        self.assertEqual(len(mail.outbox), 0)

        # Explicit admin decision (pr_update_status) to a *different* status:
        # unaffected by the mute, still follows the per-status toggles.
        self._patch_status('approved')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Approved', mail.outbox[0].body)

    def test_mute_automatic_transitions_does_not_mute_an_explicit_change_to_the_same_status(self):
        settings_row = PRNotificationSettings.objects.get(key='global')
        settings_row.mute_automatic_transitions = True
        settings_row.save()

        # Explicit admin call reaching 'matched' - not the automatic path,
        # so the mute must not apply even though the destination status is
        # the same one the automatic flip would have produced.
        response = self._patch_status('matched')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Matched', mail.outbox[0].body)
