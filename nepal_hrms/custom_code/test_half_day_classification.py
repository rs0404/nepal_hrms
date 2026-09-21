"""A half day with no leave is half worked, not a whole day absent."""

from unittest import TestCase

from nepal_hrms.custom_code.attendance_classification import classify_attendance_day


def _day(half_day_status, leave_type=None, hours=6.2):
	return classify_attendance_day(
		status="Half Day",
		half_day_status=half_day_status,
		leave_type=leave_type,
		working_hours=hours,
		is_holiday=False,
		is_sandwich=False,
		leave_type_details={},
		pool_penalty="",
	)


class TestHalfDayWithoutLeave(TestCase):
	"""An hours-threshold half day: the person was here for half of it."""

	def test_other_half_absent_is_half_worked_half_absent(self):
		day = _day("Absent")
		self.assertEqual(day["present_half"], 0.5)
		self.assertEqual(day["absent_half"], 0.5)
		self.assertEqual(day["paid_flag"], 0.5)

	def test_other_half_present_reads_the_same(self):
		day = _day("Present")
		self.assertEqual(day["present_half"], 0.5)
		self.assertEqual(day["absent_half"], 0.5)

	def test_a_missing_half_day_status_reads_the_same(self):
		day = _day(None)
		self.assertEqual((day["present_half"], day["absent_half"]), (0.5, 0.5))

	def test_it_never_bills_a_whole_day(self):
		self.assertLess(_day("Absent")["absent_half"], 1.0)


class TestHalfDayWithLeave(TestCase):
	"""Leave claims one half; half_day_status still names the other."""

	def test_leave_plus_an_absent_other_half(self):
		day = _day("Absent", leave_type="Sick Leave")
		self.assertEqual(day["absent_half"], 0.5)
		self.assertEqual(day["present_half"], 0.0)

	def test_leave_plus_a_worked_other_half(self):
		day = _day("Present", leave_type="Sick Leave")
		self.assertEqual(day["present_half"], 0.5)
		self.assertEqual(day["absent_half"], 0.0)


class TestPenaltyStillSeparate(TestCase):
	def test_a_marked_penalty_day_never_reaches_the_absence_buckets(self):
		day = classify_attendance_day(
			status="Half Day",
			half_day_status="Absent",
			leave_type=None,
			working_hours=4.0,
			is_holiday=False,
			is_sandwich=False,
			leave_type_details={},
			pool_penalty="half",
		)
		self.assertEqual(day["penalty_half"], 0.5)
		self.assertEqual(day["absent_half"], 0.0)
