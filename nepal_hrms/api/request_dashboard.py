# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint

from nepal_hrms.api.cnr_applications import CNR_DOCTYPES, _team_employee_names


REQUEST_FIELDS = {
	"Leave Application": [
		"name",
		"employee",
		"employee_name",
		"leave_type",
		"status",
		"from_date",
		"to_date",
		"half_day",
		"half_day_date",
		"description",
		"total_leave_days",
		"leave_balance",
		"leave_approver",
		"docstatus",
		"creation",
		"modified",
	],
	"Expense Claim": [
		"name",
		"employee",
		"employee_name",
		"approval_status",
		"status",
		"expense_approver",
		"total_claimed_amount",
		"posting_date",
		"company",
		"docstatus",
		"creation",
		"modified",
	],
	"Shift Request": [
		"name",
		"employee",
		"employee_name",
		"shift_type",
		"from_date",
		"to_date",
		"status",
		"approver",
		"docstatus",
		"creation",
		"modified",
	],
	"Attendance Request": [
		"name",
		"employee",
		"employee_name",
		"reason",
		"from_date",
		"to_date",
		"include_holidays",
		"shift",
		"status",
		"docstatus",
		"creation",
		"modified",
	],
}

CNR_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"attendance_date",
	"type_of_work",
	"status",
	"reason",
	"docstatus",
	"creation",
	"modified",
	"attendance",
]


def _is_hr_user():
	return bool(
		set(frappe.get_roles())
		& {"HR Manager", "HR User", "System Manager"}
	)


def _approved_filters(doctype):
	filters = {"docstatus": ["<", 2]}
	if doctype == "Expense Claim":
		filters["approval_status"] = "Approved"
	else:
		filters["status"] = "Approved"

	if _is_hr_user():
		return filters

	approver_field = {
		"Leave Application": "leave_approver",
		"Expense Claim": "expense_approver",
		"Shift Request": "approver",
	}.get(doctype)
	if approver_field:
		filters[approver_field] = frappe.session.user
		return filters

	team = _team_employee_names()
	filters["employee"] = ["in", team or ["__none__"]]
	return filters


def _available_fields(doctype, fields):
	meta = frappe.get_meta(doctype)
	return [field for field in fields if field in {"name", "creation", "modified", "docstatus"} or meta.has_field(field)]


@frappe.whitelist()
def get_recently_approved_team_requests(limit=20):
	"""Return recently approved requests that the current user is allowed to review."""
	limit = max(1, min(cint(limit) or 20, 100))
	requests = []

	for doctype, fields in REQUEST_FIELDS.items():
		rows = frappe.get_list(
			doctype,
			filters=_approved_filters(doctype),
			fields=_available_fields(doctype, fields),
			order_by="modified desc",
			limit_page_length=limit,
		)
		for row in rows:
			row["doctype"] = doctype
		requests.append(row)

	for doctype in CNR_DOCTYPES:
		fields = list(CNR_FIELDS)
		meta = frappe.get_meta(doctype)
		for fieldname in (
			"estimated_late_entry_time",
			"estimated_from_time",
			"estimated_to_time",
		):
			if meta.has_field(fieldname):
				fields.append(fieldname)
		if meta.has_field("late_entry_time"):
			fields.append("late_entry_time")
		if meta.has_field("early_exit_time"):
			fields.append("early_exit_time")
		if meta.has_field("from_time"):
			fields.extend(["from_time", "to_time", "total_hours"])

		rows = frappe.get_list(
			doctype,
			filters=_approved_filters(doctype),
			fields=_available_fields(doctype, fields),
			order_by="modified desc",
			limit_page_length=limit,
		)
		for row in rows:
			row["doctype"] = doctype
		requests.append(row)

	requests.sort(
		key=lambda row: str(row.get("modified") or row.get("creation") or ""),
		reverse=True,
	)
	return requests[:limit]
