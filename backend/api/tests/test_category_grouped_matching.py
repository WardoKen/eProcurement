"""Category-grouped supplier matching and category-scoped RFQs.

A mixed-category Purchase Request is split into one procurement group per
distinct item category; each RFQ belongs to one group and contains only that
group's items.
"""

import json

from django.test import TestCase

from api.models import (
    Category, PurchaseRequest, PurchaseRequestItem, RFQ, RFQItem, Role,
    Supplier, SupplierCategory, SupplierDocument, User,
)

_BASE_DOCS = ('mayor_permit', 'business_permit', 'philgeps_registration',
              'bir_registration', 'tax_clearance')


def _login_as(client, role_name, *, user=None):
    """Authenticate ``client``'s session as a user with the given role.

    Mirrors what ``login_view`` stores in the session, without a real
    password round trip in every test.
    """
    if user is None:
        role = Role.objects.get_or_create(name=role_name)[0]
        user = User.objects.create(username=f'test-{role_name}', password_hash='x', role=role)
    session = client.session
    session['user_id'] = user.id
    session['role'] = role_name
    session['username'] = user.username
    session.save()
    return user


def make_eligible_supplier(name, *categories):
    supplier = Supplier.objects.create(
        company_name=name, status='Approved', business_type='Others',
        email=f'{name.split()[0].lower()}@example.com', contact_person='Rep',
    )
    for key in _BASE_DOCS:
        SupplierDocument.objects.create(
            supplier=supplier, doc_type=key, filename=f'{key}.pdf',
            verification_status='Verified',
        )
    for category in categories:
        SupplierCategory.objects.get_or_create(supplier=supplier, category=category)
    return supplier


class CategoryGroupingTests(TestCase):
    def setUp(self):
        admin_role = Role.objects.get_or_create(name='admin')[0]
        admin_user = User.objects.create(username='bac', password_hash='x', role=admin_role)
        _login_as(self.client, 'admin', user=admin_user)
        self.aircon = Category.objects.create(name='Airconditioning and Airconditioning Systems')
        self.office_eq = Category.objects.create(name='Office Equipment')
        self.office_sup = Category.objects.create(name='Office Supplies')
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU-Tuburan Campus', pr_no='2026-09-001',
            status=PurchaseRequest.STATUS_MATCHED, grand_total=0,
        )

    def _item(self, description, category, qty=1, unit_cost=100):
        return PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description=description, category=category,
            quantity=qty, unit_cost=unit_cost, total_cost=qty * unit_cost, unit='unit',
        )

    def _match(self):
        return self.client.get(f'/api/pr/{self.pr.id}/supplier-match/').json()

    # TEST 1 - single category PR
    def test_single_category_pr_makes_one_group(self):
        for n in range(4):
            self._item(f'Item {n}', self.aircon.name)
        data = self._match()
        self.assertEqual(data['category_count'], 1)
        self.assertEqual(data['item_count'], 4)
        self.assertEqual(len(data['groups']), 1)
        self.assertEqual(data['groups'][0]['item_count'], 4)

    # TEST 2 - multiple categories
    def test_mixed_pr_groups_by_category(self):
        i1 = self._item('4HP Air Conditioner', self.aircon.name)
        i2 = self._item('Installation', self.aircon.name)
        i3 = self._item('Office Printer', self.office_eq.name)
        i4 = self._item('Bond Paper', self.office_sup.name)
        i5 = self._item('Printer Toner', self.office_sup.name)

        data = self._match()
        self.assertEqual(data['category_count'], 3)
        self.assertEqual(data['item_count'], 5)
        groups = {g['category']: g for g in data['groups']}
        self.assertEqual(
            sorted(x['id'] for x in groups[self.aircon.name]['items']), sorted([i1.id, i2.id]))
        self.assertEqual([x['id'] for x in groups[self.office_eq.name]['items']], [i3.id])
        self.assertEqual(
            sorted(x['id'] for x in groups[self.office_sup.name]['items']), sorted([i4.id, i5.id]))

    # TEST 3 - category matching is per group
    def test_category_matched_suppliers_are_per_group(self):
        self._item('Aircon', self.aircon.name)
        self._item('Printer', self.office_eq.name)
        cooltech = make_eligible_supplier('CoolTech Climate', self.aircon)
        make_eligible_supplier('ABC Office Systems', self.office_eq)

        groups = {g['category']: g for g in self._match()['groups']}
        self.assertEqual(
            [s['company_name'] for s in groups[self.aircon.name]['suppliers']], ['CoolTech Climate'])
        self.assertEqual(
            [s['company_name'] for s in groups[self.office_eq.name]['suppliers']], ['ABC Office Systems'])

    # TEST 15 - missing category
    def test_uncategorized_item_is_surfaced_not_grouped(self):
        self._item('Categorized', self.aircon.name)
        loose = self._item('No category yet', None)
        data = self._match()
        self.assertEqual([x['id'] for x in data['uncategorized_items']], [loose.id])
        grouped_ids = [x['id'] for g in data['groups'] for x in g['items']]
        self.assertNotIn(loose.id, grouped_ids)


