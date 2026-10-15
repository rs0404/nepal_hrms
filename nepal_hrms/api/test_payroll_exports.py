from io import BytesIO
from unittest import TestCase

from frappe import _dict
from openpyxl import load_workbook

from nepal_hrms.api.payroll_exports import (
	BANK_FIRST_ROW,
	_bank_xlsx,
	amounts_by_root,
	bank_code_for,
	bank_rows,
	component_amounts,
	component_root,
	normalize_bank_name,
	offset_roots,
)


def detail(parent, parentfield, component, amount):
	return _dict(parent=parent, parentfield=parentfield, salary_component=component, amount=amount)


def slip(name, account="0010017501", bank="Nabil Bank", employee="EMP-1", employee_name="A Person"):
	return _dict(
		name=name, bank_account_no=account, bank_name=bank,
		employee=employee, employee_name=employee_name,
	)


CODES = {normalize_bank_name("Nabil Bank Limited"): "0401"}


class TestComponentGrouping(TestCase):
	def test_variants_share_a_root(self):
		self.assertEqual(component_root("Festival Allowance - Wages"), "Festival Allowance")
		self.assertEqual(component_root("Festival Allowance - Salary"), "Festival Allowance")
		self.assertEqual(component_root("CIT"), "CIT")
		self.assertEqual(
			component_root("Employer's Contribution SSF Deduction"),
			"Employer's Contribution SSF Deduction",
		)

	def test_component_amounts_sum_variants_per_slip_and_round_once(self):
		amounts = component_amounts(
			[
				detail("S1", "earnings", "Festival Allowance - Salary", 100.004),
				detail("S1", "earnings", "Festival Allowance - Wages", 0.004),
				detail("S1", "deductions", "CIT", 50),
			]
		)
		self.assertEqual(amounts, {("S1", "Festival Allowance"): 100.01})

	def test_employer_ssf_counts_the_earning_not_its_offsetting_deduction(self):
		details = [
			detail("S1", "earnings", "Employer's Contribution SSF - Salary", 2000),
			detail("S1", "deductions", "Employer's Contribution SSF Deduction", 2000),
		]
		self.assertEqual(amounts_by_root(details, "Employer's Contribution SSF"), {"S1": 2000})


class TestOffsetRoots(TestCase):
	def test_employer_contribution_deducted_back_is_offset(self):
		details = [
			detail("S1", "earnings", "Employer's Contribution SSF - Wages", 2000),
			detail("S1", "deductions", "Employer's Contribution SSF Deduction", 2000),
			detail("S1", "earnings", "Festival Allowance - Wages", 5000),
			detail("S1", "deductions", "CIT", 500),
		]
		self.assertEqual(offset_roots(details), {"Employer's Contribution SSF"})


class TestBankCodes(TestCase):
	def test_name_variants_find_the_same_bank(self):
		for name in ("Nabil Bank", "Nabil Bank Limited", "NABIL BANK LTD.", " nabil  bank "):
			self.assertEqual(bank_code_for(name, CODES), "0401", name)

	def test_unknown_bank_has_no_code(self):
		self.assertEqual(bank_code_for("Some Other Bank", CODES), "")
		self.assertEqual(bank_code_for(None, CODES), "")


class TestBankRows(TestCase):
	def test_row_layout_matches_the_template_columns(self):
		rows, problems = bank_rows([slip("S1")], {"S1": 1234.567}, CODES, "Salary Ashwin 2083")
		self.assertEqual(problems, [])
		self.assertEqual(rows, [[1234.57, "0401", "0010017501", "A Person", "Salary Ashwin 2083", "EMP-1"]])

	def test_remarks_are_cut_to_the_bank_limit(self):
		rows, _ = bank_rows([slip("S1")], {"S1": 1}, CODES, "Festival Allowance + Bonus Ashwin 2083")
		self.assertEqual(len(rows[0][4]), 30)

	def test_nothing_to_pay_and_cash_paid_are_left_out(self):
		rows, problems = bank_rows(
			[slip("S1"), slip("S2", account="")], {"S1": 0, "S2": 500}, CODES, "Salary"
		)
		self.assertEqual((rows, problems), ([], []))

	def test_missing_bank_code_and_negative_amount_are_reported(self):
		rows, problems = bank_rows(
			[slip("S1", bank="Unknown Bank"), slip("S2")], {"S1": 10, "S2": -5}, CODES, "Salary"
		)
		self.assertEqual(rows, [])
		self.assertEqual([p[0].name for p in problems], ["S1", "S2"])


class TestBankWorkbook(TestCase):
	def test_rows_land_under_the_template_headers_as_text(self):
		content = _bank_xlsx([[1234.5, "0401", "0010017501", "A Person", "Salary", "EMP-1"]])
		ws = load_workbook(BytesIO(content)).active
		self.assertEqual(ws.title, "CIPS BULK TRANSFER")
		self.assertEqual(ws.cell(row=4, column=1).value, "Transaction Amount (*)")
		row = [ws.cell(row=BANK_FIRST_ROW, column=c).value for c in range(1, 7)]
		self.assertEqual(row, [1234.5, "0401", "0010017501", "A Person", "Salary", "EMP-1"])
		self.assertEqual(ws.cell(row=BANK_FIRST_ROW, column=2).number_format, "@")
		self.assertEqual(ws.cell(row=BANK_FIRST_ROW, column=1).number_format, "#,##0.00")
