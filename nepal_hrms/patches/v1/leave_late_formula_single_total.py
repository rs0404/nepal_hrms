"""Point the Leave and Late Deduction formula at the one computed total.

The formula used to respell the deduction term by term. Every time a term moved --
most recently late / early half days leaving for penalty_days -- the row drifted
from the amount actually charged to earnings, under-reporting the deduction on the
slip. `leave_late_deduction_total` is that amount, computed once.

Unlike the earlier split patch this also reterms submitted structures: they are
what new draft slips are built from, and leaving them stale keeps producing wrong
rows. Slips already issued are not recalculated.
"""

import frappe

from nepal_hrms.custom_code.payroll.setup import LEAVE_LATE_FORMULA

# Every spelling this formula has shipped with.
LEGACY_FORMULAS = (
	"(late_entry_half_days + early_exit_half_days + out_of_office_half_days) * late_deduction_rate "
	"+ lwp_days * lwp_deduction_rate "
	"+ unapproved_absent_days * unapproved_absent_rate",
	"(late_entry_half_days + early_exit_half_days + out_of_office_half_days) * late_deduction_rate "
	"+ lwp_days * lwp_deduction_rate "
	"+ unapproved_absent_days * unapproved_absent_rate "
	"+ penalty_days * penalty_deduction_rate",
)


def _normalise(formula):
	return " ".join((formula or "").split())


def execute():
	legacy = {_normalise(f) for f in LEGACY_FORMULAS}
	values = {"formula": LEAVE_LATE_FORMULA, "amount_based_on_formula": 1}

	components = [
		row.name
		for row in frappe.get_all(
			"Salary Component", filters={"type": "Deduction"}, fields=["name", "formula"]
		)
		if _normalise(row.formula) in legacy
	]
	for name in components:
		frappe.db.set_value("Salary Component", name, values, update_modified=False)

	rows = frappe.get_all(
		"Salary Detail",
		filters={"parenttype": "Salary Structure", "parentfield": "deductions"},
		fields=["name", "formula"],
	)
	for row in rows:
		if _normalise(row.formula) in legacy:
			frappe.db.set_value("Salary Detail", row.name, values, update_modified=False)

	if components or rows:
		frappe.clear_cache()