class CategoryScopedRFQTests(TestCase):
    def setUp(self):
        admin_role = Role.objects.get_or_create(name='admin')[0]
        admin_user = User.objects.create(username='bac', password_hash='x', role=admin_role)
        _login_as(self.client, 'admin', user=admin_user)
        self.aircon = Category.objects.create(name='Airconditioning and Airconditioning Systems')
        self.office = Category.objects.create(name='Office Supplies')
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU-Tuburan Campus', pr_no='2026-09-002',
            status=PurchaseRequest.STATUS_MATCHED, grand_total=0,
        )
        self.a1 = self._item('4HP Air Conditioner', self.aircon.name, unit_cost=25000)
        self.a2 = self._item('Installation', self.aircon.name, unit_cost=5000)
        self.o1 = self._item('Bond Paper', self.office.name, unit_cost=200)
        self.o2 = self._item('Printer Toner', self.office.name, unit_cost=3000)
        self.cooltech = make_eligible_supplier('CoolTech Climate', self.aircon)
        self.metro = make_eligible_supplier('Metro Supply', self.office)

    def _item(self, description, category, qty=1, unit_cost=100):
        return PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description=description, category=category,
            quantity=qty, unit_cost=unit_cost, total_cost=qty * unit_cost, unit='unit',
        )

    def _rfq(self, body):
        return self.client.post(
            f'/api/pr/{self.pr.id}/rfq/', data=json.dumps(body),
            content_type='application/json',
        )

    # TEST 6 / 7 - RFQ contains only its category's items
    def test_rfq_contains_only_its_category_items(self):
        res = self._rfq({'supplier_id': self.cooltech.id, 'category': self.aircon.name})
        self.assertEqual(res.status_code, 201, res.content)
        rfq = RFQ.objects.get(id=res.json()['id'])
        self.assertEqual(rfq.category_id, self.aircon.id)
        linked = sorted(rfq.rfq_items.values_list('purchase_request_item_id', flat=True))
        self.assertEqual(linked, sorted([self.a1.id, self.a2.id]))
        self.assertNotIn(self.o1.id, linked)
        self.assertNotIn(self.o2.id, linked)
        self.assertEqual(sorted(x['id'] for x in res.json()['purchase_request']['items']),
                         sorted([self.a1.id, self.a2.id]))

    # TEST 16 / 37 - cross-category item is rejected
    def test_item_from_another_category_is_rejected(self):
        res = self._rfq({
            'supplier_id': self.cooltech.id, 'category': self.aircon.name,
            'item_ids': [self.a1.id, self.o1.id],
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn('do not belong', res.json()['message'])

    # TEST 9 - independent selection per group
    def test_selection_is_independent_per_group(self):
        a = self._rfq({'supplier_id': self.cooltech.id, 'category': self.aircon.name})
        b = self._rfq({'supplier_id': self.metro.id, 'category': self.office.name})
        self.assertEqual(a.status_code, 201)
        self.assertEqual(b.status_code, 201)
        self.assertEqual(RFQ.objects.filter(purchase_request=self.pr).count(), 2)
        self.assertEqual(RFQ.objects.get(id=a.json()['id']).category_id, self.aircon.id)
        self.assertEqual(RFQ.objects.get(id=b.json()['id']).category_id, self.office.id)

    # TEST 10 - same supplier for multiple groups, no record corruption
    def test_same_supplier_two_groups(self):
        both = make_eligible_supplier('OneStop Trading', self.aircon, self.office)
        a = self._rfq({'supplier_id': both.id, 'category': self.aircon.name})
        b = self._rfq({'supplier_id': both.id, 'category': self.office.name})
        self.assertEqual(a.status_code, 201)
        self.assertEqual(b.status_code, 201)
        self.assertEqual(Supplier.objects.filter(company_name='OneStop Trading').count(), 1)
        self.assertEqual(
            RFQ.objects.filter(purchase_request=self.pr, supplier=both).count(), 2)
        # A second RFQ for the SAME (supplier, category) after issuing is blocked.
        issued = self._rfq({
            'supplier_id': both.id, 'category': self.aircon.name,
            'mode_of_procurement': 'Shopping', 'send': True, 'generate_pdf': True,
        })
        self.assertEqual(issued.status_code, 200)  # reuses the draft, then issues
        again = self._rfq({'supplier_id': both.id, 'category': self.aircon.name})
        self.assertEqual(again.status_code, 409)

    # TEST 12 - a draft consumes no quotation number
    def test_draft_has_no_number_until_issued(self):
        res = self._rfq({'supplier_id': self.cooltech.id, 'category': self.aircon.name,
                         'mode_of_procurement': 'Shopping', 'generate_pdf': True, 'preview': True})
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json()['quotation_no'], '')
        self.assertIsNone(RFQ.objects.get(id=res.json()['id']).rfq_no)

        issued = self._rfq({
            'supplier_id': self.cooltech.id, 'category': self.aircon.name,
            'rfq_id': res.json()['id'], 'mode_of_procurement': 'Shopping',
            'send': True, 'generate_pdf': True,
        })
        self.assertEqual(issued.status_code, 200, issued.content)
        self.assertRegex(issued.json()['quotation_no'], r'^RFQ-\d{4}-\d{4}$')

    # TEST 17 - duplicate item records are never created
    def test_grouping_does_not_duplicate_items(self):
        before = PurchaseRequestItem.objects.filter(purchase_request=self.pr).count()
        self._rfq({'supplier_id': self.cooltech.id, 'category': self.aircon.name})
        self._rfq({'supplier_id': self.metro.id, 'category': self.office.name})
        self.assertEqual(
            PurchaseRequestItem.objects.filter(purchase_request=self.pr).count(), before)

    # multi-category PR requires an explicit group
    def test_mixed_pr_without_category_is_rejected(self):
        res = self._rfq({'supplier_id': self.cooltech.id})
        self.assertEqual(res.status_code, 400)
        self.assertIn('multiple procurement categories', res.json()['message'])

    # TEST 18 - security
    def test_non_admin_cannot_create_rfq(self):
        _login_as(self.client, 'buyer')
        res = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.cooltech.id, 'category': self.aircon.name}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(RFQ.objects.count(), 0)
