from datetime import date
from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from nepal_hrms.custom_code.payroll.bs_period import (
	cycle_start_day,
	effective_start_date,
	extension_enabled,
	previous_bs_month_tail_start,
	year_opening_bs_month,
)


def _slip(start, end, company="Yarsa Tech Pvt. Ltd."):
	return frappe._dict(start_date=start, end_date=end, company=company)


class TestCycleStartDay(TestCase):
	"""The cycle's first day is read off the period's end, never assumed."""

	def test_period_ending_on_day_28_opens_on_29(self):
		# 2026-08-13 is BS 2083-04-28.
		self.assertEqual(cycle_start_day("2026-08-13"), 29)

	def test_period_ending_on_the_bs_month_end_has_no_leading_days(self):
		# 2026-07-16 is BS 2083-03-32, the last day of Ashadh.
		self.assertIsNone(cycle_start_day("2026-07-16"))

	def test_a_period_ending_on_day_25_opens_on_26(self):
		with patch("nepal_hrms.custom_code.payroll.bs_period.nepali_date") as nd:
			nd.ad_to_bs.return_value = {"year": 2083, "month": 4, "day": 25}
			nd.days_in_bs_month.return_value = 31
			self.assertEqual(cycle_start_day("2026-08-10"), 26)


class TestYearOpeningMonth(TestCase):
	def test_taken_from_the_payroll_period_covering_the_slip(self):
		"""Payroll Period 2083/84 starts 2026-07-17, which is BS month 4."""
		self.assertEqual(year_opening_bs_month(_slip("2026-07-17", "2026-08-13")), 4)

	def test_falls_back_to_fiscal_year_when_no_payroll_period_matches(self):
		with patch(
			"nepal_hrms.custom_code.payroll.bs_period.frappe.get_all"
		) as get_all:
			get_all.side_effect = [[], [], [frappe._dict(start_date=date(2026, 7, 17))]]
			self.assertEqual(year_opening_bs_month(_slip("2026-07-17", "2026-08-13")), 4)

	def test_no_record_means_no_opinion(self):
		with patch(
			"nepal_hrms.custom_code.payroll.bs_period.frappe.get_all", return_value=[]
		):
			self.assertIsNone(year_opening_bs_month(_slip("2026-07-17", "2026-08-13")))


class TestPreviousBsMonthTail(TestCase):
	def test_year_opening_period_extends_to_the_cycle_start(self):
		"""BS 2083-04-01 to 04-28 really begins on 2083-03-29 = 2026-07-13."""
		self.assertEqual(
			previous_bs_month_tail_start(_slip("2026-07-17", "2026-08-13")),
			date(2026, 7, 13),
		)

	def test_a_later_period_in_the_year_is_left_alone(self):
		"""BS 2083-05-01 to 05-28: its leading days belong to the slip before it."""
		self.assertIsNone(
			previous_bs_month_tail_start(_slip("2026-08-17", "2026-09-13"))
		)

	def test_a_period_already_entered_as_the_full_cycle_is_left_alone(self):
		self.assertIsNone(
			previous_bs_month_tail_start(_slip("2026-07-13", "2026-08-13"))
		)

	def test_month_aligned_cycle_has_nothing_to_extend(self):
		with patch(
			"nepal_hrms.custom_code.payroll.bs_period.cycle_start_day", return_value=None
		):
			self.assertIsNone(
				previous_bs_month_tail_start(_slip("2026-07-17", "2026-08-13"))
			)

	def test_previous_month_too_short_for_the_cycle_day(self):
		with patch("nepal_hrms.custom_code.payroll.bs_period.nepali_date") as nd, patch(
			"nepal_hrms.custom_code.payroll.bs_period.cycle_start_day", return_value=29
		), patch(
			"nepal_hrms.custom_code.payroll.bs_period.year_opening_bs_month",
			return_value=4,
		):
			nd.ad_to_bs.return_value = {"year": 2083, "month": 4, "day": 1}
			nd.days_in_bs_month.return_value = 28
			self.assertIsNone(
				previous_bs_month_tail_start(_slip("2026-07-17", "2026-08-13"))
			)

	def test_opening_month_one_walks_back_a_bs_year(self):
		with patch("nepal_hrms.custom_code.payroll.bs_period.nepali_date") as nd, patch(
			"nepal_hrms.custom_code.payroll.bs_period.cycle_start_day", return_value=29
		), patch(
			"nepal_hrms.custom_code.payroll.bs_period.year_opening_bs_month",
			return_value=1,
		):
			nd.ad_to_bs.return_value = {"year": 2084, "month": 1, "day": 1}
			nd.days_in_bs_month.return_value = 30
			nd.bs_to_ad.return_value = date(2027, 4, 9)
			previous_bs_month_tail_start(_slip("2027-04-14", "2027-05-11"))
			nd.bs_to_ad.assert_called_once_with(2083, 12, 29)

	def test_calendar_gap_is_left_alone(self):
		with patch("nepal_hrms.custom_code.payroll.bs_period.nepali_date") as nd, patch(
			"nepal_hrms.custom_code.payroll.bs_period.cycle_start_day", return_value=29
		), patch(
			"nepal_hrms.custom_code.payroll.bs_period.year_opening_bs_month",
			return_value=4,
		):
			nd.ad_to_bs.return_value = {"year": 2083, "month": 4, "day": 1}
			nd.days_in_bs_month.side_effect = ValueError("outside calendar")
			self.assertIsNone(
				previous_bs_month_tail_start(_slip("2026-07-17", "2026-08-13"))
			)


class TestExtensionFlag(TestCase):
	def test_setting_alone_decides(self):
		with patch(
			"nepal_hrms.custom_code.payroll.bs_period._settings_default", return_value=1
		):
			self.assertTrue(extension_enabled())
		with patch(
			"nepal_hrms.custom_code.payroll.bs_period._settings_default", return_value=0
		):
			self.assertFalse(extension_enabled())

	def test_disabled_keeps_the_entered_start_date(self):
		with patch(
			"nepal_hrms.custom_code.payroll.bs_period._settings_default", return_value=0
		):
			self.assertEqual(
				effective_start_date(_slip("2026-07-17", "2026-08-13")),
				date(2026, 7, 17),
			)

	def test_enabled_moves_the_opening_period_back(self):
		with patch(
			"nepal_hrms.custom_code.payroll.bs_period._settings_default", return_value=1
		):
			self.assertEqual(
				effective_start_date(_slip("2026-07-17", "2026-08-13")),
				date(2026, 7, 13),
			)

	def test_enabled_leaves_a_later_period_where_it_is(self):
		with patch(
			"nepal_hrms.custom_code.payroll.bs_period._settings_default", return_value=1
		):
			self.assertEqual(
				effective_start_date(_slip("2026-08-17", "2026-09-13")),
				date(2026, 8, 17),
			)
