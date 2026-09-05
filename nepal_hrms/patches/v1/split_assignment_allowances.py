# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Move fixed miscellaneous pay into component-wise assignment allowances."""

import frappe
from frappe.utils import flt, now


def _variant(structure):
	for variant in ("Wages", "Salary"):
		if f" - {variant} - " in (structure or ""):
			return variant
	return None


def _append_allowance(assignment, component, amount):
	abbr = frappe.db.get_value("Salary Component", component, "salary_component_abbr")
	row = assignment.append(
		"custom_allowances",
		{
			"salary_component": component,
			"abbr": abbr,
			"amount": amount,
			"description": "Migrated from Employee Miscellaneous Allowance",
		},
	)
	row.db_insert()


def execute():
	assignments = frappe.get_all(
		"Salary Structure Assignment",
		filters={
			"docstatus": 1,
			"salary_structure": ["like", "Nepal Payroll - %"],
		},
		fields=["name", "employee", "salary_structure"],
		order_by="employee, from_date",
	)
	migrated_employees = set()

	for record in assignments:
		variant = _variant(record.salary_structure)
		if not variant:
			continue

		assignment = frappe.get_doc("Salary Structure Assignment", record.name)
		default_component = f"Other Allowance - {variant}"
		default_abbr = frappe.db.get_value(
			"Salary Component", default_component, "salary_component_abbr"
		)

		# Old base-derived assignments used the unmapped generic component.
		for row in assignment.custom_allowances:
			if row.salary_component == "Other Allowance":
				frappe.db.set_value(
					"Nepal Salary Allowance",
					row.name,
					{"salary_component": default_component, "abbr": default_abbr},
					update_modified=False,
				)
				row.salary_component = default_component
				row.abbr = default_abbr

		misc_amount = flt(
			frappe.db.get_value(
				"Employee", record.employee, "custom_miscellaneous_allowance"
			)
		)
		misc_component = f"Miscellaneous Allowance - {variant}"
		if misc_amount and frappe.db.exists("Salary Component", misc_component):
			existing = next(
				(row for row in assignment.custom_allowances if row.salary_component == misc_component),
				None,
			)
			if existing:
				frappe.db.set_value(
					"Nepal Salary Allowance",
					existing.name,
					"amount",
					flt(existing.amount) + misc_amount,
					update_modified=False,
				)
				existing.amount = flt(existing.amount) + misc_amount
			else:
				_append_allowance(assignment, misc_component, misc_amount)
			migrated_employees.add(record.employee)

		allowance_total = flt(sum(flt(row.amount) for row in assignment.custom_allowances), 2)
		fixed_total = flt(
			flt(assignment.custom_basic_salary)
			+ flt(assignment.custom_dearness_allowance)
			+ flt(assignment.custom_grade_amount)
			+ allowance_total,
			2,
		)
		frappe.db.set_value(
			"Salary Structure Assignment",
			assignment.name,
			{
				"base": fixed_total,
				"custom_total_allowances": allowance_total,
				"custom_total_fixed_remuneration": fixed_total,
			},
			update_modified=False,
		)

	for employee in migrated_employees:
		frappe.db.set_value(
			"Employee",
			employee,
			"custom_miscellaneous_allowance",
			0,
			update_modified=False,
		)

	# These generated rows are replaced at runtime by one earning per assignment
	# allowance. Existing Salary Slips remain untouched.
	frappe.db.sql(
		"""
		DELETE FROM `tabSalary Detail`
		WHERE parenttype = 'Salary Structure'
			AND parent LIKE 'Nepal Payroll - %'
			AND (
				salary_component LIKE 'Other Allowance - %%'
				OR salary_component LIKE 'Miscellaneous Allowance - %%'
			)
		"""
	)
	frappe.db.sql(
		"""
		UPDATE `tabSalary Structure`
		SET modified = %s
		WHERE name LIKE 'Nepal Payroll - %%'
		""",
		now(),
	)
	frappe.clear_cache(doctype="Salary Structure")
	frappe.clear_cache(doctype="Salary Structure Assignment")
