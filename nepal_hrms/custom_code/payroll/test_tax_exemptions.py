from unittest import TestCase
from unittest.mock import patch

from frappe import _dict

from nepal_hrms.custom_code.payroll import tax_exemptions as te


class FakeSlip(_dict):
	def get_amount_from_formula(self, row, sub_period):
		return row.formula_amount


def slip(**kwargs):
	defaults = dict(
		employee="EMP-1", start_date="2026-09-14", remaining_sub_periods=10,
		payroll_period=_dict(name="2083/84", start_date="2026-07-17"),
		tax_slab=_dict(allow_tax_exemption=1, standard_tax_exemption_amount=0),
		deductions=[], _salary_structure_doc=_dict(deductions=[]),
		deductions_before_tax_calculation=0, tax_exemption_declaration=0, standard_tax_exemption_amount=0,
	)
	defaults.update(kwargs)
	return FakeSlip(defaults)


def row(component, amount, exempt=1, **kwargs):
	return _dict(salary_component=component, amount=amount, exempted_from_income_tax=exempt, **kwargs)


class TestExemptDeductions(TestCase):
	def test_insurance_projected_for_the_year_retirement_left_out(self):
		doc = slip(
			deductions=[row("Insurance", 2000), row("CIT", 10000), row("Advance Deduction", 5000, exempt=0)],
			_salary_structure_doc=_dict(deductions=[row("Insurance", 2000, amount_based_on_formula=0), row("CIT", 10000)]),
		)
		with patch.object(te, "_previous_exempt_deductions", return_value={"Insurance": 4000, "CIT": 20000}):
			lines = te.exempt_deduction_lines(doc)
		# 2 months paid + this month + 9 projected = 12 × 2,000
		self.assertEqual([(l["label"], l["amount"]) for l in lines], [("Insurance", 24000)])

	def test_formula_rows_use_the_formula_for_each_month_ahead(self):
		doc = slip(
			remaining_sub_periods=3,
			deductions=[row("Insurance", 1000)],
			_salary_structure_doc=_dict(deductions=[row("Insurance", 0, amount_based_on_formula=1, formula_amount=1500)]),
		)
		with patch.object(te, "_previous_exempt_deductions", return_value={}):
			self.assertEqual(te.exempt_deduction_lines(doc)[0]["amount"], 1000 + 1500 * 2)


class TestDeclarations(TestCase):
	def test_rows_are_capped_and_match_the_declared_total(self):
		parent = _dict(name="DEC-1", total_exemption_amount=45000)
		rows = [
			_dict(exemption_sub_category="Life Insurance Premium", amount=50000, max_amount=40000),
			_dict(exemption_sub_category="Health Insurance", amount=5000, max_amount=20000),
		]
		with patch.object(te.frappe.db, "get_value", return_value=parent), patch.object(
			te.frappe, "get_all", return_value=rows
		), patch.object(te.frappe, "get_meta", return_value=_dict(has_field=lambda f: True)):
			lines = te.declaration_lines(slip())
		self.assertEqual([(l["label"], l["amount"]) for l in lines], [("Life Insurance Premium", 40000), ("Health Insurance", 5000)])
		self.assertIn("limited to", lines[0]["note"])

	def test_no_exemptions_allowed_by_the_slab_means_none_listed(self):
		self.assertEqual(te.declaration_lines(slip(tax_slab=_dict(allow_tax_exemption=0))), [])


class TestReconciliation(TestCase):
	def test_lines_add_up_to_what_payroll_subtracted(self):
		doc = slip(deductions_before_tax_calculation=60000 + 24000, tax_exemption_declaration=25000, standard_tax_exemption_amount=0)
		with patch.object(te, "exempt_deduction_lines", return_value=[te._line("Insurance", 24000)]), patch.object(
			te, "declaration_lines", return_value=[te._line("Children's Education Fee", 20000)]
		):
			lines = te.other_exemption_lines(doc, allowed_retirement=60000)
		self.assertEqual(sum(l["amount"] for l in lines), 24000 + 25000)
		self.assertEqual(lines[-1]["label"], "Other exemptions")
		self.assertEqual(lines[-1]["amount"], 5000)

	def test_nothing_beyond_retirement_lists_nothing(self):
		doc = slip(deductions_before_tax_calculation=40902.33)
		with patch.object(te, "exempt_deduction_lines", return_value=[]), patch.object(te, "declaration_lines", return_value=[]):
			self.assertEqual(te.other_exemption_lines(doc, allowed_retirement=40902.33), [])
