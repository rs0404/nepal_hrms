"""The slip being made always counts as one remaining period.

The BS-month patch rounded the days left to the employee's last day into
months, so someone relieved early in the slip's month got 0: income tax
divided by it (ZeroDivisionError on HRMS before v15.62) and the year's
projection multiplied the current month by -1.
"""

from unittest import TestCase

import frappe

import hrms.payroll.doctype.payroll_period.payroll_period as pp

PERIOD = frappe._dict(start_date="2026-07-17", end_date="2027-07-16")


def _factor(frequency, relieving_date=None, start="2026-07-17", end="2026-08-16"):
	return pp.get_period_factor(
		"EMP-1", start, end, frequency, PERIOD, joining_date="2020-01-01", relieving_date=relieving_date
	)


class TestRemainingPeriods(TestCase):
	def test_the_patch_is_in_place(self):
		self.assertEqual(pp.get_period_factor.__name__, "patched_get_period_factor")

	def test_relieved_early_in_the_month_still_has_one(self):
		self.assertEqual(_factor("Monthly", "2026-07-25")[1], 1)

	def test_blank_frequency_relieved_early_still_has_one(self):
		self.assertEqual(_factor("", "2026-07-25", end="2026-08-13")[1], 1)

	def test_a_full_year_is_untouched(self):
		self.assertEqual(_factor("Monthly"), (12, 12))
