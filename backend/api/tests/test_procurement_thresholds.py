"""Mode-of-procurement ceiling and contract-splitting checks at RFQ issue.

* Small Value Procurement cannot be issued for a PR whose ABC (the whole
  PR's grand total) is above P2M (Sec. 39).
* An SVP RFQ is flagged as possible splitting when other SVP-issued PRs from
  the same office, for the same category, this year bring the combined
  amount over P2M. It may be issued only with a justification of at least
  20 characters, which is recorded with who gave it, when, and the related
  PRs and total at that moment, and shown on the RFQ to the BAC (not the
  supplier). Far above the ceiling, the warning advises Competitive Bidding.
* None of this applies to drafts or previews.
"""

import json
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from api.models import RFQ, Category, PurchaseRequest, PurchaseRequestItem, Role, Supplier, SupplierCategory, User
from api.tests.test_authorization import _login_as

SVP = 'Small Value Procurement'
JUSTIFICATION = 'Separate request: the second laboratory was approved mid-year.'


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ProcurementThresholdTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Office Supplies')
        self.supplier = Supplier.objects.create(
            company_name='Acme Supplies', contact_person='Rep', email='acme@example.com', status='Approved',
        )
        SupplierCategory.objects.create(supplier=self.supplier, category=self.category)
        role = Role.objects.get_or_create(name='admin')[0]
        self.admin = User.objects.create(username='bac', password_hash='x', role=role)
        _login_as(self.client, 'admin', user=self.admin)
        self.pr = self._pr('2026-11-100', 900_000)

    def _pr(self, pr_no, amount, office='ICT Office'):
        pr = PurchaseRequest.objects.create(
            entity_name='CTU', pr_no=pr_no, office_section=office, status=PurchaseRequest.STATUS_MATCHED,
            grand_total=Decimal(amount),
        )
        PurchaseRequestItem.objects.create(
            purchase_request=pr, item_description='Bond paper', category=self.category.name,
            quantity=1, unit='lot', unit_cost=Decimal(amount), total_cost=Decimal(amount),
        )
        return pr

    def _issued_svp(self, pr, sent_at=None, mode=SVP, category=None):
        """An earlier SVP RFQ already issued for ``pr``."""
        return RFQ.objects.create(
            purchase_request=pr, supplier=self.supplier, category=category or self.category,
            rfq_no=f'RFQ-{pr.pr_no}:01', subject='RFQ', message='m', status=RFQ.STATUS_SENT,
            mode_of_procurement=mode, sent_at=sent_at or timezone.now(),
        )

    def _send(self, pr=None, mode=SVP, **extra):
        payload = {'supplier_id': self.supplier.id, 'mode_of_procurement': mode, 'send': True}
        payload.update(extra)
        return self.client.post(
            f'/api/pr/{(pr or self.pr).id}/rfq/', data=json.dumps(payload), content_type='application/json',
        )

    def _manual(self, pr=None, mode=SVP, **extra):
        payload = {'manual_supplier_name': 'Walk-in Trading', 'mode_of_procurement': mode}
        payload.update(extra)
        return self.client.post(
            f'/api/pr/{(pr or self.pr).id}/manual-rfq/', data=json.dumps(payload), content_type='application/json',
        )

    # ── ABC ceiling ──────────────────────────────────────────────────────
    def test_svp_above_two_million_cannot_be_issued(self):
        pr = self._pr('2026-11-200', 2_000_000.01)
        response = self._send(pr)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'abc_exceeds_mode_ceiling')
        self.assertIn('₱2,000,000.00', response.json()['message'])
        self.assertIn('Sec. 39', response.json()['message'])
        self.assertFalse(RFQ.objects.filter(purchase_request=pr).exclude(status=RFQ.STATUS_DRAFT).exists())

    def test_svp_at_exactly_two_million_is_allowed(self):
        response = self._send(self._pr('2026-11-201', 2_000_000))
        self.assertEqual(response.status_code, 201, response.content)

    def test_ceiling_matches_a_typed_svp_variant_and_manual_rfqs(self):
        pr = self._pr('2026-11-202', 3_000_000)
        self.assertEqual(self._send(pr, mode='Negotiated Procurement - small value procurement').status_code, 400)
        self.assertEqual(self._manual(pr).status_code, 400)
        self.assertFalse(RFQ.objects.filter(purchase_request=pr, delivery_method=RFQ.DELIVERY_MANUAL).exists())

    def test_other_modes_have_no_ceiling(self):
        response = self._send(self._pr('2026-11-203', 5_000_000), mode='Competitive Bidding')
        self.assertEqual(response.status_code, 201, response.content)

    def test_drafts_are_not_checked(self):
        pr = self._pr('2026-11-204', 3_000_000)
        response = self._send(pr, send=False, generate_pdf=True, preview=True)
        self.assertEqual(response.status_code, 201, response.content)

    # ── Splitting ────────────────────────────────────────────────────────
    def test_combined_same_office_category_year_over_ceiling_needs_justification(self):
        self._issued_svp(self._pr('2026-11-001', 700_000))
        self._issued_svp(self._pr('2026-11-002', 600_000))

        response = self._send()  # 900k + 700k + 600k = 2.2M

        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body['code'], 'possible_contract_splitting')
        self.assertEqual(body['min_justification_length'], 20)
        self.assertEqual(body['splitting']['combined_total'], 2_200_000.0)
        self.assertEqual({row['pr_no'] for row in body['splitting']['related']}, {'2026-11-001', '2026-11-002'})
        self.assertFalse(body['splitting']['advise_competitive_bidding'])
        self.assertNotIn('Competitive Bidding', body['message'])
        self.assertFalse(RFQ.objects.filter(purchase_request=self.pr, status=RFQ.STATUS_SENT).exists())

    def test_justification_must_be_long_enough(self):
        self._issued_svp(self._pr('2026-11-001', 1_500_000))
        for text in ('x', '   ', 'too           short'):
            with self.subTest(text=text):
                response = self._send(splitting_justification=text)
                self.assertEqual(response.status_code, 409)
        self.assertIn('at least 20 characters', self._send(splitting_justification='too short').json()['message'])

    def test_justified_rfq_is_issued_and_records_who_when_and_the_check(self):
        self._issued_svp(self._pr('2026-11-001', 1_500_000))

        response = self._send(splitting_justification=f'  {JUSTIFICATION}  ')

        self.assertEqual(response.status_code, 201, response.content)
        rfq = RFQ.objects.get(purchase_request=self.pr)
        self.assertEqual(rfq.status, RFQ.STATUS_SENT)
        self.assertEqual(rfq.splitting_justification, JUSTIFICATION)
        self.assertEqual(rfq.splitting_justified_by, self.admin)
        self.assertEqual(rfq.splitting_justified_by_username, 'bac')
        self.assertIsNotNone(rfq.splitting_justified_at)
        self.assertEqual(rfq.splitting_check['combined_total'], 2_400_000.0)
        self.assertEqual(rfq.splitting_check['related'][0]['pr_no'], '2026-11-001')
        self.assertEqual(rfq.splitting_check['this_pr']['amount'], 900_000.0)

        review = response.json()['splitting_review']
        self.assertEqual(review['justification'], JUSTIFICATION)
        self.assertEqual(review['justified_by'], 'bac')
        self.assertEqual(review['check']['combined_total'], 2_400_000.0)

    def test_justification_is_not_shown_to_the_supplier(self):
        self._issued_svp(self._pr('2026-11-001', 1_500_000))
        self._send(splitting_justification=JUSTIFICATION)
        _login_as(self.client, 'supplier', supplier=self.supplier)

        rfqs = self.client.get(f'/api/suppliers/{self.supplier.id}/rfqs/').json()['rfqs']
        self.assertTrue(rfqs)
        for rfq in rfqs:
            self.assertNotIn('splitting_review', rfq)

    def test_manual_rfq_is_checked_and_records_the_justification(self):
        self._issued_svp(self._pr('2026-11-001', 1_500_000))
        self.assertEqual(self._manual().status_code, 409)

        response = self._manual(splitting_justification=JUSTIFICATION)
        self.assertEqual(response.status_code, 201, response.content)
        rfq = RFQ.objects.get(purchase_request=self.pr, delivery_method=RFQ.DELIVERY_MANUAL)
        self.assertEqual(rfq.splitting_justified_by_username, 'bac')
        self.assertEqual(rfq.splitting_check['combined_total'], 2_400_000.0)

    def test_far_above_the_ceiling_advises_competitive_bidding(self):
        self._issued_svp(self._pr('2026-11-001', 1_900_000))
        self._issued_svp(self._pr('2026-11-002', 1_900_000))  # + 900k = 4.7M

        body = self._send().json()
        self.assertTrue(body['splitting']['advise_competitive_bidding'])
        self.assertIn('should consider Competitive Bidding', body['message'])
        # Advice only: a justification still lets it be issued. (200: the
        # refused attempt above left a draft, which this send reuses.)
        response = self._send(splitting_justification=JUSTIFICATION)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], RFQ.STATUS_SENT)

    def test_not_flagged_when_under_the_ceiling_combined(self):
        self._issued_svp(self._pr('2026-11-001', 1_000_000))  # 1.9M combined
        self.assertEqual(self._send().status_code, 201)

    def test_only_same_office_category_year_svp_and_issued_prs_count(self):
        other_category = Category.objects.get_or_create(name='Janitorial Supplies')[0]
        last_year = datetime(timezone.now().year - 1, 6, 1, tzinfo=dt_timezone.utc)
        self._issued_svp(self._pr('2026-11-001', 1_500_000, office='Library'))          # other office
        self._issued_svp(self._pr('2026-11-002', 1_500_000), sent_at=last_year)         # last year
        self._issued_svp(self._pr('2026-11-003', 1_500_000), mode='Shopping')           # other mode
        self._issued_svp(self._pr('2026-11-004', 1_500_000), category=other_category)   # other category
        draft = self._issued_svp(self._pr('2026-11-005', 1_500_000))
        RFQ.objects.filter(id=draft.id).update(status=RFQ.STATUS_DRAFT)                   # never issued

        self.assertEqual(self._send().status_code, 201)

    def test_office_match_ignores_case_and_spacing(self):
        self._issued_svp(self._pr('2026-11-001', 1_500_000, office='  ict office '))
        self.assertEqual(self._send().status_code, 409)
