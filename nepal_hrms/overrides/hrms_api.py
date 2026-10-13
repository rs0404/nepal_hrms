# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""bshrms list APIs: Attendance Requests with Open/Approved/Rejected status, and
Leave Applications with the half each half-day leave takes."""

from __future__ import annotations

import frappe
from frappe import cint

from hrms.api import get_filters, get_workflow_state_field


@frappe.whitelist()
def get_attendance_requests(
	employee: str,
	for_approval: bool | int = False,
	limit: int | None = None,
) -> list[dict]:
	for_approval = cint(for_approval)
	filters = get_filters("Attendance Request", employee, None, for_approval)

	# Pending approval: Open drafts, and Approved ones still waiting for Submit.
	# A rejected request is final as a draft, so it stays off the queue.
	if for_approval:
		filters["status"] = ["in", ["Open", "Approved"]]

	fields = [
		"name",
		"reason",
		"employee",
		"employee_name",
		"from_date",
		"to_date",
		"include_holidays",
		"shift",
		"docstatus",
		"creation",
		"status",
		"custom_rejection_reason",
		"explanation",
		"owner",
	]

	if workflow_state_field := get_workflow_state_field("Attendance Request"):
		fields.append(workflow_state_field)

	attendance_requests = frappe.get_list(
		"Attendance Request",
		fields=fields,
		filters=filters,
		order_by="creation desc",
		limit=limit,
	)

	if workflow_state_field:
		for application in attendance_requests:
			application["workflow_state_field"] = workflow_state_field

	return attendance_requests


@frappe.whitelist()
def get_leave_applications(
	employee: str,
	approver_id: str | None = None,
	for_approval: bool = False,
	limit: int | None = None,
) -> list[dict]:
	"""Stock leave list, plus docstatus and which half each half-day leave takes.

	The PWA marks a leave Full day / 1st half / 2nd half; stock returns half_day
	alone, which cannot tell the two halves apart.
	"""
	from hrms.api import get_leave_applications as stock_get_leave_applications

	from nepal_hrms.custom_code.half_day import SESSION_FIELD

	applications = stock_get_leave_applications(
		employee, approver_id=approver_id, for_approval=for_approval, limit=limit
	)
	# Stock leaves docstatus out, so an approved draft read as approved.
	if applications:
		docstatus = dict(
			frappe.get_all(
				"Leave Application",
				filters={"name": ["in", [row.name for row in applications]]},
				fields=["name", "docstatus"],
				as_list=True,
			)
		)
		for row in applications:
			row["docstatus"] = docstatus.get(row.name, 0)
	names = [row.name for row in applications if row.get("half_day")]
	if names and frappe.get_meta("Leave Application").has_field(SESSION_FIELD):
		# Rows already passed stock's permission check; this only adds a column.
		sessions = dict(
			frappe.get_all(
				"Leave Application",
				filters={"name": ["in", names]},
				fields=["name", SESSION_FIELD],
				as_list=True,
			)
		)
		for row in applications:
			row[SESSION_FIELD] = sessions.get(row.name)
	return applications
