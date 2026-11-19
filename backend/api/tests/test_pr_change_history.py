"""PR change history: the write-once original snapshot, the append-only edit
log written by ``pr_update``, and the ``/api/pr/<id>/changes/`` read API."""
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase

from api import pr_changes
from api.models import PRAuditLog, PurchaseRequest, PurchaseRequestItem, Role, User


def _login(client, role_name, username=None):
    role = Role.objects.get_or_create(name=role_name)[0]
    user = User.objects.create(
        username=username or f'{role_name}-user', password_hash='x', role=role, is_active=True,
        full_name=f'{role_name.title()} Person',
    )
    session = client.session
    session['user_id'] = user.id
    session['role'] = role_name
    session['username'] = user.username
    session.save()
    return user


class ChangeHistoryTestBase(TestCase):
    def setUp(self):
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU-Tuburan Campus', office_section='ICT Office', purpose='Office supplies',
            submitted_by='enduser1', status=PurchaseRequest.STATUS_UPLOADED,
        )
        self.item = PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description='Bond paper', unit='ream',
            quantity=10, unit_cost=250, total_cost=2500,
        )
        self.pr.original_extract_json = pr_changes.build_original_snapshot(self.pr)
        self.pr.save(update_fields=['original_extract_json'])
        self.admin = _login(self.client, 'admin', 'bac-secretariat')

    def _payload(self, **overrides):
        payload = {
            'entity_name': self.pr.entity_name,
            'office_section': 'ICT Office',
            'purpose': 'Office supplies',
            'items': [{
                'id': self.item.id, 'item_description': 'Bond paper', 'unit': 'ream',
                'quantity': 10, 'unit_cost': 250,
            }],
        }
        payload.update(overrides)
        return payload

    def _edit(self, **overrides):
        return self.client.patch(
            f'/api/pr/{self.pr.id}/edit/', data=json.dumps(self._payload(**overrides)),
            content_type='application/json',
        )

    def _changes(self):
        return self.client.get(f'/api/pr/{self.pr.id}/changes/')


class EditLoggingTests(ChangeHistoryTestBase):
    def test_one_log_row_per_changed_field(self):
        response = self._edit(purpose='Printer ink', office_section='Registrar', reason='OCR misread')

        self.assertEqual(response.status_code, 200, response.content)
        logs = list(PRAuditLog.objects.filter(pr=self.pr).order_by('field_name'))
        self.assertEqual([log.field_name for log in logs], ['office_section', 'purpose'])
        purpose = logs[1]
        self.assertEqual(purpose.event_type, PRAuditLog.EVENT_FIELD_EDIT)
        self.assertEqual((purpose.old_value, purpose.new_value), ('Office supplies', 'Printer ink'))
        self.assertEqual(purpose.edited_by, self.admin)
        self.assertEqual(purpose.edited_by_username, 'bac-secretariat')
        self.assertEqual(purpose.reason, 'OCR misread')
        self.assertIsNone(purpose.item_id)

    def test_no_log_row_for_unchanged_fields(self):
        # Same values, written in a different but equivalent form.
        response = self._edit(items=[{
            'id': self.item.id, 'item_description': 'Bond paper ', 'unit': 'ream',
            'quantity': '10.00', 'unit_cost': '250',
        }])

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(PRAuditLog.objects.filter(pr=self.pr).exists())

    def test_item_field_edit_is_logged_against_the_same_item(self):
        response = self._edit(
            items=[{'id': self.item.id, 'item_description': 'Bond paper', 'unit': 'ream', 'quantity': 12, 'unit_cost': 250}],
            reason='Quantity corrected per end user',
        )

        self.assertEqual(response.status_code, 200, response.content)
        # Items are updated in place, so the id (and its history) is stable.
        self.assertEqual(list(self.pr.line_items.values_list('id', flat=True)), [self.item.id])
        log = PRAuditLog.objects.get(pr=self.pr)
        self.assertEqual((log.item_id, log.field_name, log.old_value, log.new_value), (self.item.id, 'quantity', '10.00', '12.00'))

    def test_item_added_and_removed_events(self):
        response = self._edit(
            items=[{'item_description': 'Stapler', 'unit': 'pc', 'quantity': 2, 'unit_cost': 150}],
            reason='Replaced item',
        )

        self.assertEqual(response.status_code, 200, response.content)
        removed = PRAuditLog.objects.get(pr=self.pr, event_type=PRAuditLog.EVENT_ITEM_REMOVED)
        added = PRAuditLog.objects.get(pr=self.pr, event_type=PRAuditLog.EVENT_ITEM_ADDED)
        self.assertEqual(removed.item_id, self.item.id)
        self.assertEqual(json.loads(removed.old_value)['item_description'], 'Bond paper')
        new_item = self.pr.line_items.get()
        self.assertEqual(added.item_id, new_item.id)
        self.assertEqual(json.loads(added.new_value)['item_description'], 'Stapler')

        events = self._changes().json()['events']
        self.assertEqual(sorted(event['type'] for event in events), ['item_added', 'item_removed'])

    def test_reason_is_required_for_edits(self):
        for reason in (None, '', '   '):
            overrides = {'purpose': 'Printer ink'}
            if reason is not None:
                overrides['reason'] = reason
            response = self._edit(**overrides)
            self.assertEqual(response.status_code, 400)
            self.assertTrue(response.json()['reason_required'])
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.purpose, 'Office supplies')
        self.assertFalse(PRAuditLog.objects.exists())

    def test_edit_is_blocked_once_the_pr_number_is_assigned(self):
        PurchaseRequest.objects.filter(id=self.pr.id).update(pr_no='2026-11-001', status=PurchaseRequest.STATUS_IN_REVIEW)

        response = self._edit(purpose='Printer ink', reason='Late correction')

        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json()['locked'])
        self.assertIn('locked', response.json()['message'])
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.purpose, 'Office supplies')
        self.assertFalse(PRAuditLog.objects.exists())

    def test_finalizing_logs_the_edits_then_locks(self):
        response = self._edit(purpose='Printer ink', reason='OCR misread', finalize_review=True)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['pr_no'])
        self.assertEqual(PRAuditLog.objects.filter(pr=self.pr).count(), 1)

        self.assertEqual(self._edit(purpose='Again', reason='x').status_code, 409)

    def test_buyer_still_cannot_edit(self):
        _login(self.client, 'buyer', 'enduser1')
        self.assertEqual(self._edit(purpose='Printer ink', reason='x').status_code, 403)


