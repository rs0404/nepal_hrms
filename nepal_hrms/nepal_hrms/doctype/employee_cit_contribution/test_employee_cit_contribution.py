from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from nepal_hrms.custom_code.payroll.retirement_tax import get_cit_contribution


class TestEmployeeCITContribution(FrappeTestCase):
	def setUp(self):
		self.employee = "EMP-CIT-TEST"
		self.employee_details = frappe._dict(
			employee_name="CIT Test Employee",
			department=None,
			company="_Test Company",
			date_of_joining="2025-01-01",
			relieving_date=None,
		)

	def _new_contribution(self, effective_from, amount):
		return frappe.get_doc(
			{
				"doctype": "Employee CIT Contribution",
				"employee": self.employee,
				"effective_from": effective_from,
				"monthly_amount": amount,
			}
		)

	def test_employee_details_and_negative_amount_validation(self):
		doc = self._new_contribution("2026-07-17", -1)
		with patch("frappe.db.get_value", return_value=self.employee_details):
			with self.assertRaises(frappe.ValidationError):
				doc.validate()

	def test_effective_date_cannot_precede_joining(self):
		doc = self._new_contribution("2024-12-31", 5000)
		with patch("frappe.db.get_value", return_value=self.employee_details):
			with self.assertRaises(frappe.ValidationError):
				doc.validate()

	@patch("frappe.db.table_exists", return_value=True)
	@patch("frappe.db.get_value")
	def test_latest_effective_election_and_zero_stop(self, get_value, _table_exists):
		get_value.side_effect = [
			frappe._dict(name="CIT-1", effective_from="2026-07-17", monthly_amount=5000),
			frappe._dict(name="CIT-2", effective_from="2026-09-17", monthly_amount=0),
		]

		active = get_cit_contribution(self.employee, "2026-08-17")
		stopped = get_cit_contribution(self.employee, "2026-09-17")

		self.assertEqual(active.name, "CIT-1")
		self.assertEqual(active.monthly_amount, 5000)
		self.assertEqual(stopped.name, "CIT-2")
		self.assertEqual(stopped.monthly_amount, 0)
