"""The PWA summary and the desk report must be the same numbers, by construction."""

from datetime import date
from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.custom_code import attendance_summary
from nepal_hrms.custom_code.attendance_summary import (
	TOTAL_FIELDS,
	_upcoming_leave,
	summarize_period,
)


class TestClassificationModuleIsSelfContained(TestCase):
	def test_it_does_not_import_the_report(self):
		# The whole point of the extraction: the PWA must reach these rules without
		# dragging in a report module. A cycle here would undo that.
		import nepal_hrms.custom_code.attendance_classification as mod

		source = open(mod.__file__).read()
		self.assertNotIn("monthly_attendance_sheet_bs", source)

	def test_report_still_re_exports_every_moved_name(self):
		from nepal_hrms.nepal_hrms.report.monthly_attendance_sheet_bs import (
			monthly_attendance_sheet_bs as report,
		)

		for name in (
			"classify_attendance_day", "_finalize_paid_days", "_include_in_paid_day_audit",
			"_new_day_classification", "_add_leave_unit", "_accumulate_day",
			"_collect_day_dates", "_date_labels", "_merge_breakdown",
			"_get_leave_type_details", "DAY_COUNT_DATE_FIELDS",
			"LEAVE_GROUP_ANNUAL_HOME", "LEAVE_GROUP_SICK", "LEAVE_GROUP_OTHER",
		):
			self.assertTrue(hasattr(report, name), f"report no longer exports {name}")


class TestUpcomingLeave(TestCase):
	"""Future leave is reported, but never inside the audited totals."""

	def _map(self, day, status, **extra):
		detail = {"status": status, "leave_type": "Home Leave", "half_day": 0}
		detail.update(extra)
		return {("EMP-1", day): [detail]}

	def test_future_approved_leave_is_counted_as_upcoming(self):
		out = _upcoming_leave(
			self._map(date(2026, 2, 10), "approved"), "EMP-1", date(2026, 2, 1)
		)
		self.assertEqual(out["approved_leave_days"], 1.0)
		self.assertEqual(out["approved_leave_types"], {"Home Leave": 1.0})
		self.assertEqual(out["pending_leave_days"], 0.0)

	def test_past_leave_is_not_upcoming(self):
		out = _upcoming_leave(
			self._map(date(2026, 1, 10), "approved"), "EMP-1", date(2026, 2, 1)
		)
		self.assertEqual(out["approved_leave_days"], 0.0)

	def test_today_is_neither_audited_nor_upcoming(self):
		# Deliberate one-day gap: today is genuinely undetermined.
		out = _upcoming_leave(
			self._map(date(2026, 2, 1), "approved"), "EMP-1", date(2026, 2, 1)
		)
		self.assertEqual(out["approved_leave_days"], 0.0)

	def test_pending_and_rejected_are_separated(self):
		out = _upcoming_leave(
			self._map(date(2026, 2, 10), "pending"), "EMP-1", date(2026, 2, 1)
		)
		self.assertEqual(out["pending_leave_days"], 1.0)
		self.assertEqual(out["approved_leave_days"], 0.0)

		out = _upcoming_leave(
			self._map(date(2026, 2, 10), "rejected"), "EMP-1", date(2026, 2, 1)
		)
		self.assertEqual(out["pending_leave_days"], 0.0)

	def test_half_day_counts_a_half(self):
		out = _upcoming_leave(
			self._map(date(2026, 2, 10), "approved", half_day=1, half_day_date="2026-02-10"),
			"EMP-1",
			date(2026, 2, 1),
		)
		self.assertEqual(out["approved_leave_days"], 0.5)

	def test_other_employees_are_ignored(self):
		out = _upcoming_leave(
			self._map(date(2026, 2, 10), "approved"), "EMP-2", date(2026, 2, 1)
		)
		self.assertEqual(out["approved_leave_days"], 0.0)


class TestSummarizePeriodDegradesHonestly(TestCase):
	def test_employee_without_a_company_returns_empty_not_an_error(self):
		with patch.object(frappe.db, "get_value", return_value=None):
			out = summarize_period("EMP-GONE", date(2026, 1, 1), date(2026, 1, 31))
		self.assertFalse(out["found"])
		self.assertEqual(out["totals"]["total_present"], 0)

	def test_totals_expose_every_allowlisted_field(self):
		with patch.object(frappe.db, "get_value", return_value=None):
			out = summarize_period("EMP-GONE", date(2026, 1, 1), date(2026, 1, 31))
		self.assertEqual(set(out["totals"]), set(TOTAL_FIELDS))

	def test_allowlist_carries_no_per_day_payload(self):
		# The raw report row holds a day_YYYY_MM_DD JSON blob per day, each with
		# per-minute bar_data. None of it belongs in a summary response.
		self.assertFalse([f for f in TOTAL_FIELDS if f.startswith("day_")])
