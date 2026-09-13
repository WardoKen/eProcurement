"""Coverage for the admin-configurable PR numbering format (PRNumberFormat).

next_pr_number()/generate_pr_number()/validate_custom_pr_number() used to
build/validate against a single hardcoded YYYY-MM-NNN pattern. They now read
a PRNumberFormat row instead. The exact-reproduction tests here guard against
a config or logic change silently altering today's numbering for existing
deployments; the rest exercise the new configurability itself.
"""
from datetime import date, datetime
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from api.models import PRNumberFormat, PurchaseRequest
from api.views import generate_pr_number, next_pr_number, validate_custom_pr_number


def _default_config():
    """The row migration 0026 seeds - reproduces the old hardcoded behavior."""
    return PRNumberFormat.objects.get_or_create(key='global')[0]


class DefaultFormatReproducesHardcodedBehaviorTests(TestCase):
    """The seeded default config must produce byte-identical output to the
    old hardcoded f'{today:%Y-%m}-{highest + 1:03d}' logic, including its
    "sequence carries across months within a year" quirk."""

    def test_seeded_defaults_match_the_old_hardcoded_format(self):
        config = _default_config()
        self.assertEqual(config.prefix, '')
        self.assertEqual(config.date_granularity, PRNumberFormat.DATE_GRANULARITY_YEAR_MONTH)
        self.assertEqual(config.separator, '-')
        self.assertEqual(config.sequence_digits, 3)
        self.assertEqual(config.reset_period, PRNumberFormat.RESET_YEARLY)

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_first_number_of_the_month(self, _localdate):
        self.assertEqual(next_pr_number(), '2026-08-001')

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_increments_from_highest_existing_in_month(self, _localdate):
        PurchaseRequest.objects.create(entity_name='A', pr_no='2026-08-001')
        PurchaseRequest.objects.create(entity_name='B', pr_no='2026-08-007')
        self.assertEqual(next_pr_number(), '2026-08-008')

    @patch('api.views.timezone.localdate', return_value=date(2026, 9, 1))
    def test_sequence_carries_over_into_a_new_month_within_the_same_year(self, _localdate):
        PurchaseRequest.objects.create(entity_name='August', pr_no='2026-08-051')
        self.assertEqual(next_pr_number(), '2026-09-052')

    @patch('api.views.timezone.localdate', return_value=date(2027, 1, 1))
    def test_sequence_resets_on_a_new_year(self, _localdate):
        PurchaseRequest.objects.create(entity_name='Previous year', pr_no='2026-12-051')
        self.assertEqual(next_pr_number(), '2027-01-001')

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_validate_custom_pr_number_accepts_the_default_shape(self, _localdate):
        self.assertEqual(validate_custom_pr_number('2026-08-100'), '2026-08-100')

    def test_validate_custom_pr_number_rejects_malformed_input(self):
        self.assertIsNone(validate_custom_pr_number('not-a-number'))
        self.assertIsNone(validate_custom_pr_number('2026-99-100'))  # invalid month
        self.assertIsNone(validate_custom_pr_number('2026-08-1000'))  # too many sequence digits


class CustomFormatCompositionTests(TestCase):
    """Changing prefix/separator/digits/date granularity produces correctly
    shaped numbers."""

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_prefix_and_wider_sequence_digits(self, _localdate):
        config = _default_config()
        config.prefix = 'CTU'
        config.sequence_digits = 5
        config.save()

        self.assertEqual(next_pr_number(), 'CTU-2026-08-00001')

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_custom_separator(self, _localdate):
        config = _default_config()
        config.separator = '/'
        config.save()

        self.assertEqual(next_pr_number(), '2026/08/001')

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_date_granularity_year_only(self, _localdate):
        config = _default_config()
        config.date_granularity = PRNumberFormat.DATE_GRANULARITY_YEAR
        config.save()

        self.assertEqual(next_pr_number(), '2026-001')

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_date_granularity_none(self, _localdate):
        config = _default_config()
        config.date_granularity = PRNumberFormat.DATE_GRANULARITY_NONE
        config.prefix = 'PR'
        config.save()

        self.assertEqual(next_pr_number(), 'PR-001')

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_scan_and_composition_use_the_new_format_consistently(self, _localdate):
        config = _default_config()
        config.prefix = 'CTU'
        config.save()
        PurchaseRequest.objects.create(entity_name='Existing', pr_no='CTU-2026-08-004')

        self.assertEqual(next_pr_number(), 'CTU-2026-08-005')

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_validate_custom_pr_number_matches_the_active_format(self, _localdate):
        config = _default_config()
        config.prefix = 'CTU'
        config.separator = '/'
        config.save()

        self.assertEqual(validate_custom_pr_number('CTU/2026/08/001'), 'CTU/2026/08/001')
        # Numbers shaped like the *old* default format no longer validate once
        # the format has changed.
        self.assertIsNone(validate_custom_pr_number('2026-08-001'))


