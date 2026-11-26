"""Procurement Activity Summary PDF (api/reports/procurement_summary.py)."""
import zoneinfo
from datetime import date, datetime, timedelta

from django.test import TestCase
from django.utils.dateparse import parse_datetime

from api.models import (
    Category, PRPostingLog, PurchaseRequest, PurchaseRequestItem, RFQ, Role, Supplier, SupplierCategory,
    SupplierChangeLog, User,
)
from api.reports import procurement_summary

MANILA = zoneinfo.ZoneInfo('Asia/Manila')
URL = '/api/admin/reports/procurement-summary/'


def _login_as(client, role_name):
    role = Role.objects.get_or_create(name=role_name)[0]
    user = User.objects.create(username=f'{role_name}-{User.objects.count()}', password_hash='x', role=role, is_active=True)
    session = client.session
    session.update({'user_id': user.id, 'role': role_name, 'username': user.username})
    session.save()
    return user


class ProcurementSummaryReportTests(TestCase):
    def setUp(self):
        at = parse_datetime

        def pr(no, office, total, created, status='matched'):
            obj = PurchaseRequest.objects.create(entity_name='CTU', pr_no=no, office_section=office,
                                                 grand_total=total, status=status)
            PurchaseRequest.objects.filter(pk=obj.pk).update(created_at=at(created))
            return obj

        # November in Manila. 2026-10-31T23:30Z is already Nov 1 there.
        self.pr_a = pr('2026-11-001', 'ICT Office', 1000, '2026-10-31T23:30:00+00:00')
        self.pr_b = pr('2026-11-002', 'Registrar', 500, '2026-11-10T02:00:00+00:00', status='approved')
        pr('2026-10-009', 'ICT Office', 9999, '2026-10-15T02:00:00+00:00')  # October: outside
        PurchaseRequestItem.objects.create(purchase_request=self.pr_a, item_description='Laptop',
                                           quantity=1, unit_cost=1000, total_cost=1000, category='IT Equipment')
        self.pr_b.signature_confirmations = [{'key': 'approved_by', 'label': 'Approved By',
                                              'confirmed_role': 'bac', 'confirmed_by': 'bac'}]
        self.pr_b.save(update_fields=['signature_confirmations'])

        category = Category.objects.create(name='IT Equipment')
        Category.objects.create(name='Janitorial')
        acme = Supplier.objects.create(company_name='Acme', email='a@example.com', status='Approved')
        SupplierCategory.objects.create(supplier=acme, category=category)

        def rfq(no, status, sent, submitted=None, **extra):
            return RFQ.objects.create(
                rfq_no=no, purchase_request=self.pr_a, supplier=acme, subject='RFQ', message='m', status=status,
                sent_at=at(sent), submitted_at=at(submitted) if submitted else None,
                mode_of_procurement='Small Value Procurement', category=category, **extra,
            )

        rfq('RFQ-2026-11-001:01', RFQ.STATUS_QUOTATION_RECEIVED,
            '2026-11-02T01:00:00+00:00', '2026-11-04T01:00:00+00:00')
        rfq('RFQ-2026-11-001:02', RFQ.STATUS_SENT, '2026-11-02T01:00:00+00:00',
            splitting_justification='Separate funding source', splitting_justified_by_username='bac')
        rfq('RFQ-2026-10-009:01', RFQ.STATUS_SENT, '2026-10-16T01:00:00+00:00')  # October: outside

        PRPostingLog.objects.create(pr=self.pr_a, action=PRPostingLog.ACTION_POSTED,
                                    changed_at=at('2026-11-01T11:30:00+00:00'))
        PRPostingLog.objects.create(pr=self.pr_a, action=PRPostingLog.ACTION_UNPOSTED,
                                    changed_at=at('2026-11-03T11:30:00+00:00'))
        SupplierChangeLog.objects.create(supplier=acme, event_type=SupplierChangeLog.EVENT_STATUS,
                                         field_name='status', old_value='Pending Review', new_value='Approved',
                                         changed_by_role='admin', changed_at=at('2026-11-05T01:00:00+00:00'))

    def _november(self):
        start = datetime.combine(date(2026, 11, 1), datetime.min.time(), tzinfo=MANILA)
        end = datetime.combine(date(2026, 12, 1), datetime.min.time(), tzinfo=MANILA)
        return procurement_summary.build_summary(start=start, end=end, tz=MANILA,
                                                 period_label='November 2026', generated_by='bac')

    def test_requires_admin(self):
        self.assertEqual(self.client.get(URL).status_code, 401)
        _login_as(self.client, 'buyer')
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_returns_a_pdf_named_for_the_period(self):
        _login_as(self.client, 'admin')
        response = self.client.get(f'{URL}?date_from=2026-11-01&date_to=2026-11-30&tz=Asia/Manila')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('procurement_summary_2026-11-01_2026-11-30.pdf', response['Content-Disposition'])

    def test_an_empty_period_still_renders(self):
        _login_as(self.client, 'admin')
        response = self.client.get(f'{URL}?date_from=2020-01-01&date_to=2020-01-31')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_a_reversed_range_is_rejected(self):
        _login_as(self.client, 'admin')
        self.assertEqual(self.client.get(f'{URL}?date_from=2026-11-30&date_to=2026-11-01').status_code, 400)

    def test_purchase_request_figures_cover_only_the_period(self):
        pr = self._november()['pr']
        self.assertEqual(pr['count'], 2)
        self.assertEqual(pr['value'], 'Php 1,500.00')
        statuses = {row['label']: row['count'] for row in pr['by_status']}
        self.assertEqual((statuses['Matched'], statuses['Completed']), (1, 1))
        self.assertEqual({row['label'] for row in pr['by_office']}, {'ICT Office', 'Registrar'})
        self.assertEqual(pr['by_category'][0]['label'], 'IT Equipment')

    def test_rfq_figures_and_response_time(self):
        rfq = self._november()['rfq']
        self.assertEqual((rfq['sent'], rfq['responded'], rfq['awaiting'], rfq['rate']), (2, 1, 1, '50%'))
        self.assertEqual(rfq['by_mode'], [{'label': 'Small Value Procurement', 'rfqs': 2, 'prs': 1}])
        self.assertEqual(rfq['per_pr'][0]['pr_no'], '2026-11-001')
        self.assertEqual(rfq['avg_response'], '2.0 days')

    def test_timeliness(self):
        timeliness = self._november()['timeliness']
        self.assertEqual(timeliness['avg_to_post'], '12 hours')  # uploaded 23:30Z, posted 11:30Z next day
        self.assertEqual(timeliness['avg_posted'], '2.0 days')
        self.assertEqual(timeliness['not_posted'], 1)

    def test_suppliers_and_items_for_review(self):
        summary = self._november()
        suppliers = summary['suppliers']
        self.assertEqual(suppliers['decision_total'], 1)
        # Migrations seed the category list; only IT Equipment has an approved supplier.
        self.assertEqual(suppliers['categories_covered'], 1)
        self.assertEqual(suppliers['categories_uncovered'], Category.objects.count() - 1)
        self.assertEqual(suppliers['category_rows'], [({'label': 'IT Equipment', 'count': 1}, None)])
        self.assertEqual([row['rfq_no'] for row in summary['splitting']], ['RFQ-2026-11-001:02'])
        self.assertEqual([row['pr_no'] for row in summary['signature_flags']], ['2026-11-002'])
