# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Keep an Additional Salary on the component variant its employee is paid under.

Wages and Salary components are twins: identical arithmetic and tax flags, but
they post to different expense accounts (see setup.py). Stock HRMS ties the
component you pick on an Additional Salary to nothing at all, so a salaried
employee's one-off overtime silently lands on the wages expense account and
nobody notices until the accrual JE is booked.

The rule is stated as "not the opposite variant" rather than "the matching
variant" on purpose: components carrying no variant suffix -- TDS, CIT,
Insurance, the SSF and PF contributions -- post to liability accounts and are
valid for anyone, so they must keep passing.
"""

import frappe
from frappe import _

VARIANTS = ("Salary", "Wages")

# Fallback when the settings field has not reached the site yet.
DEFAULT_ACTION = "Block"


def opposite_variant(variant):
	return "Wages" if variant == "Salary" else "Salary"


def structure_variant(salary_structure):
	"""Salary/Wages out of a structure name, e.g.
	'Nepal Payroll - SSF - Salary - Yarsa Tech Pvt. Ltd.'.

	None when the name carries neither marker, which is how a structure built
	outside Nepal payroll setup opts out of the whole check."""
	name = salary_structure or ""
	for variant in VARIANTS:
		if f" - {variant} - " in name:
			return variant
	return None


def component_variant(salary_component):
	"""Salary/Wages out of a component name, or None for a shared component."""
	name = salary_component or ""
	for variant in VARIANTS:
		if name.endswith(f" - {variant}"):
			return variant
	return None


def twin_component(salary_component, variant):
	"""The same component in the other variant. Returns the name whether or not
	the site has created it, so the caller can name it in the error."""
	current = component_variant(salary_component)
	if not current or current == variant:
		return None
	return f"{salary_component[: -len(f' - {current}')]} - {variant}"


def employee_variant(employee, on_date=None):
	"""The variant the employee is assigned to, as of on_date."""
	if not employee:
		return None

	filters = {"employee": employee, "docstatus": 1}
	if on_date:
		filters["from_date"] = ["<=", on_date]

	structure = frappe.db.get_value(
		"Salary Structure Assignment", filters, "salary_structure", order_by="from_date desc"
	)
	if not structure and on_date:
		# Dated ahead of the first assignment: fall back to whatever they are on.
		structure = frappe.db.get_value(
			"Salary Structure Assignment",
			{"employee": employee, "docstatus": 1},
			"salary_structure",
			order_by="from_date desc",
		)
	return structure_variant(structure)


def mismatch_action():
	"""Block or Warn, from Nepal HRMS Settings.

	Read defensively: live sites reload doctypes rather than migrate, so the
	field may not exist yet. An unset value must block, not wave things through."""
	try:
		action = frappe.db.get_single_value("Nepal HRMS Settings", "additional_salary_variant_action")
	except Exception:
		action = None
	return action or DEFAULT_ACTION


def validate_component_variant(doc, method=None):
	variant = employee_variant(doc.employee, doc.get("payroll_date") or doc.get("from_date"))
	if not variant:
		return

	wrong = component_variant(doc.salary_component)
	if not wrong or wrong == variant:
		return

	twin = twin_component(doc.salary_component, variant)
	message = _("{0} is paid on a {1} structure, so {2} would post to the {3} expense account.").format(
		doc.get("employee_name") or doc.employee,
		variant,
		frappe.bold(doc.salary_component),
		wrong,
	)

	if frappe.db.exists("Salary Component", twin):
		message += " " + _("Use {0} instead.").format(frappe.bold(twin))
	else:
		message += " " + _("This component has no {0} variant yet -- create {1}.").format(
			variant, frappe.bold(twin)
		)

	title = _("Component Variant Mismatch")
	if mismatch_action() == "Warn":
		frappe.msgprint(message, title=title, indicator="orange")
	else:
		frappe.throw(message, title=title)


@frappe.whitelist()
def get_employee_variant(employee, on_date=None):
	"""Drives the salary_component link filter on the Additional Salary form."""
	frappe.has_permission("Employee", doc=employee, throw=True)
	return employee_variant(employee, on_date)
