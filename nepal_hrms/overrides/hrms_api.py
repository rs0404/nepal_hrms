# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Attendance Request list APIs with Open/Approved/Rejected status for bshrms."""

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

	# Pending approval: only Open drafts (Rejected/Approved stay off the team queue)
	if for_approval:
		filters["status"] = "Open"

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