class ResetPeriodTests(TestCase):
    """never / yearly / monthly reset the running sequence at the right
    boundary (or never reset it at all)."""

    @patch('api.views.timezone.localdate', return_value=date(2026, 9, 1))
    def test_monthly_reset_starts_over_in_a_new_month(self, _localdate):
        config = _default_config()
        config.reset_period = PRNumberFormat.RESET_MONTHLY
        config.save()
        PurchaseRequest.objects.create(entity_name='August', pr_no='2026-08-051')

        self.assertEqual(next_pr_number(), '2026-09-001')

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_monthly_reset_still_increments_within_the_same_month(self, _localdate):
        config = _default_config()
        config.reset_period = PRNumberFormat.RESET_MONTHLY
        config.save()
        PurchaseRequest.objects.create(entity_name='August', pr_no='2026-08-005')

        self.assertEqual(next_pr_number(), '2026-08-006')

    @patch('api.views.timezone.localdate', return_value=date(2026, 9, 1))
    def test_yearly_reset_carries_over_into_a_new_month(self, _localdate):
        config = _default_config()
        config.reset_period = PRNumberFormat.RESET_YEARLY
        config.save()
        PurchaseRequest.objects.create(entity_name='August', pr_no='2026-08-051')

        self.assertEqual(next_pr_number(), '2026-09-052')

    @patch('api.views.timezone.localdate', return_value=date(2027, 1, 1))
    def test_yearly_reset_starts_over_in_a_new_year(self, _localdate):
        config = _default_config()
        config.reset_period = PRNumberFormat.RESET_YEARLY
        config.save()
        PurchaseRequest.objects.create(entity_name='December', pr_no='2026-12-051')

        self.assertEqual(next_pr_number(), '2027-01-001')

    @patch('api.views.timezone.localdate', return_value=date(2027, 1, 1))
    def test_never_reset_keeps_accumulating_across_years(self, _localdate):
        config = _default_config()
        config.reset_period = PRNumberFormat.RESET_NEVER
        config.save()
        PurchaseRequest.objects.create(entity_name='Last year', pr_no='2026-12-051')

        self.assertEqual(next_pr_number(), '2027-01-052')

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_reset_period_falls_back_to_created_at_when_date_is_not_embedded(self, _localdate):
        """date_granularity='none' means the printed number carries no date at
        all, so a yearly/monthly reset has nothing to parse out of the string
        - it must fall back to the row's own timestamp instead."""
        config = _default_config()
        config.date_granularity = PRNumberFormat.DATE_GRANULARITY_NONE
        config.reset_period = PRNumberFormat.RESET_YEARLY
        config.save()

        old = PurchaseRequest.objects.create(entity_name='Old', pr_no='050')
        PurchaseRequest.objects.filter(pk=old.pk).update(
            created_at=timezone.make_aware(datetime(2025, 12, 1))
        )
        PurchaseRequest.objects.create(entity_name='Current year', pr_no='003')

        # The 2025 row must not count toward 2026's running total.
        self.assertEqual(next_pr_number(), '004')


class MidYearFormatChangeTests(TestCase):
    """Changing the format after PRs already exist must not crash or
    miscount - historical numbers that no longer match the current pattern
    are simply skipped when computing "highest so far"."""

    @patch('api.views.timezone.localdate', return_value=date(2026, 9, 1))
    def test_generation_ignores_historically_differently_formatted_numbers(self, _localdate):
        PurchaseRequest.objects.create(entity_name='Old format', pr_no='2026-08-050')

        config = _default_config()
        config.prefix = 'CTU'
        config.save()

        # No CTU-prefixed PR exists yet under the new format, so numbering
        # starts fresh rather than crashing on the old-shaped pr_no.
        self.assertEqual(next_pr_number(), 'CTU-2026-09-001')

    @patch('api.views.timezone.localdate', return_value=date(2026, 9, 1))
    def test_generation_continues_correctly_once_new_format_has_its_own_history(self, _localdate):
        PurchaseRequest.objects.create(entity_name='Old format', pr_no='2026-08-050')

        config = _default_config()
        config.prefix = 'CTU'
        config.save()
        PurchaseRequest.objects.create(entity_name='New format', pr_no='CTU-2026-09-001')

        self.assertEqual(next_pr_number(), 'CTU-2026-09-002')

    @patch('api.views.timezone.localdate', return_value=date(2026, 9, 1))
    def test_generate_pr_number_locking_path_also_survives_format_change(self, _localdate):
        PurchaseRequest.objects.create(entity_name='Old format', pr_no='2026-08-050')
        config = _default_config()
        config.sequence_digits = 5
        config.save()

        self.assertEqual(generate_pr_number(), '2026-09-00001')
