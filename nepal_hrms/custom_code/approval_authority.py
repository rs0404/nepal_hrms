# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Who may approve an employee's request.

One rule for Late Entry, Early Exit, Out of Office (applications and check-ins),
Attendance Request, Leave Application, Compensatory Leave and Shift Request:

  * the employee's designated approver, or anyone above that approver in the
    Reports To chain;
  * never the employee themself, unless an active Attendance Policy Escape with
    Allow Self-Approval covers the day (or the site switched that request
    type's "prevent self-approval" setting off);
  * anyone holding an active Attendance Policy Escape with Allow Approving
    Everyone (a System Manager grant) on the request's date;
  * Administrator.

HR roles grant nothing here on purpose: approval follows the org chart, not
access to the HR module.

The designated approver is read from the Employee record (Leave Approver or
Shift Request Approver), falling back to the department's first approver, the
same resolution Frappe HR uses. The approver typed onto a document is not
trusted: an employee could pick anyone.
"""

import frappe
from frappe import _

LEAVE = "leave"
SHIFT = "shift"

# Employee field and Department Approver table per kind of approval.
APPROVER_SOURCES = {
	LEAVE: ("leave_approver", "leave_approvers"),
	SHIFT: ("shift_request_approver", "shift_request_approver"),
}

# A Reports To chain longer than this is a loop in the data, not an org chart.
MAX_CHAIN = 25


def _same_user(a, b):
	return bool(a and b and str(a).strip().lower() == str(b).strip().lower())


def designated_approver(employee, kind=LEAVE):
	"""The approver user set for the employee, or None."""
	field, department_table = APPROVER_SOURCES[kind]
	approver, department = frappe.db.get_value("Employee", employee, [field, "department"]) or (None, None)
	if not approver and department:
		approver = frappe.db.get_value(
			"Department Approver",
			{"parent": department, "parentfield": department_table, "idx": 1},
			"approver",
		)
	return approver or None


def approver_chain(approver_user):
	"""[approver, their Reports To's user, that person's, ...], top last."""
	chain = []
	user = approver_user
	# Stops at the top, at a user with no Employee record, or where Reports To
	# loops back on itself.
	while user and user not in chain and len(chain) < MAX_CHAIN:
		chain.append(user)
		row = frappe.db.get_value(
			"Employee", {"user_id": user, "status": "Active"}, ["name", "reports_to"], as_dict=True
		)
		if not row or not row.reports_to:
			break
		user = frappe.db.get_value("Employee", row.reports_to, "user_id")
	return chain


def is_own(employee, user=None):
	user = user or frappe.session.user
	return _same_user(frappe.db.get_value("Employee", employee, "user_id"), user)


def self_approval_allowed(employee, on_date=None, site_allows=False):
	if site_allows:
		return True
	from nepal_hrms.custom_code.policy_escape import has_policy_escape

	return bool(has_policy_escape(employee, "allow_self_approval", on_date))


def approves_everyone(user=None, on_date=None):
	"""True while `user`'s own employee holds an Allow Approving Everyone escape."""
	from nepal_hrms.custom_code.policy_escape import has_policy_escape

	user = user or frappe.session.user
	approver_employee = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")
	return bool(approver_employee and has_policy_escape(approver_employee, "allow_approve_all", on_date))


def can_approve(employee, kind=LEAVE, on_date=None, user=None, site_allows_self=False):
	"""True when `user` (default: session user) may approve for `employee`."""
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	if not employee:
		return False
	if is_own(employee, user):
		return self_approval_allowed(employee, on_date, site_allows_self)
	if approves_everyone(user, on_date):
		return True
	approver = designated_approver(employee, kind)
	return any(_same_user(user, member) for member in approver_chain(approver))


def assert_can_approve(employee, label, kind=LEAVE, on_date=None, site_allows_self=False):
	if can_approve(employee, kind, on_date, site_allows_self=site_allows_self):
		return
	if is_own(employee):
		frappe.throw(
			_("You cannot approve your own {0}. Your approver must do it.").format(label),
			frappe.PermissionError,
			title=_("Self-Approval Not Allowed"),
		)
	frappe.throw(
		_("Only {0}'s approver, or someone above them in Reports To, can approve this {1}.").format(
			frappe.db.get_value("Employee", employee, "employee_name") or employee, label
		),
		frappe.PermissionError,
		title=_("Approval Not Allowed"),
	)


def approvable_employees(user=None, kind=LEAVE):
	"""Active employees `user` may approve for (not counting themself).

	For team lists and approval queues: whoever's designated approver has
	`user` somewhere in their chain.
	"""
	user = user or frappe.session.user
	field, department_table = APPROVER_SOURCES[kind]
	if user != "Administrator" and approves_everyone(user):
		return [
			name
			for name, user_id in frappe.get_all(
				"Employee", filters={"status": "Active"}, fields=["name", "user_id"], as_list=True
			)
			if not _same_user(user_id, user)
		]
	rows = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "user_id", "department", field],
	)
	department_first = {
		d.parent: d.approver
		for d in frappe.get_all(
			"Department Approver",
			filters={"parentfield": department_table, "idx": 1},
			fields=["parent", "approver"],
		)
	}
	chains = {}
	names = []
	for row in rows:
		if _same_user(row.user_id, user):
			continue
		approver = row.get(field) or department_first.get(row.department)
		if not approver:
			continue
		if approver not in chains:
			chains[approver] = approver_chain(approver)
		if user == "Administrator" or any(_same_user(user, member) for member in chains[approver]):
			names.append(row.name)
	return names
