"""What posting controls, and what the public and each role can see.

* The public Opportunities feed lists only posted PRs, with public posting
  fields only (no requester/approver names, source document or item costs).
* Category counts on the public page are posted PRs with an item in the
  category.
* The supplier portal's opportunities and dashboard count only posted PRs,
  and a supplier cannot open an unposted PR they have no RFQ for.
* The full PR list needs a sign-in; an End User only ever gets their own PRs.
* The migration keeps old automatic posting stamps as history and leaves
  every PR unposted.
"""
import importlib
import json
from datetime import timedelta

from django.apps import apps as django_apps
from django.test import TestCase
from django.utils import timezone

from api.models import RFQ, Category, PRPostingLog, PurchaseRequest, PurchaseRequestItem, Role, User
from api.tests.test_authorization import _login_as
from api.tests.test_category_grouped_matching import make_eligible_supplier


class PublicPostingTests(TestCase):
    def setUp(self):
        self.category = Category.objects.get_or_create(name='Office Supplies')[0]
        self.posted = self._pr('2026-11-001', posted=True)
        self.unposted = self._pr('2026-11-002', posted=False)

    def _pr(self, pr_no, posted, category='Office Supplies', status=PurchaseRequest.STATUS_MATCHED):
        pr = PurchaseRequest.objects.create(
            entity_name='CTU', pr_no=pr_no, office_section='ICT Office', purpose='Bond paper for exams',
            status=status, grand_total=2500, requested_by='Ana Cruz', approved_by='Carla Esposo',
            source_filename='signed-pr.pdf', submitted_by='enduser1',
            is_posted=posted, posted_at=timezone.now() if posted else None, posted_by='bac' if posted else '',
        )
        PurchaseRequestItem.objects.create(
            purchase_request=pr, item_description='Bond paper', category=category,
            quantity=10, unit='ream', unit_cost=137.25, total_cost=1372.50,
        )
        return pr

    def _public(self, query=''):
        response = self.client.get(f'/api/public/opportunities/{query}')
        self.assertEqual(response.status_code, 200)  # no sign-in needed
        return response.json()['opportunities']

    def test_public_feed_lists_only_posted_prs(self):
        self.assertEqual([opp['pr_no'] for opp in self._public()], ['2026-11-001'])

    def test_public_feed_shows_only_public_posting_fields(self):
        [opp] = self._public()
        self.assertEqual(opp['abc'], 2500.0)
        self.assertEqual(opp['categories'], ['Office Supplies'])
        self.assertEqual(opp['items'], [{'description': 'Bond paper', 'quantity': 10.0, 'unit': 'ream'}])
        text = json.dumps(opp)
        for private in ('Ana Cruz', 'Carla Esposo', 'signed-pr.pdf', 'enduser1', 'unit_cost', '137.25', '1372.5'):
            self.assertNotIn(private, text)

    def test_public_feed_filters_by_item_category_ignoring_case(self):
        janitorial = Category.objects.get_or_create(name='Janitorial Supplies')[0]
        self._pr('2026-11-003', posted=True, category=janitorial.name)
        self.assertEqual([o['pr_no'] for o in self._public('?category=office%20supplies')], ['2026-11-001'])
        self.assertEqual([o['pr_no'] for o in self._public('?category=Janitorial Supplies')], ['2026-11-003'])

    def test_a_posted_pr_no_longer_at_a_postable_status_is_not_listed(self):
        PurchaseRequest.objects.filter(id=self.posted.id).update(status=PurchaseRequest.STATUS_REJECTED)
        self.assertEqual(self._public(), [])

    def test_category_counts_are_posted_prs(self):
        counts = {row['name']: row['count'] for row in self.client.get('/api/categories/').json()}
        self.assertEqual(counts['Office Supplies'], 1)

    def test_pr_list_needs_a_sign_in(self):
        self.assertEqual(self.client.get('/api/pr/list/').status_code, 401)

    def test_end_user_only_gets_their_own_prs(self):
        role = Role.objects.get_or_create(name='buyer')[0]
        _login_as(self.client, 'buyer', user=User.objects.create(username='someone-else', password_hash='x', role=role))
        # Asking for another End User's PRs still returns only your own (none).
        self.assertEqual(self.client.get('/api/pr/list/?submitted_by=enduser1').json(), [])
        self.assertEqual(self.client.get('/api/pr/list/').json(), [])
        self.assertEqual(self.client.get(f'/api/pr/{self.posted.id}/details/').status_code, 404)

    def test_supplier_portal_counts_only_posted_prs(self):
        supplier = make_eligible_supplier('Acme Supplies', self.category)
        _login_as(self.client, 'supplier', supplier=supplier)

        opportunities = self.client.get(f'/api/suppliers/{supplier.id}/opportunities/').json()['opportunities']
        self.assertEqual([opp['pr_no'] for opp in opportunities], ['2026-11-001'])
        summary = self.client.get(f'/api/suppliers/{supplier.id}/dashboard/').json()
        self.assertEqual(summary['open_opportunities'], 1)

    def test_supplier_cannot_open_an_unposted_pr_without_an_rfq(self):
        supplier = make_eligible_supplier('Acme Supplies', self.category)
        _login_as(self.client, 'supplier', supplier=supplier)
        self.assertEqual(self.client.get(f'/api/pr/{self.posted.id}/details/').status_code, 200)
        self.assertEqual(self.client.get(f'/api/pr/{self.unposted.id}/details/').status_code, 404)

        # Issued an RFQ for it: the supplier may open it.
        RFQ.objects.create(
            purchase_request=self.unposted, supplier=supplier, rfq_no='RFQ-2026-11-002:01',
            subject='RFQ', message='m', status=RFQ.STATUS_SENT, sent_at=timezone.now(),
        )
        self.assertEqual(self.client.get(f'/api/pr/{self.unposted.id}/details/').status_code, 200)


class LegacyPostingMigrationTests(TestCase):
    def test_old_automatic_stamps_become_history_and_prs_start_unposted(self):
        stamped_at = timezone.now() - timedelta(days=30)
        stamped = PurchaseRequest.objects.create(
            entity_name='CTU', pr_no='2026-10-001', status=PurchaseRequest.STATUS_MATCHED,
            posted_at=stamped_at, posted_by='bac',
        )
        never = PurchaseRequest.objects.create(entity_name='CTU', pr_no='2026-10-002')

        migration = importlib.import_module('api.migrations.0038_explicit_pr_posting')
        migration.move_legacy_stamps_to_history(django_apps, None)

        stamped.refresh_from_db()
        self.assertFalse(stamped.is_posted)
        self.assertIsNone(stamped.posted_at)
        self.assertEqual(stamped.posted_by, '')
        posted_row, reset_row = PRPostingLog.objects.filter(pr=stamped).order_by('changed_at', 'id')
        self.assertEqual((posted_row.action, posted_row.changed_by_username, posted_row.automatic), ('posted', 'bac', True))
        self.assertEqual(posted_row.changed_at, stamped_at)
        self.assertEqual(reset_row.action, 'unposted')
        self.assertFalse(PRPostingLog.objects.filter(pr=never).exists())
