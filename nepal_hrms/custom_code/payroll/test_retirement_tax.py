from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from nepal_hrms.custom_code.payroll.retirement_tax import (
	_future_contributions,
	_sum_rows,
	apply_retirement_cap_to_taxable_earnings,
	calculate_retirement_cap,
)


class TestRetirementTax(FrappeTestCase):
	def test_actual_contribution_is_lowest(self):
		result = calculate_retirement_cap(100_000, 900_000)
		self.assertEqual(result.allowed_deduction, 100_000)

	def test_one_third_limit_is_lowest(self):
		result = calculate_retirement_cap(400_000, 900_000)
		self.assertEqual(result.allowed_deduction, 300_000)

	def test_annual_limit_is_lowest(self):
		result = calculate_retirement_cap(700_000, 3_000_000)
		self.assertEqual(result.allowed_deduction, 500_000)

	def test_combines_only_retirement_deductions(self):
		rows = [
			frappe._dict(salary_component="Employee's Contribution SSF", amount=11_000),
			frappe._dict(salary_component="Employer's Contribution SSF Deduction", amount=20_000),
			frappe._dict(salary_component="CIT", amount=5_000),
			# The matching employer earning must not be counted again.
			frappe._dict(salary_component="Employer's Contribution SSF", amount=20_000),
			frappe._dict(salary_component="Insurance", amount=2_000),
		]
		self.assertEqual(_sum_rows(rows), 36_000)

	@patch("nepal_hrms.custom_code.payroll.retirement_tax.get_cit_contribution")
	def test_future_cit_changes_are_projected_by_effective_period(self, get_cit):
		get_cit.side_effect = [
			frappe._dict(monthly_amount=5_000),
			frappe._dict(monthly_amount=8_000),
		]
		doc = frappe._dict(
			employee="EMP-1",
			start_date="2026-07-17",
			remaining_sub_periods=3,
			_salary_structure_doc=frappe._dict(
				deductions=[
					frappe._dict(
						salary_component="CIT",
						amount_based_on_formula=1,
						formula="cit_contribution",
						amount=0,
					)
				]
			),
		)

		self.assertEqual(_future_contributions(doc), 13_000)

	@patch("nepal_hrms.custom_code.payroll.retirement_tax.build_retirement_projection")
	def test_uncapped_stock_exemption_is_replaced(self, build_projection):
		build_projection.return_value = frappe._dict(
			previous_contributions=100_000,
			current_contributions=40_000,
			allowed_deduction=300_000,
		)
		doc = frappe._dict(
			tax_slab=frappe._dict(allow_tax_exemption=1),
			remaining_sub_periods=6,
			total_taxable_earnings=800_000,
			total_taxable_earnings_without_full_tax_addl_components=800_000,
		)

		result = apply_retirement_cap_to_taxable_earnings(doc)

		# HRMS had subtracted 100,000 + 40,000 * 6 = 340,000. Only 300,000
		# is allowed, so taxable earnings increase by the 40,000 excess.
		self.assertEqual(result.taxable_correction, 40_000)
		self.assertEqual(doc.total_taxable_earnings, 840_000)
