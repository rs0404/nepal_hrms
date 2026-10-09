"""The slip assigns the occurrence pool itself, as the BS sheet does."""

from unittest import TestCase
from unittest.mock import patch

import frappe
from frappe.utils import getdate

from nepal_hrms.overrides.salary_slip import _counted_in_absent_bucket


def _row(status, half_day_status=None):
	return frappe._dict(status=status, half_day_status=half_day_status)


class TestCountedInAbsentBucket(TestCase):
	"""Which penalty days HRMS already folded into absent_days."""

	def test_a_full_absence_is_in_the_bucket(self):
		self.assertTrue(_counted_in_absent_bucket(_row("Absent")))

	def test_a_half_day_whose_other_half_is_absent_is_in_the_bucket(self):
		self.assertTrue(_counted_in_absent_bucket(_row("Half Day", "Absent")))

	def test_a_row_still_reading_present_is_not(self):
		"""A live assignment on an unrecalculated row was never counted."""
		self.assertFalse(_counted_in_absent_bucket(_row("Present")))

	def test_a_half_day_whose_other_half_was_worked_is_not(self):
		self.assertFalse(_counted_in_absent_bucket(_row("Half Day", "Present")))

	def test_a_leave_day_is_not(self):
		self.assertFalse(_counted_in_absent_bucket(_row("On Leave")))

	def test_a_missing_status_is_not(self):
		self.assertFalse(_counted_in_absent_bucket(_row(None)))


class TestPenaltyFromTheLivePool(TestCase):
	"""A penalty the pool assigns counts even with no mark written."""

	def _days(self, rows, assigned):
		with patch(
			"nepal_hrms.overrides.salary_slip.frappe.get_meta"
		) as meta, patch(
			"nepal_hrms.overrides.salary_slip.frappe.db.get_single_value",
			return_value=0.5,
		), patch(
			"nepal_hrms.overrides.salary_slip.frappe.get_all", return_value=rows
		), patch(
			"nepal_hrms.custom_code.attendance_holiday.holiday_dates_between",
			return_value=set(),
		), patch(
			"nepal_hrms.custom_code.attendance_policy.assign_employee_pool_penalties_for_range",
			return_value=assigned,
		), patch(
			"nepal_hrms.custom_code.attendance_policy.get_hr_settings", return_value={}
		), patch(
			"nepal_hrms.custom_code.policy_escape.escaped_dates", return_value=set()
		):
			meta.return_value.has_field.return_value = True
			from nepal_hrms.overrides.salary_slip import get_pool_penalty_days

			return get_pool_penalty_days("EMP-001", "2026-08-14", "2026-09-13")

	def test_an_unmarked_day_the_pool_assigns_still_counts(self):
		"""Nabin 2026-08-31: the sheet charged it, the slip charged nothing."""
		from frappe.utils import getdate

		days, dates = self._days(
			[frappe._dict(attendance_date=getdate("2026-08-31"), status="Present",
			              half_day_status=None, custom_cnr_pool_penalty="")],
			{getdate("2026-08-31"): "half"},
		)
		self.assertEqual(days, 0.5)
		self.assertFalse(dates[0]["in_absent_bucket"])

	def test_a_stored_mark_overrides_the_live_assignment(self):
		from frappe.utils import getdate

		days, dates = self._days(
			[frappe._dict(attendance_date=getdate("2026-08-31"), status="Absent",
			              half_day_status=None, custom_cnr_pool_penalty="full")],
			{getdate("2026-08-31"): "half"},
		)
		self.assertEqual(days, 1.0)
		self.assertEqual(dates[0]["kind"], "full")
		self.assertTrue(dates[0]["in_absent_bucket"])

	def test_a_day_with_neither_is_not_a_penalty(self):
		from frappe.utils import getdate

		days, dates = self._days(
			[frappe._dict(attendance_date=getdate("2026-08-31"), status="Present",
			              half_day_status=None, custom_cnr_pool_penalty="")],
			{},
		)
		self.assertEqual(days, 0.0)
		self.assertEqual(dates, [])


class TestEscapedDayIsNotCharged(TestCase):
	"""A mark stamped before the escape existed must not reach the slip."""

	def test_stored_mark_on_an_escaped_day(self):
		rows = [
			frappe._dict(attendance_date="2026-08-20", status="Half Day", half_day_status="Absent", custom_cnr_pool_penalty="half"),
			frappe._dict(attendance_date="2026-08-21", status="Half Day", half_day_status="Absent", custom_cnr_pool_penalty="half"),
		]
		with patch("nepal_hrms.overrides.salary_slip.frappe.get_meta") as meta, patch(
			"nepal_hrms.overrides.salary_slip.frappe.db.get_single_value", return_value=0.5
		), patch("nepal_hrms.overrides.salary_slip.frappe.get_all", return_value=rows), patch(
			"nepal_hrms.custom_code.attendance_holiday.holiday_dates_between", return_value=set()
		), patch(
			"nepal_hrms.custom_code.attendance_policy.assign_employee_pool_penalties_for_range",
			return_value={},
		), patch(
			"nepal_hrms.custom_code.attendance_policy.get_hr_settings", return_value={}
		), patch(
			"nepal_hrms.custom_code.policy_escape.escaped_dates",
			return_value={getdate("2026-08-20")},
		):
			meta.return_value.has_field.return_value = True
			from nepal_hrms.overrides.salary_slip import get_pool_penalty_days

			days, dates = get_pool_penalty_days("EMP-001", "2026-08-14", "2026-09-13")
		self.assertEqual(days, 0.5)
		self.assertEqual([d["date"] for d in dates], ["2026-08-21"])
