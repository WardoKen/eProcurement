"""Advisory ranking of category-matched suppliers (api/supplier_scoring.py).

Scoring only orders suppliers that already passed the eligibility rules in
``pr_supplier_match``; it never adds or removes anyone.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from api import supplier_scoring
from api.models import (
    Category, PurchaseRequest, PurchaseRequestItem, Quotation, RFQ, Role,
    SupplierCategory, User,
)
from api.tests.test_category_grouped_matching import _login_as, make_eligible_supplier


class SupplierScoringTests(TestCase):
    def setUp(self):
        admin_role = Role.objects.get_or_create(name='admin')[0]
        _login_as(self.client, 'admin', user=User.objects.create(username='bac', password_hash='x', role=admin_role))
        self.aircon = Category.objects.get_or_create(name='Airconditioning and Airconditioning Systems')[0]
        self.office = Category.objects.get_or_create(name='Office Supplies')[0]
        self.pr = self._pr('2026-11-001')
        PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description='Split type air conditioner', category=self.aircon.name,
            quantity=1, unit_cost=100, total_cost=100, unit='unit',
        )

    def _pr(self, number):
        return PurchaseRequest.objects.create(
            entity_name='CTU-Tuburan Campus', pr_no=number,
            status=PurchaseRequest.STATUS_MATCHED, grand_total=0,
        )

    def _rfq(self, supplier, *, responded, sent_days_ago=30, pr=None):
        pr = pr or self._pr(f'2026-10-{RFQ.objects.count() + 100:03d}')
        return RFQ.objects.create(
            purchase_request=pr, supplier=supplier, category=self.aircon,
            subject='RFQ', message='Please quote.',
            status=RFQ.STATUS_QUOTATION_RECEIVED if responded else RFQ.STATUS_SENT,
            sent_at=timezone.now() - timedelta(days=sent_days_ago),
            submitted_at=timezone.now() if responded else None,
        )

    def _suppliers(self):
        group = self.client.get(f'/api/pr/{self.pr.id}/supplier-match/').json()['groups'][0]
        return group['suppliers']

    def test_ranked_by_score_descending(self):
        responsive = make_eligible_supplier('Zenith Cooling', self.aircon)
        unresponsive = make_eligible_supplier('Alpha Aircon', self.aircon)
        for _ in range(3):
            self._rfq(responsive, responded=True)
            self._rfq(unresponsive, responded=False)

        suppliers = self._suppliers()
        self.assertEqual([s['company_name'] for s in suppliers], ['Zenith Cooling', 'Alpha Aircon'])
        self.assertGreater(suppliers[0]['match_score'], suppliers[1]['match_score'])

    def test_breakdown_shape_and_total(self):
        make_eligible_supplier('Zenith Cooling', self.aircon)
        entry = self._suppliers()[0]
        self.assertEqual(
            [f['factor'] for f in entry['score_breakdown']],
            ['RFQ responsiveness', 'Quotation history', 'Category focus', 'Item relevance'],
        )
        for factor in entry['score_breakdown']:
            self.assertEqual(set(factor), {'factor', 'points', 'max_points', 'explanation'})
            self.assertLessEqual(factor['points'], factor['max_points'])
        self.assertEqual(sum(f['max_points'] for f in entry['score_breakdown']), 100)
        self.assertAlmostEqual(entry['match_score'], sum(f['points'] for f in entry['score_breakdown']), places=1)
        # Existing fields are unchanged.
        self.assertTrue(entry['category_match'])
        self.assertEqual(entry['compliance_status'], 'Eligible')
        self.assertEqual(entry['compliance_percentage'], 100)

    def test_no_history_gets_neutral_not_zero(self):
        make_eligible_supplier('Newcomer Aircon', self.aircon)
        ignored = make_eligible_supplier('Silent Aircon', self.aircon)
        for _ in range(2):
            self._rfq(ignored, responded=False)

        by_name = {s['company_name']: s for s in self._suppliers()}
        new_resp = by_name['Newcomer Aircon']['score_breakdown'][0]
        self.assertEqual(new_resp['points'],
                         supplier_scoring.RESPONSIVENESS_WEIGHT * supplier_scoring.NEUTRAL_RESPONSIVENESS)
        self.assertGreater(new_resp['points'], 0)
        self.assertEqual(by_name['Silent Aircon']['score_breakdown'][0]['points'], 0)
        self.assertGreater(by_name['Newcomer Aircon']['match_score'], by_name['Silent Aircon']['match_score'])

    def test_recent_unanswered_rfq_is_not_penalised(self):
        supplier = make_eligible_supplier('Fresh Aircon', self.aircon)
        self._rfq(supplier, responded=False, sent_days_ago=1)
        resp = self._suppliers()[0]['score_breakdown'][0]
        self.assertEqual(resp['points'],
                         supplier_scoring.RESPONSIVENESS_WEIGHT * supplier_scoring.NEUTRAL_RESPONSIVENESS)

    def test_rfqs_on_current_pr_do_not_change_score(self):
        supplier = make_eligible_supplier('Zenith Cooling', self.aircon)
        before = self._suppliers()[0]['match_score']
        self._rfq(supplier, responded=False, pr=self.pr)
        self.assertEqual(self._suppliers()[0]['match_score'], before)

    def test_quotation_history_is_capped(self):
        supplier = make_eligible_supplier('Busy Aircon', self.aircon)
        for n in range(supplier_scoring.QUOTATION_HISTORY_CAP + 3):
            Quotation.objects.create(
                supplier=supplier, purchase_request=self._pr(f'2026-08-{n:03d}'),
                quoted_amount=100, status=Quotation.STATUS_SUBMITTED,
            )
        history = self._suppliers()[0]['score_breakdown'][1]
        self.assertEqual(history['points'], supplier_scoring.QUOTATION_HISTORY_WEIGHT)

    def test_specialist_outranks_generalist(self):
        extra = [Category.objects.get_or_create(name=f'Extra {n}')[0] for n in range(3)]
        make_eligible_supplier('Alpha General Trading', self.aircon, *extra)
        make_eligible_supplier('Zenith Cooling', self.aircon)
        self.assertEqual([s['company_name'] for s in self._suppliers()],
                         ['Zenith Cooling', 'Alpha General Trading'])

    def test_item_relevance_uses_goods_services_text(self):
        match = make_eligible_supplier('Zenith Cooling', self.aircon)
        match.goods_services = 'Air conditioners, installation and repair'
        match.save()
        make_eligible_supplier('Alpha Aircon', self.aircon)
        suppliers = self._suppliers()
        self.assertEqual(suppliers[0]['company_name'], 'Zenith Cooling')
        self.assertEqual(suppliers[0]['score_breakdown'][3]['points'], supplier_scoring.ITEM_RELEVANCE_WEIGHT)
        self.assertEqual(suppliers[1]['score_breakdown'][3]['points'], 0)

    def test_equal_scores_tiebreak_by_name(self):
        for name in ('Charlie Cooling', 'alpha Aircon', 'Bravo Air'):
            make_eligible_supplier(name, self.aircon)
        suppliers = self._suppliers()
        self.assertEqual(len({s['match_score'] for s in suppliers}), 1)
        self.assertEqual([s['company_name'] for s in suppliers], ['alpha Aircon', 'Bravo Air', 'Charlie Cooling'])

    def test_ineligible_suppliers_still_excluded(self):
        make_eligible_supplier('Eligible Aircon', self.aircon)
        # Strong history but a required document is not verified.
        unverified = make_eligible_supplier('Unverified Aircon', self.aircon)
        unverified.documents.filter(doc_type='tax_clearance').update(verification_status='Pending')
        for _ in range(3):
            self._rfq(unverified, responded=True)
        # Not approved.
        pending = make_eligible_supplier('Pending Aircon', self.aircon)
        pending.status = 'Pending Review'
        pending.save()
        # Approved and verified but registered under another category.
        make_eligible_supplier('Office Only', self.office)

        self.assertEqual([s['company_name'] for s in self._suppliers()], ['Eligible Aircon'])

    def test_low_score_never_excludes(self):
        weak = make_eligible_supplier('Weak Aircon', self.aircon, self.office,
                                      *[Category.objects.get_or_create(name=f'Extra {n}')[0] for n in range(6)])
        for _ in range(4):
            self._rfq(weak, responded=False)
        suppliers = self._suppliers()
        self.assertEqual([s['company_name'] for s in suppliers], ['Weak Aircon'])
        self.assertGreaterEqual(suppliers[0]['match_score'], 0)

    def test_context_queries_do_not_grow_with_suppliers(self):
        ids = [make_eligible_supplier(f'Supplier {n}', self.aircon).id for n in range(6)]
        with self.assertNumQueries(3):
            supplier_scoring.build_scoring_context(ids, {self.aircon.name: ['Air conditioner']})
        self.assertEqual(SupplierCategory.objects.filter(supplier_id__in=ids).count(), 6)
