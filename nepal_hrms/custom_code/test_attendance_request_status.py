"""An approved Attendance Request decides how the day reads."""

from unittest import TestCase

import frappe

from nepal_hrms.custom_code.attendance_policy import apply_attendance_request_status


def _att(status="Absent", half_day_status=None, leave_type=None, date="2026-08-31"):
	return frappe._dict(
		status=status,
		half_day_status=half_day_status,
		leave_type=leave_type,
		attendance_date=date,
		employee="EMP-001",
	)


FULL = {"name": "HR-ARQ-1", "half_day": 0, "half_day_date": None}
HALF = {"name": "HR-ARQ-2", "half_day": 1, "half_day_date": "2026-08-31"}
HALF_ELSEWHERE = {"name": "HR-ARQ-3", "half_day": 1, "half_day_date": "2026-09-01"}


class TestAttendanceRequestStatus(TestCase):
	def test_a_full_request_overrides_absent(self):
		doc = _att(status="Absent")
		apply_attendance_request_status(doc, FULL)
		self.assertEqual((doc.status, doc.half_day_status), ("Present", None))

	def test_a_full_request_clears_a_penalty_half_day(self):
		doc = _att(status="Half Day", half_day_status="Absent")
		apply_attendance_request_status(doc, FULL)
		self.assertEqual((doc.status, doc.half_day_status), ("Present", None))

	def test_a_half_day_request_lands_as_a_half_day(self):
		doc = _att(status="Absent")
		apply_attendance_request_status(doc, HALF)
		self.assertEqual((doc.status, doc.half_day_status), ("Half Day", "Absent"))

	def test_a_half_day_request_for_another_date_covers_this_one_fully(self):
		"""A ranged request half-daying a different date is a full day here."""
		doc = _att(status="Absent")
		apply_attendance_request_status(doc, HALF_ELSEWHERE)
		self.assertEqual((doc.status, doc.half_day_status), ("Present", None))

	def test_a_half_day_leave_keeps_its_leave_and_takes_the_other_half(self):
		"""Leave holds one half; the request accounts for the half it covers."""
		doc = _att(status="Half Day", half_day_status="Absent", leave_type="Sick Leave")
		apply_attendance_request_status(doc, FULL)
		self.assertEqual(doc.status, "Half Day")
		self.assertEqual(doc.half_day_status, "Present")
		self.assertEqual(doc.leave_type, "Sick Leave")

	def test_full_day_leave_is_never_overridden(self):
		doc = _att(status="On Leave", leave_type="Annual/Home Leave")
		apply_attendance_request_status(doc, FULL)
		self.assertEqual(doc.status, "On Leave")

	def test_a_day_off_is_never_overridden(self):
		for status in ("Holiday", "Weekly Off"):
			doc = _att(status=status)
			apply_attendance_request_status(doc, FULL)
			self.assertEqual(doc.status, status)

	def test_a_holiday_date_is_left_alone(self):
		doc = _att(status="Absent")
		apply_attendance_request_status(
			doc, FULL, holiday=frappe._dict(is_holiday=True, weekly_off=True)
		)
		self.assertEqual(doc.status, "Absent")
