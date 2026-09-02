# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Wire effective-dated CIT into existing Nepal payroll structures."""

import frappe


def execute():
	if frappe.db.exists("Salary Component", "CIT"):
		frappe.db.set_value(
			"Salary Component",
			"CIT",
			{
				"formula": "cit_contribution",
				"amount_based_on_formula": 1,
				"exempted_from_income_tax": 1,
				"depends_on_payment_days": 0,
			},
			update_modified=False,
		)

	# Submitted structures keep a copy of the component formula. Update only the
	# CIT rows; historical submitted Salary Slips are separate child rows and are
	# intentionally untouched.
	frappe.db.sql(
		"""
		UPDATE `tabSalary Detail`
		SET formula = 'cit_contribution', amount_based_on_formula = 1
		WHERE parenttype = 'Salary Structure'
			AND salary_component = 'CIT'
			AND parent LIKE 'Nepal Payroll - %'
		"""
	)

	slabs = frappe.db.sql(
		"""
		SELECT DISTINCT ssa.income_tax_slab
		FROM `tabSalary Structure Assignment` ssa
		WHERE ssa.docstatus = 1
			AND ssa.salary_structure LIKE 'Nepal Payroll - %'
			AND COALESCE(ssa.income_tax_slab, '') != ''
		""",
		pluck=True,
	)
	for slab in slabs:
		frappe.db.set_value(
			"Income Tax Slab",
			slab,
			"allow_tax_exemption",
			1,
			update_modified=False,
		)

	frappe.clear_cache(doctype="Salary Component")
	frappe.clear_cache(doctype="Salary Structure")
