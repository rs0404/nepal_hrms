"""An IN with no OUT is an incomplete record, not evidence of absence."""

from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.overrides.attendance_override import compute_hours_from_checkin_rows


def _log(time, log_type, shift="B - 09:00-17:00"):
	return frappe._dict(
		time=time, log_type=log_type, shift=shift, custom_attendance_type="Normal"
	)


class TestUnpairedCheckin(TestCase):
	def _compute(self, rows):
		# Thresholds live on Shift Type; the pairing is what is under test.
		with patch(
			"nepal_hrms.overrides.attendance_override.frappe.db.get_value",
			return_value=(4.0, 6.0),
		):
			return compute_hours_from_checkin_rows(rows)

	def test_lone_in_punch_is_flagged_unpaired(self):
		"""Dipendra 2026-08-13: punched in at 14:49, never punched out."""
		computed = self._compute([_log("2026-08-13 14:49:56", "IN")])
		self.assertTrue(computed.unpaired_in)
		self.assertEqual(computed.total_hours, 0.0)
		self.assertEqual(computed.first_in.strftime("%H:%M"), "14:49")

	def test_a_complete_day_is_not_flagged(self):
		computed = self._compute(
			[_log("2026-08-12 09:05:00", "IN"), _log("2026-08-12 17:30:00", "OUT")]
		)
		self.assertFalse(computed.unpaired_in)
		self.assertEqual(computed.total_hours, 8.42)

	def test_a_trailing_in_after_a_complete_pair_is_flagged(self):
		computed = self._compute(
			[
				_log("2026-08-12 09:00:00", "IN"),
				_log("2026-08-12 13:00:00", "OUT"),
				_log("2026-08-12 14:00:00", "IN"),
			]
		)
		self.assertTrue(computed.unpaired_in)
		self.assertEqual(computed.total_hours, 4.0)

	def test_a_day_with_no_punches_is_not_flagged(self):
		computed = self._compute([])
		self.assertFalse(computed.unpaired_in)
		self.assertEqual(computed.total_hours, 0.0)
