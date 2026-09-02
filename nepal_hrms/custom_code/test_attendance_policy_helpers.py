from datetime import datetime
from unittest import TestCase

from frappe import _dict

from nepal_hrms.custom_code.attendance_policy import (
	max_out_in_gap_mins,
	ooo_required_from_checkins,
)


class TestAttendancePolicyHelpers(TestCase):
	def test_max_out_in_gap_uses_next_in_pair(self):
		checkins = [
			_dict(log_type="IN", time=datetime(2026, 8, 1, 9, 0)),
			_dict(log_type="OUT", time=datetime(2026, 8, 1, 11, 0)),
			_dict(log_type="IN", time=datetime(2026, 8, 1, 11, 20)),
			_dict(log_type="OUT", time=datetime(2026, 8, 1, 13, 0)),
			_dict(log_type="IN", time=datetime(2026, 8, 1, 14, 5)),
		]

		self.assertEqual(max_out_in_gap_mins(checkins), 65)
		self.assertTrue(ooo_required_from_checkins(checkins, grace_mins=60))
		self.assertFalse(ooo_required_from_checkins(checkins, grace_mins=65))

	def test_unpaired_and_empty_logs_do_not_create_gap(self):
		checkins = [
			{"log_type": "IN", "time": datetime(2026, 8, 1, 9, 0)},
			{"log_type": "OUT", "time": datetime(2026, 8, 1, 17, 0)},
		]

		self.assertEqual(max_out_in_gap_mins(checkins), 0)
		self.assertEqual(max_out_in_gap_mins([]), 0)
