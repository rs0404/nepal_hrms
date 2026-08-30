# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, get_first_day, get_last_day, getdate, today


CNR_DOCTYPES = (
	"Late Entry Application",
	"Early Exit Application",
	"Out of Office Application",
)


def _team_employee_names(approver_user=None):
	"""Employees whose leave_approver is the given user (User id / email)."""
	approver_user = approver_user or frappe.session.user
	names = frappe.get_all(
		"Employee",
		filters={"leave_approver": approver_user, "status": "Active"},
		pluck="name",
	)
	# Also allow HR Manager / HR User to see all draft apps for approval
	roles = frappe.get_roles(approver_user)
	if "HR Manager" in roles or "HR User" in roles or "System Manager" in roles:
		return None  # no employee filter — all drafts
	return names or ["__none__"]


@frappe.whitelist()
def get_cnr_applications(doctype, employee=None, for_approval=0, limit=20):
	"""List Late Entry / Early Exit / Out of Office applications for PWA."""
	if doctype not in CNR_DOCTYPES:
		frappe.throw(_("Invalid application type"))

	for_approval = cint(for_approval)
	limit = cint(limit) or 20

	filters = {}
	if for_approval:
		team = _team_employee_names()
		filters.update({"docstatus": 0, "status": "Draft"})
		if team is not None:
			filters["employee"] = ["in", team]
	else:
		if not employee:
			employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		if not employee:
			return []
		filters.update({"employee": employee, "docstatus": ["<", 2]})

	fields = [
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
	meta = frappe.get_meta(doctype)
	if meta.has_field("late_entry_time"):
		fields.append("late_entry_time")
	if meta.has_field("early_exit_time"):
		fields.append("early_exit_time")
	if meta.has_field("from_time"):
		fields.extend(["from_time", "to_time", "total_hours"])

	rows = frappe.get_list(
		doctype,
		filters=filters,
		fields=fields,
		order_by="modified desc",
		limit_page_length=limit,
	)
	for r in rows:
		r["doctype"] = doctype
	return rows


def _resolve_employee(employee=None):
	if employee:
		return employee
	return frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")


@frappe.whitelist()
def can_approve_cnr_application(employee=None):
	"""Whether the current user may Approve / Reject / Submit CNR apps for this employee."""
	from nepal_hrms.custom_code.application_hooks import (
		can_approve_cnr_application as _can_approve,
	)

	employee = _resolve_employee(employee)
	if not employee:
		return False
	return bool(_can_approve(employee))


@frappe.whitelist()
def get_late_early_application_deadline_settings():
	"""Public (logged-in) read of late/early application deadline flags for PWA/desk hints."""
	from nepal_hrms.custom_code.attendance_policy import get_hr_settings

	settings = get_hr_settings()
	return {
		"enable_late_early_application_deadline": cint(
			getattr(settings, "enable_late_early_application_deadline", 0) or 0
		),
		"late_early_application_max_days": cint(
			getattr(settings, "late_early_application_max_days", None) or 2
		),
	}


@frappe.whitelist()
def get_late_early_pool_summary(employee=None, month_date=None, from_date=None, to_date=None):
	"""
	Month pool summary for BS HRMS / desk: counts, free remaining, half-days so far,
	and full-day escalation state. Uses the same rules as salary slip payroll.

	Pass from_date + to_date for a custom window (e.g. current BS month AD span);
	otherwise month_date / today uses Gregorian calendar month bounds.
	"""
	from nepal_hrms.custom_code.attendance_policy import (
		free_occurrences_remaining,
		get_hr_settings,
		occurrence_half_days,
	)

	employee = _resolve_employee(employee)
	if not employee:
		frappe.throw(_("Employee not found"))

	# Employees may only read their own summary unless HR/System Manager
	roles = frappe.get_roles()
	if not ({"HR Manager", "HR User", "System Manager"} & set(roles)):
		session_emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		if employee != session_emp:
			frappe.throw(_("Not permitted"), frappe.PermissionError)

	if from_date and to_date:
		start = getdate(from_date)
		end = getdate(to_date)
	else:
		ref = getdate(month_date or today())
		start = get_first_day(ref)
		end = get_last_day(ref)

	settings = get_hr_settings()
	initial_grace = cint(getattr(settings, "initial_grace_occurrences", None) or 2)
	subsequent_step = cint(getattr(settings, "subsequent_grace_step_occurrences", None) or 2)
	combine = cint(getattr(settings, "combine_late_and_early_pool", 0) or 0)
	escalate = cint(getattr(settings, "enable_late_full_day_escalation", 0) or 0)
	escalate_after = cint(getattr(settings, "late_full_day_after_occurrences", 5) or 5)
	penalty_on = cint(getattr(settings, "enable_late_early_penalty", 0) or 0)

	meta = frappe.get_meta("Attendance")
	late_pool_count = 0
	early_pool_count = 0
	if meta.has_field("custom_cnr_late_in_pool"):
		late_pool_count = frappe.db.count(
			"Attendance",
			{
				"employee": employee,
				"attendance_date": ["between", [start, end]],
				"docstatus": ["<", 2],
				"custom_cnr_late_in_pool": 1,
			},
		)
	if meta.has_field("custom_cnr_early_in_pool"):
		early_pool_count = frappe.db.count(
			"Attendance",
			{
				"employee": employee,
				"attendance_date": ["between", [start, end]],
				"docstatus": ["<", 2],
				"custom_cnr_early_in_pool": 1,
			},
		)

	combined_count = late_pool_count + early_pool_count
	if combine:
		pool_for_half = combined_count
		half_days_so_far = occurrence_half_days(pool_for_half, initial_grace, subsequent_step)
		free_remaining = free_occurrences_remaining(pool_for_half, initial_grace, subsequent_step)
		escalation_active = bool(escalate and pool_for_half > escalate_after)
	else:
		late_hd = occurrence_half_days(late_pool_count, initial_grace, subsequent_step)
		early_hd = occurrence_half_days(early_pool_count, initial_grace, subsequent_step)
		half_days_so_far = late_hd + early_hd
		# Show free remaining against the larger of the two pools for clarity
		primary = max(late_pool_count, early_pool_count)
		free_remaining = free_occurrences_remaining(primary, initial_grace, subsequent_step)
		escalation_active = bool(
			escalate and (late_pool_count > escalate_after or early_pool_count > escalate_after)
		)

	return {
		"employee": employee,
		"from_date": str(start),
		"to_date": str(end),
		"penalty_enabled": penalty_on,
		"late_pool_count": late_pool_count,
		"early_pool_count": early_pool_count,
		"combined_count": combined_count,
		"combine_pools": combine,
		"initial_grace_occurrences": initial_grace,
		"subsequent_grace_step_occurrences": subsequent_step,
		"free_remaining": free_remaining,
		"half_days_so_far": half_days_so_far,
		"full_day_escalation_enabled": escalate,
		"full_day_escalation_threshold": escalate_after,
		"full_day_escalation_active": escalation_active,
	}


@frappe.whitelist()
def get_cnr_application_counts(employee=None, from_date=None, to_date=None):
	"""
	Counts for Late Entry / Early Exit / Out of Office applications in a date range.
	Returns approved / rejected / pending (Draft) / total per doctype.
	"""
	employee = _resolve_employee(employee)
	if not employee:
		frappe.throw(_("Employee not found"))

	roles = frappe.get_roles()
	if not ({"HR Manager", "HR User", "System Manager"} & set(roles)):
		session_emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		if employee != session_emp:
			frappe.throw(_("Not permitted"), frappe.PermissionError)

	ref = getdate(from_date or today()) if from_date else getdate(today())
	start = getdate(from_date) if from_date else get_first_day(ref)
	end = getdate(to_date) if to_date else get_last_day(ref)

	result = {}
	for doctype in CNR_DOCTYPES:
		base = {
			"employee": employee,
			"attendance_date": ["between", [start, end]],
			"docstatus": ["<", 2],
		}
		total = frappe.db.count(doctype, base)
		approved = frappe.db.count(doctype, {**base, "status": "Approved"})
		rejected = frappe.db.count(doctype, {**base, "status": "Rejected"})
		pending = frappe.db.count(doctype, {**base, "status": "Draft"})
		key = {
			"Late Entry Application": "late_entry",
			"Early Exit Application": "early_exit",
			"Out of Office Application": "out_of_office",
		}[doctype]
		result[key] = {
			"doctype": doctype,
			"label": doctype.replace(" Application", ""),
			"total": total,
			"approved": approved,
			"rejected": rejected,
			"pending": pending,
		}

	result["from_date"] = str(start)
	result["to_date"] = str(end)
	return result

