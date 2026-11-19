"""What a supplier sees of procurement opportunities.

* The list is newest posting first: the supplier dashboard previews only the
  first few, so the oldest PRs must not crowd out new ones. Only PRs the BAC
  has posted are listed.
* A supplier sees only the ABC, never the per-item estimated costs.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from api.models import RFQ, Category, PurchaseRequest, PurchaseRequestItem, Role
from api.tests.test_authorization import _login_as
from api.tests.test_category_grouped_matching import make_eligible_supplier


class SupplierOpportunityOrderTests(TestCase):
    def setUp(self):
        self.category = Category.objects.get_or_create(name='Office Supplies')[0]
        self.supplier = make_eligible_supplier('Acme Supplies', self.category)
        Role.objects.get_or_create(name='supplier')
        _login_as(self.client, 'supplier', supplier=self.supplier)

    def _pr(self, pr_no, posted_at):
        # posted_at=None: matched but never posted by the BAC.
        pr = PurchaseRequest.objects.create(
            entity_name='CTU', pr_no=pr_no, status=PurchaseRequest.STATUS_MATCHED,
            grand_total=100, posted_at=posted_at, is_posted=posted_at is not None,
        )
        PurchaseRequestItem.objects.create(
            purchase_request=pr, item_description='Bond paper', category=self.category.name,
            quantity=1, unit_cost=100, total_cost=100, unit='ream',
        )
        return pr

    def test_newest_posting_first_and_unposted_left_out(self):
        now = timezone.now()
        self._pr('2026-11-001', now - timedelta(days=10))
        self._pr('2026-11-002', None)
        self._pr('2026-11-003', now - timedelta(days=1))
        self._pr('2026-11-004', now - timedelta(days=5))

        response = self.client.get(f'/api/suppliers/{self.supplier.id}/opportunities/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [opp['pr_no'] for opp in response.json()['opportunities']],
            ['2026-11-003', '2026-11-004', '2026-11-001'],
        )


class SupplierSeesOnlyTheAbcTests(TestCase):
    def setUp(self):
        self.category = Category.objects.get_or_create(name='Office Supplies')[0]
        self.supplier = make_eligible_supplier('Acme Supplies', self.category)
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU', pr_no='2026-11-010', status=PurchaseRequest.STATUS_MATCHED,
            grand_total=2500,
        )
        PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description='Bond paper', category=self.category.name,
            quantity=10, unit_cost=250, total_cost=2500, unit='ream',
        )
        RFQ.objects.create(
            rfq_no='RFQ-2026-11-010:01', purchase_request=self.pr, supplier=self.supplier,
            subject='RFQ', message='Please quote', status=RFQ.STATUS_SENT,
        )

    def test_pr_details_hide_item_costs_from_a_supplier_but_keep_the_abc(self):
        _login_as(self.client, 'supplier', supplier=self.supplier)
        body = self.client.get(f'/api/pr/{self.pr.id}/details/').json()

        self.assertEqual(body['grand_total'], 2500.0)
        self.assertEqual(body['items'][0]['item_description'], 'Bond paper')
        self.assertNotIn('unit_cost', body['items'][0])
        self.assertNotIn('total_cost', body['items'][0])

    def test_pr_details_still_show_item_costs_to_the_bac(self):
        _login_as(self.client, 'admin')
        item = self.client.get(f'/api/pr/{self.pr.id}/details/').json()['items'][0]

        self.assertEqual(item['unit_cost'], 250.0)
        self.assertEqual(item['total_cost'], 2500.0)

    def test_supplier_rfqs_hide_item_costs(self):
        _login_as(self.client, 'supplier', supplier=self.supplier)
        rfq = self.client.get(f'/api/suppliers/{self.supplier.id}/rfqs/').json()['rfqs'][0]

        self.assertTrue(rfq['abc'])
        item = rfq['purchase_request']['items'][0]
        self.assertEqual(item['item_description'], 'Bond paper')
        self.assertNotIn('unit_cost', item)
        self.assertNotIn('total_cost', item)
