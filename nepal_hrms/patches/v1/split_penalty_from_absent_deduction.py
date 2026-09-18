# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Charge ½P / 1P pool penalties through their own formula term.

Before this patch the Leave and Late Deduction formula folded pool penalties into
`unapproved_absent_days`. They now carry their own count and rate, so every
component and every draft structure row that still uses the old formula has to be
retermed -- otherwise the penalty days are counted by nothing at all.
"""

import frappe

from nepal_hrms.custom_code.payroll.setup import LEAVE_LATE_FORMULA

OLD_FORMULA = (
	"(late_entry_half_days + early_exit_half_days + out_of_office_half_days) * late_deduction_rate "
	"+ lwp_days * lwp_deduction_rate "
	"+ unapproved_absent_days * unapproved_absent_rate"
)


def _normalise(formula):
	return " ".join((formula or "").split())


def execute():
	old = _normalise(OLD_FORMULA)

	components = frappe.get_all(
		"Salary Component",
		filters={"type": "Deduction"},
		fields=["name", "formula"],
	)
	updated_components = []
	for component in components:
		if _normalise(component.formula) != old:
			continue
		frappe.db.set_value(
			"Salary Component",
			component.name,
			{"formula": LEAVE_LATE_FORMULA, "amount_based_on_formula": 1},
			update_modified=False,
		)
		updated_components.append(component.name)

	if not updated_components:
		return

	# Draft structures hold their own copy of the formula. Submitted ones are left
	# alone: their slips are already issued and must not be restated here.
	rows = frappe.get_all(
		"Salary Detail",
		filters={
			"parenttype": "Salary Structure",
			"parentfield": "deductions",
			"salary_component": ["in", updated_components],
		},
		fields=["name", "parent", "formula"],
	)
	if not rows:
		return

	draft_structures = set(
		frappe.get_all(
			"Salary Structure",
			filters={"name": ["in", list({r.parent for r in rows})], "docstatus": 0},
			pluck="name",
		)
	)
	for row in rows:
		if row.parent not in draft_structures:
			continue
		if _normalise(row.formula) != old:
			continue
		frappe.db.set_value(
			"Salary Detail",
			row.name,
			{"formula": LEAVE_LATE_FORMULA, "amount_based_on_formula": 1},
			update_modified=False,
		)
