from io import BytesIO
from unittest import TestCase

import frappe

from nepal_hrms.api.payroll_workbook import REF, Grid, Row, build_payroll_workbook


class TestGrid(TestCase):
	def test_columns_follow_group_order_not_discovery_order(self):
		grid = Grid()
		row = Row(grid)
		row.formula("tot:net", "tot", "Net Pay", "[[earn:Basic]]")
		row.formula("earn:Basic", "earn", "Basic", "[[in:basic]]")
		row.input("in:basic", "in", "basic", 1000)
		self.assertEqual(grid.ordered(), ["in:basic", "earn:Basic", "tot:net"])
		self.assertEqual(row.cells["tot:net"], "=[[earn:Basic]]")
		self.assertEqual(row.cells["in:basic"], 1000)

	def test_an_input_keeps_its_first_value(self):
		row = Row(Grid())
		row.input("days:payment_days", "days", "Payment Days", 30, "days")
		row.input("days:payment_days", "days", "Payment Days", 0, "days")
		self.assertEqual(row.cells["days:payment_days"], 30)

	def test_references_are_placeholders(self):
		self.assertEqual(REF.findall("ROUND([[fix:Basic]]*[[es:ratio]],2)"), ["fix:Basic", "es:ratio"])


class TestBuildOnSite(TestCase):
	"""Needs a site with a Payroll Entry that has salary slips."""

	def test_payroll_sheet_is_formulas_over_inputs(self):
		from openpyxl import load_workbook

		pe_name = frappe.db.sql(
			"""select payroll_entry from `tabSalary Slip`
			where docstatus < 2 and ifnull(payroll_entry, '') != '' limit 1"""
		)
		if not pe_name:
			self.skipTest("no Payroll Entry with salary slips on this site")
		pe = frappe.get_doc("Payroll Entry", pe_name[0][0])

		wb = load_workbook(BytesIO(build_payroll_workbook(pe, "test")))
		self.assertEqual(wb.sheetnames, ["Payroll", "Settings", "How to read"])
		ws = wb["Payroll"]
		heads = {ws.cell(row=6, column=c).value: c for c in range(1, ws.max_column + 1)}
		self.assertEqual(
			[ws.cell(row=6, column=c).value for c in range(1, 7)],
			["S.N.", "Employee ID", "Employee Name", "Branch", "Department", "Salary Structure"],
		)
		for header in ("Gross Pay", "Total Deductions", "Net Pay", "Net Pay Difference"):
			self.assertIn(header, heads)
			self.assertTrue(str(ws.cell(row=7, column=heads[header]).value).startswith("="), header)
		self.assertIsInstance(ws.cell(row=7, column=heads["ERP Net Pay"]).value, (int, float))
		self.assertTrue(wb.calculation.fullCalcOnLoad)
