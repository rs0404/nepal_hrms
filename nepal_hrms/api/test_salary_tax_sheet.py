from unittest import TestCase

from frappe import _dict
from hrms.payroll.doctype.salary_slip.salary_slip import calculate_tax_by_tax_slab

from nepal_hrms.api.salary_tax_sheet import (
	amounts_by_slip,
	fiscal_months,
	np_number,
	ordered_roots,
	slab_breakdown,
)

SLABS = [  # Income Tax Slab 2083/84 as configured
	_dict(from_amount=1, to_amount=1000000, percent_deduction=0),
	_dict(from_amount=1000001, to_amount=1500000, percent_deduction=10),
	_dict(from_amount=1500001, to_amount=2500000, percent_deduction=20),
	_dict(from_amount=2500001, to_amount=4000001, percent_deduction=27),
	_dict(from_amount=4000001, to_amount=0, percent_deduction=2),
]


def detail(parent, parentfield, component, amount, idx, calc_only=0):
	return _dict(
		parent=parent, parentfield=parentfield, salary_component=component, amount=amount,
		idx=idx, do_not_include_in_total=calc_only,
	)


DETAILS = [
	detail("S1", "earnings", "Basic Salary - Salary", 40000, 1),
	detail("S1", "earnings", "Festival Allowance - Salary", 40000, 4),
	detail("S2", "earnings", "Basic Salary - Wages", 20000, 1),
	detail("S2", "earnings", "Grade - Wages", 500, 2),
	detail("S2", "earnings", "Festival Allowance - Wages", 20500, 3),
	detail("S1", "deductions", "TDS", 0, 2),
	detail("S1", "deductions", "Employee's Contribution SSF", 4400, 1),
	detail("S2", "deductions", "Leave and Late Deduction - Wages", 900, 3, calc_only=1),
]


class TestColumns(TestCase):
	def test_roots_follow_slip_order_across_variants(self):
		self.assertEqual(
			ordered_roots(DETAILS, "earnings"), ["Basic Salary", "Grade", "Festival Allowance"]
		)
		self.assertEqual(ordered_roots(DETAILS, "deductions"), ["Employee's Contribution SSF", "TDS"])

	def test_calculation_only_rows_get_their_own_columns(self):
		self.assertEqual(ordered_roots(DETAILS, "deductions", counted=False), ["Leave and Late Deduction"])
		self.assertEqual(
			amounts_by_slip(DETAILS, "deductions", counted=False),
			{("S2", "Leave and Late Deduction"): 900},
		)
		self.assertNotIn(("S2", "Leave and Late Deduction"), amounts_by_slip(DETAILS, "deductions"))


class TestSlabs(TestCase):
	def test_matches_hrms_tax_on_every_band(self):
		slab = _dict(slabs=SLABS, tax_relief_limit=0, other_taxes_and_charges=[], marginal_relief_limit=0)
		for income in (690134.56, 1000000, 1200000, 2114200, 3000000, 4500000):
			rows, total = slab_breakdown(income, SLABS)
			expected, _other = calculate_tax_by_tax_slab(income, slab, eval_locals={})
			self.assertAlmostEqual(total, expected, places=1, msg=income)
			self.assertEqual(len(rows), len(SLABS))

	def test_conditional_slab_is_listed_not_charged(self):
		rows, total = slab_breakdown(2000000, [_dict(from_amount=1, to_amount=0, percent_deduction=10, condition="married")])
		self.assertEqual(total, 0)
		self.assertEqual(rows[0][3], 0)


class TestFormatting(TestCase):
	def test_nepali_grouping(self):
		self.assertEqual(np_number(4000001), "40,00,001")
		self.assertEqual(np_number(12345678.4), "1,23,45,678")
		self.assertEqual(np_number(999), "999")

	def test_fiscal_year_starts_in_shrawan(self):
		months = fiscal_months("2026-07-17")
		self.assertEqual(months[:3], ["Shrawan", "Bhadra", "Ashwin"])
		self.assertEqual(months[-1], "Ashadh")


class TestOtherExemptions(TestCase):
	def test_itemised_lines_come_from_the_slip(self):
		from nepal_hrms.api.salary_tax_sheet import other_exemptions_of

		s = _dict(custom_tax_calculation_data='{"other_exemptions": [{"label": "Insurance", "amount": 24000, "note": "x"}]}')
		self.assertEqual([(l.label, l.amount) for l in other_exemptions_of(s, 60000)], [("Insurance", 24000)])

	def test_older_slips_get_one_total_that_still_adds_up(self):
		from nepal_hrms.api.salary_tax_sheet import other_exemptions_of

		s = _dict(
			custom_tax_calculation_data='{"annual_taxable_amount": 1}',
			deductions_before_tax_calculation=84000, tax_exemption_declaration=25000, standard_tax_exemption_amount=0,
		)
		self.assertEqual([(l.label, l.amount) for l in other_exemptions_of(s, 60000)], [("Other exemptions", 49000)])
		s.deductions_before_tax_calculation, s.tax_exemption_declaration = 60000, 0
		self.assertEqual(other_exemptions_of(s, 60000), [])
