from datetime import date
from unittest import TestCase
from unittest.mock import patch

from frappe import _dict

from nepal_hrms.overrides.salary_slip import count_sandwich_holiday_absents


class TestSalarySlipSandwichAbsents(TestCase):
    def setUp(self):
        self.holidays = [date(2026, 7, 25), date(2026, 7, 26)]
        self.rows = [
            _dict(attendance_date=date(2026, 7, 24), status="On Leave"),
            _dict(attendance_date=date(2026, 7, 25), status="Absent"),
            _dict(attendance_date=date(2026, 7, 26), status="Absent"),
            _dict(attendance_date=date(2026, 7, 27), status="On Leave"),
        ]

    @patch("nepal_hrms.custom_code.attendance_holiday.is_sandwiched", return_value=True)
    @patch("nepal_hrms.custom_code.attendance_holiday.sandwich_rule_enabled", return_value=True)
    def test_counts_sandwiched_holiday_absents(self, _enabled, _sandwiched):
        extra = count_sandwich_holiday_absents("HR-EMP-00013", self.rows, self.holidays)
        self.assertEqual(extra, 2)

    @patch("nepal_hrms.custom_code.attendance_holiday.sandwich_rule_enabled", return_value=False)
    def test_skips_when_sandwich_rule_disabled(self, _enabled):
        extra = count_sandwich_holiday_absents("HR-EMP-00013", self.rows, self.holidays)
        self.assertEqual(extra, 0)

    @patch("nepal_hrms.custom_code.attendance_holiday.is_sandwiched", return_value=True)
    @patch("nepal_hrms.custom_code.attendance_holiday.sandwich_rule_enabled", return_value=True)
    def test_skips_when_payroll_already_counts_holiday_attendance(self, _enabled, _sandwiched):
        extra = count_sandwich_holiday_absents(
            "HR-EMP-00013",
            self.rows,
            self.holidays,
            already_counting_holiday_attendance=True,
        )
        self.assertEqual(extra, 0)

    @patch("nepal_hrms.custom_code.attendance_holiday.is_sandwiched", return_value=False)
    @patch("nepal_hrms.custom_code.attendance_holiday.sandwich_rule_enabled", return_value=True)
    def test_ignores_holiday_absent_that_is_not_sandwiched(self, _enabled, _sandwiched):
        extra = count_sandwich_holiday_absents("HR-EMP-00013", self.rows, self.holidays)
        self.assertEqual(extra, 0)
