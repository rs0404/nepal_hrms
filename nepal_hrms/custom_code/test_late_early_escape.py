"""Escape Late Entry / Early Exit keeps the day Present and out of every count.

The escape used to clear only the flags. A Half Day it could not recognise as
its own stayed Half Day, the period sweep re-stamped ½P on escaped days from
their stale flags, and payroll trusted those marks.
"""

from datetime import date
from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.custom_code import attendance_policy as ap
from nepal_hrms.custom_code import policy_escape as pe


def _att(**kw):
	row = frappe._dict(
		status="Half Day",
		leave_type=None,
		half_day_status="Absent",
		late_entry=0,
		early_exit=0,
		custom_cnr_unexcused_late=0,
		custom_cnr_unexcused_early=0,
		custom_cnr_late_in_pool=0,
		custom_cnr_early_in_pool=0,
		custom_cnr_pool_penalty="",
	)
	row.update(kw)
	return row


class TestLooksLikeCnrPenalty(TestCase):
	def test_half_day_with_an_early_exit_and_no_mark(self):
		"""What bulk Recheck left behind: no mark, half_day_status Absent."""
		self.assertTrue(ap._looks_like_cnr_penalty(_att(early_exit=1)))

	def test_pool_full_day(self):
		self.assertTrue(ap._looks_like_cnr_penalty(_att(status="Absent", custom_cnr_late_in_pool=1)))

	def test_stored_mark_alone(self):
		self.assertTrue(ap._looks_like_cnr_penalty(_att(custom_cnr_pool_penalty="half")))

	def test_leave_half_day_is_not_ours(self):
		self.assertFalse(ap._looks_like_cnr_penalty(_att(leave_type="Sick Leave", early_exit=1)))

	def test_absence_without_punches_is_not_ours(self):
		self.assertFalse(ap._looks_like_cnr_penalty(_att(status="Absent")))

	def test_present_day_is_left_alone(self):
		self.assertFalse(ap._looks_like_cnr_penalty(_att(status="Present", late_entry=1)))


class TestEscapedDates(TestCase):
	def setUp(self):
		frappe.local._nepal_policy_escapes = None

	def _dates(self, rows, start, end):
		with (
			patch.object(pe, "queryable_flags", return_value=("escape_late_early",)),
			patch.object(pe.frappe, "get_all", return_value=[frappe._dict(r) for r in rows]),
		):
			return pe.escaped_dates("EMP-1", "escape_late_early", start, end)

	def test_clipped_to_the_period(self):
		dates = self._dates(
			[{"from_date": "2026-07-10", "to_date": "2026-07-20"}], "2026-07-17", "2026-08-16"
		)
		self.assertEqual(dates, {date(2026, 7, d) for d in (17, 18, 19, 20)})

	def test_open_ended_covers_the_whole_period(self):
		dates = self._dates([{"from_date": None, "to_date": None}], "2026-07-17", "2026-07-19")
		self.assertEqual(dates, {date(2026, 7, 17), date(2026, 7, 18), date(2026, 7, 19)})

	def test_missing_column_escapes_nothing(self):
		frappe.local._nepal_policy_escapes = None
		with patch.object(pe, "queryable_flags", return_value=()):
			self.assertEqual(pe.escaped_dates("EMP-1", "escape_late_early", "2026-07-17", "2026-07-19"), set())


class TestSweepUndoesEscapedPenalty(TestCase):
	def test_escaped_half_day_goes_back_to_present(self):
		row = _att(custom_cnr_unexcused_early=1, early_exit=1, custom_cnr_pool_penalty="half")
		with patch.object(ap, "_is_genuine_absent", return_value=False):
			ap._apply_pool_or_major_status(row, "", 0, ap._looks_like_cnr_penalty(row), is_holiday=False)
		self.assertEqual((row.status, row.half_day_status, row.custom_cnr_pool_penalty), ("Present", None, ""))
