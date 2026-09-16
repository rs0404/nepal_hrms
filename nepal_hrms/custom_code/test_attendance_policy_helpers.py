from datetime import date, datetime
from unittest import TestCase

from frappe import _dict

from nepal_hrms.custom_code.attendance_policy import (
	assign_employee_pool_penalties,
	max_out_in_gap_mins,
	occurrence_is_penalty,
	ooo_required_from_checkins,
	split_occurrence_penalty,
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

	def test_occurrence_penalty_split_matches_payroll_units(self):
		regular = split_occurrence_penalty(3, 1, 2, 2)
		self.assertEqual((regular.half_days, regular.full_days), (2, 0))

		escalated = split_occurrence_penalty(
			6, 1, 2, 2, enable_full_day_escalation=1, full_day_after_occurrences=5
		)
		self.assertEqual((escalated.half_days, escalated.full_days), (1, 2))
		self.assertTrue(escalated.escalated)

	def test_third_pool_occurrence_is_half_day_penalty(self):
		self.assertFalse(occurrence_is_penalty(1, 2, 2))
		self.assertFalse(occurrence_is_penalty(2, 2, 2))
		self.assertTrue(occurrence_is_penalty(3, 2, 2))
		self.assertFalse(occurrence_is_penalty(4, 2, 2))
		self.assertFalse(occurrence_is_penalty(5, 2, 2))
		self.assertTrue(occurrence_is_penalty(6, 2, 2))

	def test_assign_pool_penalties_marks_third_day(self):
		settings = _dict(
			initial_grace_occurrences=2,
			subsequent_grace_step_occurrences=2,
			combine_late_and_early_pool=0,
			enable_late_full_day_escalation=0,
			late_full_day_after_occurrences=5,
		)
		assigned = assign_employee_pool_penalties(
			[
				(date(2026, 1, 1), 1, 0),
				(date(2026, 1, 2), 1, 0),
				(date(2026, 1, 3), 1, 0),
			],
			settings,
		)
		self.assertEqual(assigned, {date(2026, 1, 3): "half"})

	def test_assign_pool_penalties_escalates_to_full_day(self):
		settings = _dict(
			initial_grace_occurrences=2,
			subsequent_grace_step_occurrences=2,
			combine_late_and_early_pool=0,
			enable_late_full_day_escalation=1,
			late_full_day_after_occurrences=5,
		)
		flags = [(date(2026, 1, day), 1, 0) for day in range(1, 7)]
		assigned = assign_employee_pool_penalties(flags, settings)
		self.assertEqual(assigned[date(2026, 1, 3)], "full")
		self.assertEqual(assigned[date(2026, 1, 6)], "full")
		self.assertNotIn(date(2026, 1, 1), assigned)
