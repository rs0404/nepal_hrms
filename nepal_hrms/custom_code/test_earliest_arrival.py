"""Lateness is measured from the day's first punch, not the paired one."""

from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.custom_code.attendance_policy import earliest_arrival


def _att(in_time=datetime(2026, 8, 31, 15, 24)):
	return frappe._dict(
		employee="EMP-001", attendance_date="2026-08-31", in_time=in_time
	)


class TestEarliestArrival(TestCase):
	def _resolve(self, first_in, doc=None):
		with patch(
			"nepal_hrms.overrides.attendance_override.compute_day_hours_from_checkins",
			return_value=frappe._dict(first_in=first_in),
		):
			return earliest_arrival(doc or _att())

	def test_the_morning_punch_wins_over_the_paired_one(self):
		"""IN 10:05, IN 15:24, OUT 17:30 -- HRMS stores 15:24, the arrival was 10:05."""
		self.assertEqual(
			self._resolve(datetime(2026, 8, 31, 10, 5, 29)),
			datetime(2026, 8, 31, 10, 5, 29),
		)

	def test_a_stored_time_earlier_than_any_punch_is_kept(self):
		"""Never move the arrival later; that would invent lateness."""
		doc = _att(in_time=datetime(2026, 8, 31, 9, 0))
		self.assertEqual(
			self._resolve(datetime(2026, 8, 31, 10, 5), doc),
			datetime(2026, 8, 31, 9, 0),
		)

	def test_no_punches_falls_back_to_the_stored_time(self):
		self.assertEqual(self._resolve(None), datetime(2026, 8, 31, 15, 24))

	def test_an_incomplete_row_is_left_alone(self):
		doc = frappe._dict(employee=None, attendance_date=None, in_time=None)
		self.assertIsNone(earliest_arrival(doc))

	def test_a_checkin_lookup_failure_falls_back(self):
		with patch(
			"nepal_hrms.overrides.attendance_override.compute_day_hours_from_checkins",
			side_effect=Exception("no table"),
		):
			self.assertEqual(earliest_arrival(_att()), datetime(2026, 8, 31, 15, 24))