class ChangesEndpointTests(ChangeHistoryTestBase):
    def test_changes_compare_against_the_original_with_full_history(self):
        self._edit(purpose='Printer ink', reason='First fix')
        self._edit(purpose='Printer toner', reason='Second fix')

        body = self._changes().json()

        self.assertTrue(body['original_available'])
        change = body['changes']['pr:purpose']
        self.assertEqual(change['original'], 'Office supplies')
        self.assertEqual(change['current'], 'Printer toner')
        self.assertEqual([(step['old'], step['new'], step['reason']) for step in change['history']], [
            ('Office supplies', 'Printer ink', 'First fix'),
            ('Printer ink', 'Printer toner', 'Second fix'),
        ])
        self.assertEqual(change['history'][0]['by'], 'Admin Person')
        self.assertEqual(body['changed_count'], 1)

    def test_each_change_names_the_account_that_made_it(self):
        self._edit(purpose='Printer ink', reason='First fix')
        second = _login(self.client, 'admin', 'bac-reviewer-2')
        self._edit(purpose='Printer toner', office_section='Registrar', reason='Second fix')

        body = self._changes().json()

        steps = body['changes']['pr:purpose']['history']
        self.assertEqual([step['by_username'] for step in steps], ['bac-secretariat', 'bac-reviewer-2'])
        self.assertEqual(steps[1]['by'], second.full_name)
        self.assertEqual(steps[1]['by_role'], 'BAC Secretariat')
        self.assertTrue(steps[1]['by_account_active'])
        self.assertEqual(
            [(editor['username'], editor['edit_count']) for editor in body['editors']],
            [('bac-secretariat', 1), ('bac-reviewer-2', 2)],
        )

    def test_editor_account_survives_the_user_being_deleted(self):
        self._edit(purpose='Printer ink', reason='Fix')
        User.objects.filter(id=self.admin.id).delete()
        _login(self.client, 'admin', 'another-admin')

        step = self._changes().json()['changes']['pr:purpose']['history'][0]

        self.assertEqual(step['by_username'], 'bac-secretariat')
        self.assertFalse(step['by_account_active'])

    def test_csv_export_names_the_editing_account(self):
        self._edit(purpose='Printer ink', reason='Fix')
        import csv
        import io
        response = self.client.get('/api/admin/export/purchase-requests/')
        rows = list(csv.reader(io.StringIO(b''.join(response.streaming_content).decode('utf-8-sig'))))
        notice = rows[1][rows[0].index('Edited Fields')]
        self.assertEqual(notice, '1 edited: Purpose (by bac-secretariat)')

    def test_item_changes_are_keyed_by_item_id(self):
        self._edit(
            items=[{'id': self.item.id, 'item_description': 'Bond paper', 'unit': 'ream', 'quantity': 12, 'unit_cost': 250}],
            reason='Qty',
        )
        changes = self._changes().json()['changes']
        self.assertEqual(list(changes), [f'{self.item.id}:quantity'])
        self.assertEqual((changes[f'{self.item.id}:quantity']['original'], changes[f'{self.item.id}:quantity']['current']), ('10.00', '12.00'))

    def test_edit_then_revert_is_excluded(self):
        self._edit(purpose='Printer ink', reason='Fix')
        self._edit(purpose='Office supplies', reason='Undo')

        body = self._changes().json()

        self.assertEqual(PRAuditLog.objects.filter(pr=self.pr).count(), 2)
        self.assertNotIn('pr:purpose', body['changes'])
        self.assertEqual(body['changed_count'], 0)

    def test_changes_endpoint_works_on_a_numbered_pr(self):
        self._edit(purpose='Printer ink', reason='OCR misread', finalize_review=True)
        self.pr.refresh_from_db()
        self.assertTrue(self.pr.is_locked)

        response = self._changes()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['locked'])
        self.assertEqual(body['pr_no'], self.pr.pr_no)
        self.assertEqual(body['changes']['pr:purpose']['current'], 'Printer ink')

    def test_supplier_gets_403(self):
        _login(self.client, 'supplier', 'supplier-a')
        self.assertEqual(self._changes().status_code, 403)

    def test_owning_end_user_can_read_but_other_end_users_cannot(self):
        _login(self.client, 'buyer', 'enduser1')
        self.assertEqual(self._changes().status_code, 200)

        _login(self.client, 'buyer', 'someone-else')
        self.assertEqual(self._changes().status_code, 403)

    def test_unauthenticated_gets_401(self):
        self.client.logout()
        self.assertEqual(self._changes().status_code, 401)

    def test_legacy_pr_without_snapshot_uses_first_logged_value(self):
        PurchaseRequest.objects.filter(id=self.pr.id).update(original_extract_json=None)
        self._edit(purpose='Printer ink', reason='Fix')

        body = self._changes().json()

        self.assertFalse(body['original_available'])
        self.assertEqual(body['changes']['pr:purpose']['original'], 'Office supplies')
        self.assertEqual(len(body['changes']), 1)


