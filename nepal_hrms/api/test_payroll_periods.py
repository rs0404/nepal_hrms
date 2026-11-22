"""The PWA's payroll period filter gets dates even when Employee only has select."""

from unittest import TestCase
from unittest.mock import patch

from nepal_hrms.api.payroll_periods import get_my_payroll_periods

MODULE = "nepal_hrms.api.payroll_periods.frappe"


class TestGetMyPayrollPeriods(TestCase):
	def test_returns_the_employees_company_periods_with_dates(self):
		with patch(f"{MODULE}.db.get_value", return_value="Test Co"), patch(
			f"{MODULE}.get_all", return_value=["period"]
		) as get_all:
			self.assertEqual(get_my_payroll_periods(), ["period"])

		get_all.assert_called_once_with(
			"Payroll Period",
			filters={"company": "Test Co"},
			fields=["name", "start_date", "end_date"],
			order_by="start_date desc",
		)

	def test_a_user_without_an_active_employee_gets_nothing(self):
		with patch(f"{MODULE}.db.get_value", return_value=None), patch(
			f"{MODULE}.get_all"
		) as get_all:
			self.assertEqual(get_my_payroll_periods(), [])
		get_all.assert_not_called()
