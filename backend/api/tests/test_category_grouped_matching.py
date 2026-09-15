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
        self.assertEqual(issued.json()['quotation_no'], '2026-09-002:01')

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


class PRSubmissionAndReviewSeparationTests(TestCase):
    """End User submission vs. BAC Secretariat review/edit split.

    The End User submits the original PR document and, once saved, may only
    view it and its status - all field corrections happen on the BAC/admin
    review side (``pr_update`` / ``/edit/``), never through the submission
    path again and never through any endpoint reachable by a buyer session.
    """

    def setUp(self):
        self.buyer = _login_as(self.client, 'buyer')

    def _submit_as_buyer(self, entity='CTU-Tuburan Campus', source_filename='original-pr.pdf', items=None):
        fields = {
            'entityName': entity,
            'reviewOnly': True,
            'sourceFilename': source_filename,
            'submittedBy': self.buyer.username,
            'requested_items': items if items is not None else [
                {'description': 'Bond Paper', 'quantity': 10, 'unit_cost': 100, 'unit': 'ream'},
            ],
            'declaration_acknowledged': True,
        }
        return self.client.post(
            '/api/pr/', data=json.dumps({'fields': fields}), content_type='application/json',
        )

    # 1. End User uploads a valid PR - submission succeeds and the original
    # document is visible to the End User afterward.
    def test_end_user_submission_succeeds_and_document_is_viewable(self):
        response = self._submit_as_buyer()
        self.assertEqual(response.status_code, 201, response.content)
        pr_id = response.json()['id']

        listing = self.client.get(
            f'/api/pr/list/?submitted_by={self.buyer.username}'
        ).json()
        record = next(r for r in listing if r['id'] == pr_id)
        self.assertTrue(record['source_file_url'].endswith('/uploads/original-pr.pdf'))
        self.assertEqual(record['status'], PurchaseRequest.STATUS_UPLOADED)

    # 2. End User attempts to call the PR edit/update API directly - rejected,
    # no data changes.
    def test_end_user_cannot_edit_submitted_pr(self):
        pr_id = self._submit_as_buyer().json()['id']
        pr_before = PurchaseRequest.objects.get(id=pr_id)

        response = self.client.patch(
            f'/api/pr/{pr_id}/edit/',
            data=json.dumps({'entity_name': 'Tampered Entity', 'items': []}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        pr_after = PurchaseRequest.objects.get(id=pr_id)
        self.assertEqual(pr_after.entity_name, pr_before.entity_name)
        self.assertEqual(PurchaseRequestItem.objects.filter(purchase_request_id=pr_id).count(), 1)

    def test_end_user_cannot_change_status_or_delete_submitted_pr(self):
        pr_id = self._submit_as_buyer().json()['id']

        status_response = self.client.patch(
            f'/api/pr/{pr_id}/status/',
            data=json.dumps({'status': PurchaseRequest.STATUS_APPROVED}),
            content_type='application/json',
        )
        delete_response = self.client.delete(f'/api/pr/{pr_id}/')

        self.assertEqual(status_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertTrue(PurchaseRequest.objects.filter(id=pr_id).exists())
        self.assertEqual(
            PurchaseRequest.objects.get(id=pr_id).status, PurchaseRequest.STATUS_UPLOADED,
        )

    # 3 & 4. BAC opens the PR: original document is visible, OCR/structured
    # fields are editable, and a correction changes the structured item only.
    def test_bac_can_review_and_correct_ocr_extracted_fields(self):
        pr_id = self._submit_as_buyer().json()['id']
        _login_as(self.client, 'admin')

        details = self.client.get(f'/api/pr/{pr_id}/details/').json()
        self.assertTrue(details['source_file_url'].endswith('/uploads/original-pr.pdf'))
        self.assertEqual(details['items'][0]['item_description'], 'Bond Paper')

        response = self.client.patch(
            f'/api/pr/{pr_id}/edit/',
            data=json.dumps({
                'entity_name': 'CTU-Tuburan Campus (Corrected)',
                'items': [{
                    'stock_property_no': '', 'unit': 'ream', 'category': '',
                    'item_description': 'Bond Paper (Corrected by BAC)',
                    'quantity': 10, 'unit_cost': 100,
                }],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content)

        pr = PurchaseRequest.objects.get(id=pr_id)
        self.assertEqual(pr.entity_name, 'CTU-Tuburan Campus (Corrected)')
        item = pr.line_items.get()
        self.assertEqual(item.item_description, 'Bond Paper (Corrected by BAC)')
        # The original uploaded document is untouched by the correction.
        self.assertEqual(pr.source_filename, 'original-pr.pdf')

    # Original document immutability - even an explicit attempt to change it
    # via the BAC edit payload is ignored.
    def test_bac_edit_cannot_change_the_original_document_reference(self):
        pr_id = self._submit_as_buyer().json()['id']
        _login_as(self.client, 'admin')

        response = self.client.patch(
            f'/api/pr/{pr_id}/edit/',
            data=json.dumps({
                'entity_name': 'CTU-Tuburan Campus',
                'source_filename': 'swapped-malicious.pdf',
                'items': [],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(PurchaseRequest.objects.get(id=pr_id).source_filename, 'original-pr.pdf')

    # 5. RFQ generation after BAC correction uses the corrected structured
    # data, and the original PR document remains untouched.
    def test_rfq_generation_uses_bac_corrected_item_data(self):
        category = Category.objects.create(name='Office Supplies')
        pr_id = self._submit_as_buyer(items=[
            {'description': 'Bond Paper', 'quantity': 10, 'unit_cost': 100, 'unit': 'ream'},
        ]).json()['id']
        supplier = make_eligible_supplier('Metro Supply', category)

        _login_as(self.client, 'admin')
        pr = PurchaseRequest.objects.get(id=pr_id)
        item = pr.line_items.get()
        self.client.patch(
            f'/api/pr/{pr_id}/edit/',
            data=json.dumps({
                'entity_name': pr.entity_name,
                'items': [{
                    'stock_property_no': '', 'unit': 'ream', 'category': category.name,
                    'item_description': 'Bond Paper, Long (Corrected by BAC)',
                    'quantity': 10, 'unit_cost': 100,
                }],
            }),
            content_type='application/json',
        )

        rfq_response = self.client.post(
            f'/api/pr/{pr_id}/rfq/',
            data=json.dumps({'supplier_id': supplier.id, 'category': category.name}),
            content_type='application/json',
        )
        self.assertEqual(rfq_response.status_code, 201, rfq_response.content)
        rfq_items = rfq_response.json()['purchase_request']['items']
        self.assertEqual(rfq_items[0]['item_description'], 'Bond Paper, Long (Corrected by BAC)')

        pr.refresh_from_db()
        self.assertEqual(pr.source_filename, 'original-pr.pdf')

    # 9. Buyer vs Admin authorization across every PR mutation endpoint.
    def test_only_admin_can_reach_pr_mutation_endpoints(self):
        pr_id = self._submit_as_buyer().json()['id']
        endpoints = [
            ('patch', f'/api/pr/{pr_id}/edit/', {'entity_name': 'X', 'items': []}),
            ('patch', f'/api/pr/{pr_id}/status/', {'status': PurchaseRequest.STATUS_IN_REVIEW}),
            ('delete', f'/api/pr/{pr_id}/', None),
        ]
        for method, url, body in endpoints:
            kwargs = {'content_type': 'application/json'}
            if body is not None:
                kwargs['data'] = json.dumps(body)
            response = getattr(self.client, method)(url, **kwargs)
            self.assertEqual(response.status_code, 403, f'{method.upper()} {url} as buyer should be 403')

        _login_as(self.client, 'admin')
        for method, url, body in endpoints:
            kwargs = {'content_type': 'application/json'}
            if body is not None:
                kwargs['data'] = json.dumps(body)
            response = getattr(self.client, method)(url, **kwargs)
            self.assertIn(response.status_code, (200, 204), f'{method.upper()} {url} as admin should succeed')
        self.assertEqual(RFQ.objects.count(), 0)
