"""Coverage for the PR posting record (``posted_at`` / ``posted_by``).

A PR is posted when it first reaches a supplier-visible status (Matched or
Approved) with at least one categorized line item, which is when it enters
the matching suppliers' Opportunities feed. The record is set once, by the
BAC user whose action posted it, and is never overwritten or cleared.
"""
import csv
import io
import json

from django.test import TestCase

from api.models import PurchaseRequest, PurchaseRequestItem, Role, User


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

    def test_new_pr_is_not_posted(self):
        self.assertIsNone(self.pr.posted_at)
        self.assertEqual(self.pr.posted_by, '')

    def test_categorizing_every_item_posts_the_pr_and_records_who(self):
        response = self._assign('Office Supplies')

        self.assertEqual(response.status_code, 200)
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.status, PurchaseRequest.STATUS_MATCHED)
        self.assertIsNotNone(self.pr.posted_at)
        self.assertEqual(self.pr.posted_by, 'bac-secretariat')
        self.assertEqual(response.json()['posted_by'], 'bac-secretariat')

    def test_manual_status_change_to_matched_posts_a_categorized_pr(self):
        self.item.category = 'Office Supplies'
        self.item.save(update_fields=['category'])

        self._patch_status('matched')

        self.pr.refresh_from_db()
        self.assertIsNotNone(self.pr.posted_at)
        self.assertEqual(self.pr.posted_by, 'bac-secretariat')

    def test_supplier_visible_status_without_categories_is_not_a_posting(self):
        self._patch_status('matched')

        self.pr.refresh_from_db()
        self.assertIsNone(self.pr.posted_at)
        self.assertEqual(self.pr.posted_by, '')

    def test_non_visible_status_is_not_a_posting(self):
        self.item.category = 'Office Supplies'
        self.item.save(update_fields=['category'])

        self._patch_status('rejected')

        self.pr.refresh_from_db()
        self.assertIsNone(self.pr.posted_at)

    def test_first_posting_is_kept_through_later_status_changes(self):
        self._assign('Office Supplies')
        self.pr.refresh_from_db()
        first_posted_at = self.pr.posted_at

        other = _login_as_admin(self.client, username='second-admin')
        self._patch_status('in_review')
        self._patch_status('approved')

        self.pr.refresh_from_db()
        self.assertEqual(self.pr.posted_at, first_posted_at)
        self.assertEqual(self.pr.posted_by, 'bac-secretariat')
        self.assertNotEqual(self.pr.posted_by, other.username)

    def test_pr_list_returns_the_posting_record_and_matching_timestamp(self):
        self._assign('Office Supplies')

        records = self.client.get('/api/pr/list/').json()
        record = next(r for r in records if r['id'] == self.pr.id)

        self.assertEqual(record['posted_by'], 'bac-secretariat')
        self.assertIsNotNone(record['posted_at'])
        self.assertEqual(record['stage_timestamps']['supplier_matching'], record['posted_at'])

    def test_csv_export_includes_the_posting_record(self):
        self._assign('Office Supplies')

        response = self.client.get('/api/admin/export/purchase-requests/')
        content = b''.join(response.streaming_content).decode('utf-8-sig')
        rows = list(csv.reader(io.StringIO(content)))

        self.assertEqual(rows[0][-2:], ['Posted At', 'Posted By'])
        row = next(r for r in rows[1:] if r[1] == '2026-11-010')
        self.assertTrue(row[-2])
        self.assertEqual(row[-1], 'bac-secretariat')
