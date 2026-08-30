# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Move employee salary onto the Salary Structure Assignment breakdown.

Salary used to live on Employee (`revised_salary` / `ctc`) with the earnings
formulas reading it directly, while deduction rates read `SSA.base`. Nothing kept
the two in sync, so assignments with base = 0 produced zero absence/LWP/late
deductions. This backfills the Nepal breakdown on every submitted assignment and
brings `base` in line with it.

Idempotent: assignments that already carry a breakdown are skipped.
"""

import frappe
from frappe.utils import flt

OTHER_ALLOWANCE_COMPONENT = "Other Allowance"


def execute():
	if not frappe.db.has_column("Salary Structure Assignment", "custom_basic_salary"):
		# after_migrate creates the custom fields; nothing to do on this pass.
		frappe.log_error(
			"custom_basic_salary missing; skipping salary breakdown migration",
			"Nepal HRMS salary migration",
		)
		return

	settings = frappe.db.get_singles_dict("Nepal HRMS Settings") or {}
	percent = flt(settings.get("default_basic_percent") or 60)
	if percent <= 0 or percent > 100:
		percent = 60.0
	has_other_allowance = bool(frappe.db.exists("Salary Component", OTHER_ALLOWANCE_COMPONENT))

	assignments = frappe.get_all(
		"Salary Structure Assignment",
		filters={"docstatus": ["<", 2]},
		fields=["name", "employee", "base"],
	)

	migrated = skipped = 0
	for ssa in assignments:
		existing = flt(
			frappe.db.get_value("Salary Structure Assignment", ssa.name, "custom_basic_salary")
		)
		if existing:
			skipped += 1
			continue

		# Prefer the employee's recorded salary; fall back to whatever base holds.
		emp = (
			frappe.db.get_value("Employee", ssa.employee, ["revised_salary", "ctc"], as_dict=True)
			or frappe._dict()
		)
		total = flt(emp.get("revised_salary")) or flt(emp.get("ctc")) or flt(ssa.base)
		if total <= 0:
			skipped += 1
			continue

		basic = flt(total * percent / 100.0, 2)
		remainder = flt(total - basic, 2)
		# Grade and DA are 0 at migration time, so basic remuneration == basic
		# regardless of how the SSF-base toggles are set.
		basic_remuneration = basic

		frappe.db.set_value(
			"Salary Structure Assignment",
			ssa.name,
			{
				"custom_basic_salary": basic,
				"custom_dearness_allowance": 0,
				"custom_grade_amount": 0,
				"custom_basic_remuneration": basic_remuneration,
				"custom_total_allowances": remainder if remainder > 0 else 0,
				"custom_total_fixed_remuneration": total,
				"base": total,
			},
			update_modified=False,
		)

		if remainder > 0 and has_other_allowance:
			_upsert_allowance_row(ssa.name, OTHER_ALLOWANCE_COMPONENT, remainder)

		migrated += 1

	frappe.db.commit()
	frappe.logger().info(
		f"[Nepal HRMS] salary breakdown migration: {migrated} migrated, {skipped} skipped"
	)


def _upsert_allowance_row(parent, component, amount):
	if frappe.db.exists(
		"Nepal Salary Allowance",
		{"parent": parent, "parenttype": "Salary Structure Assignment", "salary_component": component},
	):
		return
	abbr = frappe.db.get_value("Salary Component", component, "salary_component_abbr")
	row = frappe.get_doc(
		{
			"doctype": "Nepal Salary Allowance",
			"parent": parent,
			"parenttype": "Salary Structure Assignment",
			"parentfield": "custom_allowances",
			"salary_component": component,
			"abbr": abbr,
			"amount": amount,
			"description": "Migrated from Employee salary",
		}
	)
	row.insert(ignore_permissions=True)
