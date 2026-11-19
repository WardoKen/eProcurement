"""Coverage for explicit PR posting (``is_posted``, ``posted_at`` / ``posted_by``,
``PRPostingLog``).

A PR becomes a procurement opportunity only when the BAC posts it - reaching
Matched or Approved no longer posts it automatically. Posting needs a
postable status and a categorized item; unposting needs a reason; a posted
PR whose status leaves the postable statuses is taken down automatically.
Every post and unpost is logged with who, when and why.
"""
import csv
import io
import json

from django.test import TestCase

from api.models import PRPostingLog, PurchaseRequest, PurchaseRequestItem, Role, User


def _login_as_admin(client, username='bac-secretariat'):
    role = Role.objects.get_or_create(name='admin')[0]
    user = User.objects.create(username=username, password_hash='x', role=role, is_active=True)
    session = client.session
    session['user_id'] = user.id
    session['role'] = 'admin'
    session['username'] = user.username
    session.save()
    return user


class PrPostingRecordTests(TestCase):
    def setUp(self):
        self.admin = _login_as_admin(self.client)
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU-Tuburan Campus', pr_no='2026-11-010',
            status=PurchaseRequest.STATUS_IN_REVIEW,
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

    def _patch_status(self, status):
        return self.client.patch(
            f'/api/pr/{self.pr.id}/status/',
            data=json.dumps({'status': status}),
            content_type='application/json',
        )

    def _posting(self, action, reason=''):
        return self.client.post(
            f'/api/pr/{self.pr.id}/posting/',
            data=json.dumps({'action': action, 'reason': reason}),
            content_type='application/json',
        )

    def _matched_and_categorized(self):
        self._assign('Office Supplies')
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.status, PurchaseRequest.STATUS_MATCHED)

    def test_new_pr_is_not_posted(self):
        self.assertFalse(self.pr.is_posted)
        self.assertIsNone(self.pr.posted_at)
        self.assertEqual(self.pr.posted_by, '')

    def test_reaching_matched_no_longer_posts_automatically(self):
        self._matched_and_categorized()
        self.assertFalse(self.pr.is_posted)
        self.assertIsNone(self.pr.posted_at)
        self.assertFalse(PRPostingLog.objects.exists())

    def test_post_records_who_and_when(self):
        self._matched_and_categorized()

        response = self._posting('post')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['is_posted'])
        self.pr.refresh_from_db()
        self.assertTrue(self.pr.is_posted)
        self.assertIsNotNone(self.pr.posted_at)
        self.assertEqual(self.pr.posted_by, 'bac-secretariat')
        [row] = response.json()['history']
        self.assertEqual((row['action'], row['changed_by'], row['automatic']), ('posted', 'bac-secretariat', False))

    def test_cannot_post_before_matched_or_without_categories(self):
        response = self._posting('post')  # in review, uncategorized
        self.assertEqual(response.status_code, 400)
        self.assertIn('Only a Matched or Completed', response.json()['message'])

        self._patch_status('matched')  # matched, but no categorized item
        response = self._posting('post')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Assign a category', response.json()['message'])
        self.pr.refresh_from_db()
        self.assertFalse(self.pr.is_posted)

    def test_cannot_post_twice(self):
        self._matched_and_categorized()
        self._posting('post')
        self.assertEqual(self._posting('post').status_code, 400)
        self.assertEqual(PRPostingLog.objects.count(), 1)

    def test_unpost_requires_a_reason_and_records_it(self):
        self._matched_and_categorized()
        self._posting('post')

        for reason in ('', 'short', '   too    short '):
            with self.subTest(reason=reason):
                self.assertEqual(self._posting('unpost', reason).status_code, 400)
        self.pr.refresh_from_db()
        self.assertTrue(self.pr.is_posted)

        response = self._posting('unpost', 'End user withdrew the request.')
        self.assertEqual(response.status_code, 200)
        self.pr.refresh_from_db()
        self.assertFalse(self.pr.is_posted)
        self.assertIsNone(self.pr.posted_at)
        latest = response.json()['history'][0]
        self.assertEqual((latest['action'], latest['reason'], latest['changed_by']),
                         ('unposted', 'End user withdrew the request.', 'bac-secretariat'))

    def test_status_leaving_postable_statuses_takes_the_posting_down(self):
        self._matched_and_categorized()
        self._posting('post')

        self._patch_status('rejected')

        self.pr.refresh_from_db()
        self.assertFalse(self.pr.is_posted)
        latest = PRPostingLog.objects.order_by('-changed_at', '-id').first()
        self.assertEqual(latest.action, 'unposted')
        self.assertTrue(latest.automatic)
        self.assertEqual(latest.reason, 'Taken down automatically: status changed to Rejected.')

    def test_moving_between_postable_statuses_keeps_the_posting(self):
        self._matched_and_categorized()
        self._posting('post')
        self._patch_status('approved')
        self.pr.refresh_from_db()
        self.assertTrue(self.pr.is_posted)

    def test_only_the_bac_can_post(self):
        self._matched_and_categorized()
        self.client.logout()
        self.assertEqual(self._posting('post').status_code, 401)

    def test_pr_list_returns_posting_and_first_posting_as_matching_timestamp(self):
        self._matched_and_categorized()
        self._posting('post')

        records = self.client.get('/api/pr/list/').json()
        record = next(r for r in records if r['id'] == self.pr.id)

        self.assertTrue(record['is_posted'])
        self.assertEqual(record['posted_by'], 'bac-secretariat')
        self.assertIsNotNone(record['posted_at'])
        self.assertIsNotNone(record['stage_timestamps']['supplier_matching'])

        # Taken down: no current posting, but the matching stage keeps its date.
        self._posting('unpost', 'End user withdrew the request.')
        record = next(r for r in self.client.get('/api/pr/list/').json() if r['id'] == self.pr.id)
        self.assertFalse(record['is_posted'])
        self.assertIsNone(record['posted_at'])
        self.assertIsNotNone(record['stage_timestamps']['supplier_matching'])

    def test_csv_export_includes_the_posting_record(self):
        self._matched_and_categorized()
        self._posting('post')

        response = self.client.get('/api/admin/export/purchase-requests/')
        content = b''.join(response.streaming_content).decode('utf-8-sig')
        rows = list(csv.reader(io.StringIO(content)))

        posted_at_col = rows[0].index('Posted At')
        self.assertEqual(rows[0][posted_at_col:posted_at_col + 2], ['Posted At', 'Posted By'])
        row = next(r for r in rows[1:] if r[1] == '2026-11-010')
        self.assertTrue(row[posted_at_col])
        self.assertEqual(row[posted_at_col + 1], 'bac-secretariat')
