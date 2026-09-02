# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, today

from nepal_hrms.custom_code.attendance_policy import (
	get_hr_settings,
	link_application_to_attendance,
	set_attendance_ooo_hours,
	sync_attendance_after_application,
)


CNR_APPLICATION_DOCTYPES = (
	"Late Entry Application",
	"Early Exit Application",
	"Out of Office Application",
)


def _ensure_company(doc):
	if not doc.company and doc.employee:
		doc.company = frappe.db.get_value("Employee", doc.employee, "company")


def _prevent_self_cnr_application_approval() -> bool:
	"""Default to blocking self-approval, including before settings are migrated."""
	if not frappe.db.exists("DocType", "Nepal HRMS Settings"):
		return True
	meta = frappe.get_meta("Nepal HRMS Settings")
	if not meta.has_field("prevent_self_cnr_application_approval"):
		return True
	value = frappe.db.get_single_value(
		"Nepal HRMS Settings", "prevent_self_cnr_application_approval"
	)
	return True if value is None else bool(cint(value))


def can_approve_cnr_application(employee: str) -> bool:
	"""True if current user may Approve / Reject / Submit a CNR application for employee.

	Self-approval follows Nepal HRMS Settings. Leave Approver, HR Manager/User,
	System Manager, and Administrator may approve other employees.
	"""
	user = frappe.session.user
	if user == "Administrator":
		return True
	if not employee:
		return False

	emp_user = frappe.db.get_value("Employee", employee, "user_id")
	is_self = bool(emp_user and emp_user == user)
	if is_self and _prevent_self_cnr_application_approval():
		return False

	leave_approver = frappe.db.get_value("Employee", employee, "leave_approver")
	if leave_approver and str(leave_approver).lower() == str(user).lower():
		return True

	if is_self:
		return True

	roles = set(frappe.get_roles(user))
	return bool(roles & {"HR Manager", "HR User", "System Manager"})


def validate_cnr_approval_authority(doc, method=None):
	"""Block self-approval: only Leave Approver / HR may set Approved/Rejected."""
	if getattr(doc.flags, "ignore_permissions", False):
		return
	if doc.doctype not in CNR_APPLICATION_DOCTYPES:
		return
	if doc.status not in ("Approved", "Rejected"):
		return
	if doc.status == "Rejected" and doc.meta.has_field("custom_rejection_reason"):
		if not (doc.custom_rejection_reason or "").strip():
			frappe.throw(_("Rejection Reason is required"))
	elif doc.meta.has_field("custom_rejection_reason"):
		doc.custom_rejection_reason = None
	if can_approve_cnr_application(doc.employee):
		return

	frappe.throw(
		_(
			"Only the Leave Approver (or HR Manager) can set this {0} to {1}. "
			"You may save it as Draft for approval."
		).format(_(doc.doctype), _(doc.status)),
		frappe.PermissionError,
		title=_("Approval Required"),
	)


def before_submit_cnr_application(doc, method=None):
	"""Employees cannot submit their own Late/Early/OOO applications."""
	if getattr(doc.flags, "ignore_permissions", False):
		return
	if doc.doctype not in CNR_APPLICATION_DOCTYPES:
		return

	if not can_approve_cnr_application(doc.employee):
		frappe.throw(
			_(
				"Only the Leave Approver (or HR Manager) can submit this {0}. "
				"Please keep it as Draft until it is approved."
			).format(_(doc.doctype)),
			frappe.PermissionError,
			title=_("Submission Not Allowed"),
		)

	if doc.status != "Approved":
		frappe.throw(
			_("Only Approved applications can be submitted. Current status: {0}").format(
				_(doc.status)
			)
		)


def _validate_late_early_application_deadline(doc):
	"""Block Late/Early apps filed after the configured window from attendance_date."""
	if doc.doctype not in ("Late Entry Application", "Early Exit Application"):
		return
	if not doc.attendance_date:
		return

	from nepal_hrms.custom_code.policy_escape import has_policy_escape

	if doc.employee and has_policy_escape(
		doc.employee, "escape_applications", doc.attendance_date
	):
		return

	settings = get_hr_settings()
	if not cint(getattr(settings, "enable_late_early_application_deadline", 0) or 0):
		return

	max_days = cint(getattr(settings, "late_early_application_max_days", None) or 2)
	if max_days < 0:
		max_days = 0

	attendance_date = getdate(doc.attendance_date)
	deadline = add_days(attendance_date, max_days)
	if getdate(today()) > deadline:
		frappe.throw(
			_(
				"{0} cannot be submitted for {1}. Forms must be filed within {2} day(s) "
				"of the attendance date (deadline was {3})."
			).format(
				_(doc.doctype),
				frappe.format(attendance_date, {"fieldtype": "Date"}),
				max_days,
				frappe.format(deadline, {"fieldtype": "Date"}),
			),
			title=_("Application Deadline Passed"),
		)


def validate_late_early_application(doc, method=None):
	_ensure_company(doc)
	_validate_late_early_application_deadline(doc)
	validate_cnr_approval_authority(doc)
	link_application_to_attendance(doc)


def on_submit_late_early_application(doc, method=None):
	if doc.status != "Approved":
		frappe.throw(_("Only Approved applications can be submitted. Current status: {0}").format(doc.status))

	link_application_to_attendance(doc)
	if doc.attendance:
		frappe.db.set_value(doc.doctype, doc.name, "attendance", doc.attendance)
	# Restore Present when Personal (<= max delay) / Office Work excuses the delay
	sync_attendance_after_application(doc)


def on_cancel_late_early_application(doc, method=None):
	sync_attendance_after_application(doc)


def validate_ooo_application(doc, method=None):
	_ensure_company(doc)
	validate_cnr_approval_authority(doc)

	if doc.from_time and doc.to_time:
		from frappe.utils import time_diff_in_hours

		doc.total_hours = flt(time_diff_in_hours(doc.to_time, doc.from_time), 2)
		if doc.total_hours < 0:
			frappe.throw(_("To Time must be after From Time."))

		settings = get_hr_settings()
		max_paid_hours = flt(getattr(settings, "max_paid_out_of_office_hours", None) or 2.0)
		if doc.type_of_work == "Personal Work" and doc.total_hours > max_paid_hours:
			frappe.msgprint(
				_(
					"Warning: Out of Office duration for Personal Work is {0} hrs, which exceeds "
					"the max allowed paid limit of {1} hrs. This will count as a half-day deduction "
					"in payroll unless a Half Day Leave Application is used instead."
				).format(doc.total_hours, max_paid_hours),
				title=_("Max Paid Hours Exceeded"),
				indicator="orange",
			)

	link_application_to_attendance(doc)


def on_submit_ooo_application(doc, method=None):
	if doc.status != "Approved":
		frappe.throw(_("Only Approved applications can be submitted. Current status: {0}").format(doc.status))

	link_application_to_attendance(doc)
	if doc.attendance:
		frappe.db.set_value(doc.doctype, doc.name, "attendance", doc.attendance)
		if frappe.get_meta("Attendance").has_field("custom_ooo_hours"):
			frappe.db.set_value(
				"Attendance",
				doc.attendance,
				{
					"custom_ooo_hours": flt(doc.total_hours, 2),
					"custom_has_ooo_logs": 1,
				},
			)
	else:
		set_attendance_ooo_hours(doc.employee, doc.attendance_date, hours=flt(doc.total_hours, 2))
	sync_attendance_after_application(doc)


def on_cancel_ooo_application(doc, method=None):
	sync_attendance_after_application(doc)
