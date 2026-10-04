"""A ticked Salary Component takes its amount from the assignment's table.

No formula and no naming rule: tick Use Amount from Salary Structure
Assignment, put the component on any structure, type the amount per employee.
"""

from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.custom_code.payroll import salary_breakdown
from nepal_hrms.overrides import salary_slip


def _row(component, amount):
	return frappe._dict(salary_component=component, amount=amount)


class TestAssignmentAmount(TestCase):
	def _amount(self, rows, component):
		with patch.object(salary_breakdown, "get_allowance_rows", return_value=rows):
			return salary_breakdown.get_assignment_amount("SSA-1", component)

	def test_sums_every_row_of_the_component(self):
		rows = [_row("Commission", 15000), _row("Transport", 3000), _row("Commission", 5000)]
		self.assertEqual(self._amount(rows, "Commission"), 20000)

	def test_component_missing_from_the_table_is_zero(self):
		self.assertEqual(self._amount([_row("Transport", 3000)], "Commission"), 0)

	def test_no_assignment_is_zero(self):
		self.assertEqual(salary_breakdown.get_assignment_amount(None, "Commission"), 0)


class TestEarningsOnlyRaiseBase(TestCase):
	def test_deduction_rows_are_left_out_of_the_total(self):
		doc = frappe._dict(custom_allowances=[_row("Commission", 20000), _row("Canteen", 1000)])
		types = {"Commission": "Earning", "Canteen": "Deduction"}
		with patch.object(salary_breakdown, "_component_type", side_effect=types.get):
			self.assertEqual(salary_breakdown._allowance_total(doc), 20000)


class TestStructureRow(TestCase):
	def test_row_carries_the_assignment_amount_and_no_formula(self):
		slip = salary_slip.CustomSalarySlip.__new__(salary_slip.CustomSalarySlip)
		slip._salary_structure_assignment = {"name": "SSA-1"}
		struct_row = frappe._dict(
			salary_component="Commission",
			abbr="commission",
			amount_based_on_formula=1,
			formula="base * 0.1",
			amount=0,
		)
		with patch.object(salary_breakdown, "get_assignment_amount", return_value=20000) as get:
			row = slip._row_with_assignment_amount(struct_row)

		get.assert_called_once_with("SSA-1", "Commission")
		self.assertEqual((row.amount, row.amount_based_on_formula, row.formula), (20000, 0, None))
		# The structure is cached and shared between slips: never write to it.
		self.assertEqual(
			(struct_row.amount, struct_row.amount_based_on_formula, struct_row.formula),
			(0, 1, "base * 0.1"),
		)

	def test_unticked_component_is_not_redirected(self):
		with patch.object(salary_slip, "_component_flag", return_value=0):
			self.assertFalse(salary_slip._amount_from_assignment("Commission"))
		with patch.object(salary_slip, "_component_flag", return_value=None):
			self.assertFalse(salary_slip._amount_from_assignment("Commission"))