class OriginalSnapshotTests(TestCase):
    def test_create_pr_writes_the_snapshot_and_file_hash(self):
        _login(self.client, 'buyer', 'enduser1')
        with tempfile.TemporaryDirectory() as tmp, mock.patch('api.views.UPLOADS_DIR', Path(tmp)):
            (Path(tmp) / 'pr.pdf').write_bytes(b'%PDF-1.4 test document')
            (Path(tmp) / 'pr.pdf.extract.json').write_text(json.dumps({'fields': {'entityName': 'CTU (OCR)'}}))
            response = self.client.post('/api/pr/', data=json.dumps({'fields': {
                'entityName': 'CTU-Tuburan Campus', 'purpose': 'Office supplies', 'sourceFilename': 'pr.pdf',
                'requested_items': [{'description': 'Bond paper', 'unit': 'ream', 'quantity': '10', 'unit_cost': '250'}],
            }}), content_type='application/json')

        self.assertEqual(response.status_code, 201, response.content)
        pr = PurchaseRequest.objects.get(id=response.json()['id'])
        item = pr.line_items.get()
        snapshot = pr.original_extract_json
        self.assertEqual(snapshot['pr']['purpose'], 'Office supplies')
        self.assertEqual(snapshot['items'][str(item.id)]['quantity'], '10.00')
        self.assertEqual(snapshot['extraction'], {'entityName': 'CTU (OCR)'})
        import hashlib
        self.assertEqual(pr.original_file_hash, hashlib.sha256(b'%PDF-1.4 test document').hexdigest())

    def test_snapshot_is_write_once(self):
        pr = PurchaseRequest.objects.create(entity_name='CTU')
        pr.original_extract_json = pr_changes.build_original_snapshot(pr)
        pr.save()

        pr.original_extract_json = {'pr': {'entity_name': 'Tampered'}}
        with self.assertRaises(ValueError):
            pr.save()
        with self.assertRaises(ValueError):
            pr.save(update_fields=['original_extract_json'])
        # Saving other fields is unaffected.
        pr.refresh_from_db()
        pr.purpose = 'Updated'
        pr.save()


class AuditLogAppendOnlyTests(TestCase):
    def test_rows_cannot_be_updated_or_deleted(self):
        pr = PurchaseRequest.objects.create(entity_name='CTU')
        log = PRAuditLog.objects.create(pr=pr, field_name='purpose', old_value='a', new_value='b', reason='r')

        log.reason = 'rewritten'
        with self.assertRaises(PermissionError):
            log.save()
        with self.assertRaises(PermissionError):
            log.delete()
        with self.assertRaises(PermissionError):
            PRAuditLog.objects.filter(id=log.id).update(reason='rewritten')
        with self.assertRaises(PermissionError):
            PRAuditLog.objects.filter(id=log.id).delete()
        self.assertEqual(PRAuditLog.objects.get(id=log.id).reason, 'r')

    def test_admin_is_read_only(self):
        from django.contrib import admin as django_admin

        model_admin = django_admin.site._registry[PRAuditLog]
        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_change_permission(None))
        self.assertFalse(model_admin.has_delete_permission(None))
