# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
from datetime import date
from unittest import TestCase
from unittest.mock import patch

from frappe.utils import add_days, getdate

from nepal_hrms.custom_code.attendance_holiday import (
	_day_is_full_leave_or_absent,
)
from nepal_hrms.custom_code.sandwich_leave import evaluate_leave_sandwich


class TestEvaluateLeaveSandwich(TestCase):
	"""Unit tests with mocked holiday calendar and leave anchors."""

	def _run(
		self,
		holidays,
		leave_anchor_days,
		from_date,
		to_date,
		current_leave=None,
	):
		holiday_set = {getdate(d) for d in holidays}

		def _is_holiday(_employee, day):
			return getdate(day) in holiday_set

		def _adjacent(_employee, day, direction=-1):
			curr = add_days(getdate(day), direction)
			for _ in range(366):
				if getdate(curr) not in holiday_set:
					return getdate(curr)
				curr = add_days(curr, direction)
			return getdate(curr)

		def _anchor(_employee, day, ctx):
			d = getdate(day)
			if ctx and ctx.get("from_date") and ctx.get("to_date"):
				if getdate(ctx["from_date"]) <= d <= getdate(ctx["to_date"]):
					return True
			return d in {getdate(x) for x in leave_anchor_days}

		with patch(
			"nepal_hrms.custom_code.sandwich_leave.is_holiday_or_weekend",
			side_effect=_is_holiday,
		), patch(
			"nepal_hrms.custom_code.sandwich_leave.get_adjacent_working_day",
			side_effect=_adjacent,
		), patch(
			"nepal_hrms.custom_code.sandwich_leave.day_is_full_leave_or_absent_for_sandwich",
			side_effect=_anchor,
		):
			return evaluate_leave_sandwich(
				"EMP-001", from_date, to_date, current_leave=current_leave
			)

	def test_mon_tue_after_weekend_with_present_friday_not_violation(self):
		"""HR-LAP-2026-00362-like: Fri present, Mon–Tue leave, Wed leave elsewhere."""
		result = self._run(
			holidays=[date(2026, 8, 22), date(2026, 8, 23)],
			leave_anchor_days=[date(2026, 8, 26), date(2026, 8, 27), date(2026, 8, 28)],
			from_date=date(2026, 8, 24),
			to_date=date(2026, 8, 25),
			current_leave={
				"name": "HR-LAP-2026-00362",
				"from_date": date(2026, 8, 24),
				"to_date": date(2026, 8, 25),
			},
		)
		self.assertFalse(result["violation"])
		self.assertTrue(result["warning"])

	def test_classic_friday_mon_split_weekend_is_violation(self):
		result = self._run(
			holidays=[date(2026, 8, 22), date(2026, 8, 23)],
			leave_anchor_days=[date(2026, 8, 24)],
			from_date=date(2026, 8, 21),
			to_date=date(2026, 8, 21),
			current_leave={
				"name": "LAP-FRI",
				"from_date": date(2026, 8, 21),
				"to_date": date(2026, 8, 21),
			},
		)
		self.assertTrue(result["violation"])
		self.assertIn("2026-08-22", result["holiday_span"])

	@patch(
		"nepal_hrms.custom_code.sandwich_leave._day_is_full_leave_or_absent",
		return_value=False,
	)
	def test_current_application_dates_count_as_leave_anchors(self, _attendance_anchor):
		from nepal_hrms.custom_code.sandwich_leave import (
			day_is_full_leave_or_absent_for_sandwich,
		)

		ctx = {
			"name": "LAP-DRAFT",
			"from_date": date(2026, 8, 24),
			"to_date": date(2026, 8, 25),
		}
		self.assertTrue(
			day_is_full_leave_or_absent_for_sandwich("EMP-001", date(2026, 8, 24), ctx)
		)
		self.assertFalse(
			day_is_full_leave_or_absent_for_sandwich("EMP-001", date(2026, 8, 24), None)
		)

	@patch(
		"nepal_hrms.custom_code.attendance_holiday.covering_leave_application",
		return_value=None,
	)
	@patch(
		"nepal_hrms.custom_code.attendance_holiday.frappe.db.get_value",
		return_value=None,
	)
	def test_sandwich_anchor_queries_submitted_attendance_only(
		self, get_attendance, _covering_leave
	):
		self.assertFalse(
			_day_is_full_leave_or_absent("EMP-001", date(2026, 8, 24))
		)
		self.assertEqual(get_attendance.call_args.args[1]["docstatus"], 1)
