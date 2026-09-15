from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from frappe import _dict

from nepal_hrms.overrides.attendance_override import compute_hours_from_checkin_rows


class TestHoursFromCheckinRows(TestCase):
	def test_normal_plus_approved_ooo_counts_both_pairs(self):
		rows = [
			_dict(
				time=datetime(2026, 8, 24, 9, 29, 16),
				log_type="IN",
				shift="F - 10:00-17:30",
				custom_attendance_type="Normal",
				custom_is_approved=0,
				custom_ooo_rejected=0,
			),
			_dict(
				time=datetime(2026, 8, 24, 16, 4, 31),
				log_type="OUT",
				shift="F - 10:00-17:30",
				custom_attendance_type="Normal",
				custom_is_approved=0,
				custom_ooo_rejected=0,
			),
			_dict(
				time=datetime(2026, 8, 24, 16, 5, 4),
				log_type="IN",
				shift="F - 10:00-17:30",
				custom_attendance_type="OOO Work",
				custom_is_approved=1,
				custom_ooo_rejected=0,
			),
			_dict(
				time=datetime(2026, 8, 24, 17, 51, 43),
				log_type="OUT",
				shift="F - 10:00-17:30",
				custom_attendance_type="OOO Work",
				custom_is_approved=1,
				custom_ooo_rejected=0,
			),
		]

		with patch(
			"nepal_hrms.overrides.attendance_override._status_from_hours",
			return_value="Present",
		) as status_from_hours:
			computed = compute_hours_from_checkin_rows(rows, shift_name="F - 10:00-17:30")

		status_from_hours.assert_called_once()
		self.assertEqual(computed.total_hours, 8.37)
		self.assertEqual(computed.first_in, datetime(2026, 8, 24, 9, 29, 16))
		self.assertEqual(computed.last_out, datetime(2026, 8, 24, 17, 51, 43))
		self.assertTrue(computed.has_normal)
		self.assertTrue(computed.has_ooo)
		self.assertFalse(computed.has_unapproved_ooo)
		self.assertEqual(computed.status, "Present")

	def test_unapproved_ooo_is_excluded(self):
		rows = [
			_dict(
				time=datetime(2026, 8, 24, 9, 29, 16),
				log_type="IN",
				custom_attendance_type="Normal",
				custom_is_approved=0,
			),
			_dict(
				time=datetime(2026, 8, 24, 16, 4, 31),
				log_type="OUT",
				custom_attendance_type="Normal",
				custom_is_approved=0,
			),
			_dict(
				time=datetime(2026, 8, 24, 16, 5, 4),
				log_type="IN",
				custom_attendance_type="OOO Work",
				custom_is_approved=0,
				custom_ooo_rejected=0,
			),
			_dict(
				time=datetime(2026, 8, 24, 17, 51, 43),
				log_type="OUT",
				custom_attendance_type="OOO Work",
				custom_is_approved=0,
				custom_ooo_rejected=0,
			),
		]

		with patch(
			"nepal_hrms.overrides.attendance_override._status_from_hours",
			return_value="Half Day",
		):
			computed = compute_hours_from_checkin_rows(rows)

		self.assertEqual(computed.total_hours, 6.59)
		self.assertEqual(computed.last_out, datetime(2026, 8, 24, 16, 4, 31))
		self.assertTrue(computed.has_unapproved_ooo)
