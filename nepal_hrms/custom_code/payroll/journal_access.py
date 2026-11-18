# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Keep payroll Journal Entries to the people allowed to see salaries.

With "Process Payroll Accounting Entry based on Employee" on, the accrual JV
and the payroll bank entry carry one row per employee -- every salary, readable
by anyone who can read Journal Entries. Most accountants here also hold HR
roles, so no existing role draws the line; a dedicated one does.

A payroll Journal Entry is one with any row referencing a Payroll Entry. Only
Administrator and holders of PAYROLL_JOURNAL_ROLE see those; everyone else
keeps every other Journal Entry exactly as before. The role only unlocks: it
does not itself grant Journal Entry access.

Not covered: General Ledger and other ledger reports still list the per-employee
payable lines -- those read GL Entry, not Journal Entry.
"""

import frappe

PAYROLL_JOURNAL_ROLE = "Payroll Journal Viewer"


def can_see_payroll_journals(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or PAYROLL_JOURNAL_ROLE in frappe.get_roles(user)


def is_payroll_journal(doc):
	"""Whether a Journal Entry (doc or name) references a Payroll Entry."""
	rows = doc.get("accounts") if hasattr(doc, "get") else None
	if rows:
		return any(row.get("reference_type") == "Payroll Entry" for row in rows)
	name = doc if isinstance(doc, str) else doc.get("name")
	if not name:
		return False
	return bool(
		frappe.db.exists(
			"Journal Entry Account",
			{"parenttype": "Journal Entry", "parent": name, "reference_type": "Payroll Entry"},
		)
	)


def get_permission_query_conditions(user=None, doctype=None):
	"""Leave payroll Journal Entries out of lists, reports and link searches."""
	if can_see_payroll_journals(user):
		return ""
	return (
		"not exists (select 1 from `tabJournal Entry Account` nh_payroll_jea"
		" where nh_payroll_jea.parent = `tabJournal Entry`.`name`"
		" and nh_payroll_jea.parenttype = 'Journal Entry'"
		" and nh_payroll_jea.reference_type = 'Payroll Entry')"
	)


def has_permission(doc, ptype=None, user=None, debug=False):
	"""Refuse a payroll Journal Entry opened by link; defer on everything else.

	Frappe v16 reads anything but True as a denial (v15 took None as "no
	opinion"). True does not grant access: role permissions are still checked
	separately, so it only means this hook does not object.
	"""
	if can_see_payroll_journals(user):
		return True
	return not is_payroll_journal(doc)


def ensure_role():
	if not frappe.db.exists("Role", PAYROLL_JOURNAL_ROLE):
		frappe.get_doc(
			{"doctype": "Role", "role_name": PAYROLL_JOURNAL_ROLE, "desk_access": 1}
		).insert(ignore_permissions=True)
