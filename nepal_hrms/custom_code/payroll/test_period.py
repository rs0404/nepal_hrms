# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Payroll period naming and date->window resolution.

Every case passes `settings` explicitly, so none of this touches Nepal HRMS
Settings or the database.

Dates are BS 2083, whose Shrawan (month 4) runs 2026-07-17 to 2026-08-16 and
whose Bhadra (month 5) runs 2026-08-17 to 2026-09-16.
"""

from unittest import TestCase

from frappe.utils import add_days, getdate

from nepal_hrms.custom_code.payroll.period import (
	bs_month_of,
	period_containing,
	previous_period,
	resolve_bs_period,
)

CUSTOM_29 = {"payroll_period_basis": "Custom Day Range", "payroll_period_start_day": 29}
CUSTOM_1 = {"payroll_period_basis": "Custom Day Range", "payroll_period_start_day": 1}
NEPALI_MONTH = {"payroll_period_basis": "Nepali Month"}


class TestResolveBsPeriod(TestCase):
	def test_custom_range_names_a_period_by_the_month_it_ends_in(self):
		"""Bhadra's salary is Shrawan 29 - Bhadra 28, not Bhadra 29 - Ashwin 28.

		This is the convention the Monthly Attendance Sheet BS custom-period filter
		has always defaulted to; anchoring on the opening month instead put the
		report and the PWA a whole period apart.
		"""
		start, end, days = resolve_bs_period(2083, 5, CUSTOM_29)
		self.assertEqual(start, getdate("2026-08-14"))  # Shrawan 29
		self.assertEqual(end, getdate("2026-09-13"))  # Bhadra 28
		self.assertEqual(days, 31)

	def test_consecutive_periods_abut_without_gap_or_overlap(self):
		_s1, e1, _d1 = resolve_bs_period(2083, 5, CUSTOM_29)
		s2, _e2, _d2 = resolve_bs_period(2083, 6, CUSTOM_29)
		self.assertEqual((s2 - e1).days, 1)

	def test_custom_range_crosses_the_year_boundary(self):
		"""Baisakh (month 1) opens in Chaitra of the previous year."""
		start, end, days = resolve_bs_period(2083, 1, CUSTOM_29)
		self.assertTrue(start < end)
		self.assertEqual(days, (end - start).days + 1)

	def test_nepali_month_basis_is_the_whole_month(self):
		start, end, days = resolve_bs_period(2083, 5, NEPALI_MONTH)
		self.assertEqual(start, getdate("2026-08-17"))
		self.assertEqual(end, getdate("2026-09-16"))
		self.assertEqual(days, 31)

	def test_custom_range_starting_on_day_1_is_the_whole_month(self):
		"""Day 1 *is* the Nepali month; naming it by the previous month would be wrong."""
		self.assertEqual(
			resolve_bs_period(2083, 5, CUSTOM_1),
			resolve_bs_period(2083, 5, NEPALI_MONTH),
		)

	def test_period_is_named_by_the_bs_month_of_its_end_date(self):
		"""The invariant the PWA calendar pages on.

		get_attendance_period_summary derives the naming month from the window's end
		date and the client steps that month to reach the neighbouring period, so a
		period whose end fell in some other month would make paging skip or repeat.
		"""
		for basis in (CUSTOM_29, CUSTOM_1, NEPALI_MONTH):
			for month in range(1, 13):
				_start, end, _days = resolve_bs_period(2083, month, basis)
				self.assertEqual(
					bs_month_of(end),
					(2083, month),
					f"month {month} under {basis['payroll_period_basis']} is misnamed",
				)

	def test_unknown_bs_year_returns_empty(self):
		self.assertEqual(resolve_bs_period(1900, 5, CUSTOM_29), (None, None, 0))

	def test_first_supported_baisakh_degrades_instead_of_throwing(self):
		"""Its previous month is off the end of the BS table; the report must not blank."""
		self.assertEqual(resolve_bs_period(2000, 1, CUSTOM_29), (None, None, 0))


class TestPeriodContaining(TestCase):
	"""A date's window must not depend on how periods are named.

	Attendance policy pools, scheduled payroll and salary slips all resolve by
	date, so these windows are what keeps the naming change from restating pay.
	"""

	def test_date_before_the_start_day_belongs_to_the_period_ending_this_month(self):
		# Bhadra 28
		self.assertEqual(
			period_containing(getdate("2026-09-13"), CUSTOM_29)[:2],
			(getdate("2026-08-14"), getdate("2026-09-13")),
		)

	def test_the_start_day_itself_opens_the_next_period(self):
		# Bhadra 29
		self.assertEqual(
			period_containing(getdate("2026-09-14"), CUSTOM_29)[:2],
			(getdate("2026-09-14"), getdate("2026-10-14")),
		)

	def test_date_after_the_start_day_stays_in_the_open_period(self):
		# Ashwin 2
		self.assertEqual(
			period_containing(getdate("2026-09-18"), CUSTOM_29)[:2],
			(getdate("2026-09-14"), getdate("2026-10-14")),
		)

	def test_every_day_of_a_period_resolves_to_that_same_period(self):
		start, end, _days = resolve_bs_period(2083, 5, CUSTOM_29)
		day = start
		while day <= end:
			self.assertEqual(
				period_containing(day, CUSTOM_29)[:2],
				(start, end),
				f"{day} resolved outside the period it belongs to",
			)
			day = add_days(day, 1)

	def test_nepali_month_basis_is_unaffected(self):
		self.assertEqual(
			period_containing(getdate("2026-09-18"), NEPALI_MONTH)[:2],
			(getdate("2026-09-17"), getdate("2026-10-17")),
		)

	def test_previous_period_ends_the_day_before_the_current_one_opens(self):
		start, _end, _days = period_containing(getdate("2026-09-18"), CUSTOM_29)
		_pstart, pend, _pdays = previous_period(getdate("2026-09-18"), CUSTOM_29)
		self.assertEqual((start - pend).days, 1)


class TestReportCustomPeriodParity(TestCase):
	"""The whole point of the change.

	The report's "Use Custom Calculation Period" defaults are start day 29 /
	Previous Month, end day 28 / Current Month. resolve_bs_period must agree, or
	picking Bhadra in the report and Bhadra in the PWA means different days.
	"""

	def test_resolve_matches_the_reports_manual_custom_period_defaults(self):
		from nepal_hrms.nepal_hrms.report.monthly_attendance_sheet_bs.monthly_attendance_sheet_bs import (
			get_bs_date_with_offset,
		)

		manual_start = getdate(get_bs_date_with_offset(2083, 5, 29, -1))
		manual_end = getdate(get_bs_date_with_offset(2083, 5, 28, 0))
		start, end, _days = resolve_bs_period(2083, 5, CUSTOM_29)
		self.assertEqual((start, end), (manual_start, manual_end))
