"""RFQ ABC is always the originating Purchase Request's full grand total.

The category group an RFQ serves drives supplier matching / RFQItem tracking
only - it never narrows the ABC, and the printed RFQ still lists every PR item.
"""
import json
from decimal import Decimal
from pathlib import Path

from django.core import mail
from django.test import TestCase

from api.models import Category, PurchaseRequest, PurchaseRequestItem, RFQ, Role, Supplier, SupplierCategory, User
from api.tests.test_supplier_registration import _login_as

FULL_ABC = '₱53,400.00'


class RFQAbcTests(TestCase):
    def setUp(self):
        admin_role = Role.objects.get_or_create(name='admin')[0]
        self.admin = User.objects.create(username='bac-abc', password_hash='x', role=admin_role)
        _login_as(self.client, 'admin', user=self.admin)

        self.it = Category.objects.get_or_create(name='ABC Test IT Equipment')[0]
        self.elec = Category.objects.get_or_create(name='ABC Test Electrical Supplies')[0]

        # PR 2026-09-004: IT = 27,000 ; Electrical = 26,400 ; grand total 53,400.
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU-Tuburan Campus', pr_no='2026-09-004',
            status=PurchaseRequest.STATUS_MATCHED, grand_total=Decimal('53400'),
        )
        self.items = [
            self._item('SSD 1TB', self.it, 17500),
            self._item('Wireless Mouse/KB', self.it, 9500),
            self._item('Circuit Breaker', self.elec, 7200),
            self._item('THHN Electrical Wire', self.elec, 19200),
        ]

        self.it_supplier = self._supplier('Byte Computers', self.it)
        self.it_supplier_2 = self._supplier('Chip Traders', self.it)
        self.elec_supplier = self._supplier('Volt Electrical', self.elec)

    def _item(self, description, category, total):
        return PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description=description, category=category.name,
            quantity=1, unit='unit', unit_cost=total, total_cost=total,
        )

    def _supplier(self, name, category):
        supplier = Supplier.objects.create(
            company_name=name, email=f'{name.split()[0].lower()}@example.com', status='Approved',
        )
        SupplierCategory.objects.create(supplier=supplier, category=category)
        return supplier

    def _rfq(self, supplier, category, **extra):
        body = {
            'supplier_id': supplier.id, 'category': category.name,
            'subject': 'Request for Quotation', 'message': 'Please quote.',
            'mode_of_procurement': 'Small Value Procurement', **extra,
        }
        return self.client.post(
            f'/api/pr/{self.pr.id}/rfq/', data=json.dumps(body), content_type='application/json',
        )

    # TEST 1 - single-category PR
    def test_single_category_pr_abc_is_grand_total(self):
        pr = PurchaseRequest.objects.create(
            entity_name='CTU', pr_no='2026-09-010', status=PurchaseRequest.STATUS_MATCHED,
            grand_total=Decimal('50000'),
        )
        PurchaseRequestItem.objects.create(
            purchase_request=pr, item_description='Laptop', category=self.it.name,
            quantity=1, unit='unit', unit_cost=50000, total_cost=50000,
        )
        response = self.client.post(
            f'/api/pr/{pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.it_supplier.id, 'subject': 's', 'message': 'm'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['abc'], '₱50,000.00')
        self.assertEqual(RFQ.objects.get(id=response.json()['id']).abc, '₱50,000.00')

    # TEST 2 - mixed-category PR: each category's RFQ carries the FULL total
    def test_mixed_category_rfqs_each_carry_full_grand_total(self):
        it_rfq = self._rfq(self.it_supplier, self.it)
        elec_rfq = self._rfq(self.elec_supplier, self.elec)
        for response in (it_rfq, elec_rfq):
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(response.json()['abc'], FULL_ABC)
            self.assertEqual(RFQ.objects.get(id=response.json()['id']).abc, FULL_ABC)
        # Category grouping itself is unchanged: each RFQ tracks only its group.
        self.assertEqual(RFQ.objects.get(id=it_rfq.json()['id']).rfq_items.count(), 2)
        self.assertEqual(it_rfq.json()['category'], self.it.name)
        self.assertEqual(elec_rfq.json()['category'], self.elec.name)

    def test_client_supplied_abc_is_ignored(self):
        response = self._rfq(self.it_supplier, self.it, abc='₱1.00')
        self.assertEqual(response.json()['abc'], FULL_ABC)
        rfq_id = response.json()['id']
        patched = self.client.patch(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.it_supplier.id, 'category': self.it.name,
                             'rfq_id': rfq_id, 'abc': '₱27,000.00'}),
            content_type='application/json',
        )
        self.assertEqual(patched.status_code, 200, patched.content)
        self.assertEqual(patched.json()['abc'], FULL_ABC)
        self.assertEqual(RFQ.objects.get(id=rfq_id).abc, FULL_ABC)

    # TEST 3 - multiple issued RFQs for the same PR
    def test_multiple_issued_rfqs_share_the_pr_grand_total(self):
        responses = [
            self._rfq(self.it_supplier, self.it, send=True, generate_pdf=True),
            self._rfq(self.it_supplier_2, self.it, send=True, generate_pdf=True),
            self._rfq(self.elec_supplier, self.elec, send=True, generate_pdf=True),
        ]
        for response in responses:
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(response.json()['status'], RFQ.STATUS_SENT)
            self.assertEqual(response.json()['abc'], FULL_ABC)
        self.assertEqual(set(RFQ.objects.filter(purchase_request=self.pr).values_list('abc', flat=True)), {FULL_ABC})
        # Quotation numbering untouched: each issued RFQ got its own number.
        numbers = [r.json()['rfq_no'] for r in responses]
        self.assertEqual(len(set(numbers)), 3)
        self.assertEqual(len(mail.outbox), 3)

    # TEST 4 - PDF shows the PR grand total and every PR item
    def test_pdf_shows_full_abc_and_all_pr_items(self):
        from pdfminer.high_level import extract_text
        from api.rfq.services.rfq_generator import generate_rfq_pdf

        response = self._rfq(self.it_supplier, self.it, generate_pdf=True, preview=True)
        rfq = RFQ.objects.get(id=response.json()['id'])
        _, path = generate_rfq_pdf(rfq)
        text = ' '.join(extract_text(path).split())
        self.assertIn('Php 53,400.00', text)
        self.assertNotIn('27,000.00', text)
        for item in self.items:
            self.assertIn(item.item_description, text)
        Path(path).unlink(missing_ok=True)

    # TEST 5 - preview: ABC is the grand total, no number consumed, nothing else changes
    def test_preview_uses_grand_total_without_consuming_a_number(self):
        before_items = list(self.pr.line_items.values('id', 'total_cost', 'category'))
        response = self._rfq(self.elec_supplier, self.elec, generate_pdf=True, preview=True)
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body['abc'], FULL_ABC)
        self.assertEqual(body['status'], RFQ.STATUS_DRAFT)
        self.assertEqual(body['rfq_no'], '')
        self.assertFalse(RFQ.objects.exclude(rfq_no=None).exists())
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.grand_total, Decimal('53400'))
        self.assertEqual(self.pr.status, PurchaseRequest.STATUS_MATCHED)
        self.assertEqual(list(self.pr.line_items.values('id', 'total_cost', 'category')), before_items)
        self.assertEqual(len(mail.outbox), 0)

    # TEST 6 - quotation basis does not affect the ABC
    def test_line_and_lot_basis_both_use_grand_total(self):
        lot = self._rfq(self.it_supplier, self.it, quotation_basis='LOT')
        line = self._rfq(self.elec_supplier, self.elec, quotation_basis='LINE')
        self.assertEqual(lot.json()['quotation_basis'], 'LOT')
        self.assertEqual(line.json()['quotation_basis'], 'LINE')
        self.assertEqual(lot.json()['abc'], FULL_ABC)
        self.assertEqual(line.json()['abc'], FULL_ABC)

    # TEST 7 - manual / unregistered supplier
    def test_manual_supplier_rfq_uses_grand_total(self):
        response = self.client.post(
            f'/api/pr/{self.pr.id}/manual-rfq/',
            data=json.dumps({'manual_supplier_name': "Juan's Electrical", 'category': self.elec.name,
                             'mode_of_procurement': 'Small Value Procurement', 'abc': '₱26,400.00'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['abc'], FULL_ABC)
        self.assertEqual(RFQ.objects.get(id=response.json()['id']).abc, FULL_ABC)

    def test_stale_draft_abc_is_resynced_to_grand_total(self):
        draft = self._rfq(self.it_supplier, self.it).json()
        RFQ.objects.filter(id=draft['id']).update(abc='₱27,000.00')  # pre-change subtotal
        listed = self.client.get(f'/api/pr/{self.pr.id}/rfq/').json()['rfqs'][0]
        self.assertEqual(listed['abc'], FULL_ABC)
        issued = self._rfq(self.it_supplier, self.it, rfq_id=draft['id'], send=True, generate_pdf=True)
        self.assertEqual(issued.status_code, 200, issued.content)
        self.assertEqual(RFQ.objects.get(id=draft['id']).abc, FULL_ABC)

    def test_historical_issued_rfq_abc_is_preserved(self):
        rfq = RFQ.objects.create(
            rfq_no='RFQ-2026-0001', purchase_request=self.pr, supplier=self.it_supplier,
            category=self.it, subject='RFQ', message='m', status=RFQ.STATUS_SENT, abc='₱27,000.00',
        )
        listed = self.client.get(f'/api/pr/{self.pr.id}/rfq/').json()['rfqs'][0]
        self.assertEqual(listed['abc'], '₱27,000.00')
        rfq.refresh_from_db()
        self.assertEqual(rfq.abc, '₱27,000.00')
