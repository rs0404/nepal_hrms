"""Major late / early delays are penalties, reported the way the BS sheet reports them."""

from unittest import TestCase

import frappe

from nepal_hrms.custom_code.attendance_classification import classify_attendance_day
from nepal_hrms.custom_code.attendance_policy import _apply_pool_or_major_status


def _att(**kwargs):
	row = frappe._dict(
		status="Present",
		half_day_status=None,
		leave_type=None,
		custom_cnr_pool_penalty="",
	)
	row.update(kwargs)
	return row


class TestMajorDelayBecomesPenalty(TestCase):
	def test_major_delay_is_marked_as_a_half_day_penalty(self):
		doc = _att()
		_apply_pool_or_major_status(doc, "", unexcused=1, was_cnr_half_day=False)
		self.assertEqual(doc.custom_cnr_pool_penalty, "half")
		self.assertEqual(doc.status, "Half Day")
		self.assertEqual(doc.half_day_status, "Absent")

	def test_pool_full_day_still_outranks_a_major(self):
		doc = _att()
		_apply_pool_or_major_status(doc, "full", unexcused=1, was_cnr_half_day=False)
		self.assertEqual(doc.custom_cnr_pool_penalty, "full")
		self.assertEqual(doc.status, "Absent")

	def test_genuine_absence_earns_no_penalty_mark(self):
		"""A day nobody worked is charged as absence; it is not also a delay penalty."""
		doc = _att(status="Absent")
		_apply_pool_or_major_status(doc, "", unexcused=1, was_cnr_half_day=False)
		self.assertEqual(doc.custom_cnr_pool_penalty, "")
		self.assertEqual(doc.status, "Absent")

	def test_leave_day_earns_no_penalty_mark(self):
		doc = _att(status="On Leave", leave_type="Sick Leave")
		_apply_pool_or_major_status(doc, "", unexcused=1, was_cnr_half_day=False)
		self.assertEqual(doc.custom_cnr_pool_penalty, "")
		self.assertEqual(doc.status, "On Leave")

	def test_holiday_earns_no_penalty_mark(self):
		doc = _att()
		_apply_pool_or_major_status(
			doc, "", unexcused=1, was_cnr_half_day=False, is_holiday=True
		)
		self.assertEqual(doc.custom_cnr_pool_penalty, "")

	def test_excused_day_clears_a_stale_mark(self):
		doc = _att(status="Half Day", half_day_status="Absent", custom_cnr_pool_penalty="half")
		_apply_pool_or_major_status(doc, "", unexcused=0, was_cnr_half_day=False)
		self.assertEqual(doc.custom_cnr_pool_penalty, "")
		self.assertEqual(doc.status, "Present")


class TestReportSeesMajorAsPenalty(TestCase):
	"""The BS sheet has no late/early half-day column; the day must land on Penalty."""

	def test_marked_day_counts_as_half_penalty_not_absence(self):
		day = classify_attendance_day(
			status="Half Day",
			half_day_status="Absent",
			leave_type=None,
			working_hours=4.0,
			is_holiday=False,
			is_sandwich=False,
			pool_penalty="half",
		)
		self.assertEqual(day["penalty_half"], 0.5)
		self.assertEqual(day["absent_half"], 0.0)
		self.assertEqual(day["present_half"], 0.5)
		self.assertEqual(day["paid_flag"], 0.5)

	def test_unmarked_half_day_still_reads_as_absence(self):
		day = classify_attendance_day(
			status="Half Day",
			half_day_status="Absent",
			leave_type=None,
			working_hours=4.0,
			is_holiday=False,
			is_sandwich=False,
			pool_penalty="",
		)
		self.assertEqual(day["penalty_half"], 0.0)
		self.assertEqual(day["absent_half"], 1.0)
