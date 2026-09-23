# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from datetime import timedelta

from frappe.utils import (
	add_days,
	cint,
	flt,
	get_datetime,
	getdate,
	get_timedelta,
	today,
)

from nepal_hrms.custom_code.attendance_policy import (
	get_shift_bounds,
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


def _checkin_day(checkin):
	anchor = getattr(checkin, "shift_start", None) or checkin.time
	return get_datetime(anchor).date()


def _checkin_time(checkin):
	return get_datetime(checkin.time).time().replace(microsecond=0)


def _hours_between(end_time, start_time):
	end_delta = get_timedelta(str(end_time))
	start_delta = get_timedelta(str(start_time))
	if end_delta is None or start_delta is None:
		return 0
	return round((end_delta - start_delta).total_seconds() / 3600, 6)


def _validate_application_reason(doc):
	if not (getattr(doc, "reason", None) or "").strip():
		frappe.throw(_("Reason is required."))


def _is_rejected_application(doc):
	return (getattr(doc, "status", None) or "").strip() == "Rejected"


def _validate_cnr_application_time_limit(doc):
	# Filing is blocked for over-limit Personal Work. Rejection must still go through.
	if _is_rejected_application(doc):
		return
	# Office Work fully excuses major late/early and long OOO; caps are for Personal Work.
	if (getattr(doc, "type_of_work", None) or "").strip() == "Office Work":
		return

	settings = get_hr_settings()

	if doc.doctype == "Out of Office Application":
		if not (doc.estimated_from_time and doc.estimated_to_time):
			return
		estimated_hours = flt(
			_hours_between(
				doc.estimated_to_time, doc.estimated_from_time
			),
			2,
		)
		max_hours = flt(
			getattr(settings, "max_paid_out_of_office_hours", None) or 2
		)
		if max_hours > 0 and estimated_hours > max_hours:
			frappe.throw(
				_(
					"Estimated Out of Office duration is {0} hours, exceeding "
					"the configured limit of {1} hours. Shorten the time range "
					"before submitting."
				).format(estimated_hours, max_hours),
				title=_("Out of Office Time Limit Exceeded"),
			)
		return

	if doc.doctype not in (
		"Late Entry Application",
		"Early Exit Application",
	):
		return

	max_minutes = cint(
		getattr(settings, "late_early_max_delay_mins", None) or 60
	)
	if max_minutes <= 0:
		return

	shift = None
	if doc.attendance:
		shift = frappe.db.get_value("Attendance", doc.attendance, "shift")
	shift_start, shift_end = get_shift_bounds(
		doc.employee, doc.attendance_date, shift
	)
	if not shift_start or not shift_end:
		return

	if doc.doctype == "Late Entry Application":
		value = getattr(doc, "estimated_late_entry_time", None)
		if not value:
			return
		actual = get_datetime(f"{getdate(doc.attendance_date)} {value}")
		minutes = max(
			0, cint((actual - shift_start).total_seconds() / 60)
		)
		label = _("Estimated late entry")
	else:
		value = getattr(doc, "early_exit_time", None)
		if not value:
			return
		actual = get_datetime(f"{getdate(doc.attendance_date)} {value}")
		if shift_end.date() > shift_start.date() and actual < shift_start:
			actual += timedelta(days=1)
		minutes = max(
			0, cint((shift_end - actual).total_seconds() / 60)
		)
		label = _("Early exit")

	if minutes > max_minutes:
		frappe.throw(
			_(
				"{0} is {1} minutes, exceeding the configured limit of "
				"{2} minutes. Change the time before submitting."
			).format(label, minutes, max_minutes),
			title=_("Application Time Limit Exceeded"),
		)


def _active_application(doctype, employee, attendance_date, extra_filters=None):
	filters = {
		"employee": employee,
		"attendance_date": attendance_date,
		"docstatus": ["<", 2],
		"status": ["!=", "Rejected"],
	}
	filters.update(extra_filters or {})
	name = frappe.db.get_value(
		doctype,
		filters,
		"name",
		order_by="creation desc",
	)
	return frappe.get_doc(doctype, name) if name else None


def _set_application_actuals(application, values):
	changed = {
		fieldname: value
		for fieldname, value in values.items()
		if application.meta.has_field(fieldname)
		and value is not None
		and application.get(fieldname) != value
	}
	if not changed:
		return

	application.db_set(changed, notify=True)

	if (
		application.doctype == "Out of Office Application"
		and application.status == "Approved"
		and application.attendance
		and flt(changed.get("total_hours") or application.total_hours) > 0
	):
		frappe.db.set_value(
			"Attendance",
			application.attendance,
			{
				"custom_ooo_hours": flt(
					changed.get("total_hours") or application.total_hours, 2
				),
				"custom_has_ooo_logs": 1,
			},
		)


def _ooo_application_for_checkin(checkin, day):
	if frappe.get_meta("Employee Checkin").has_field("custom_ooo_application"):
		if getattr(checkin, "custom_ooo_application", None):
			return frappe.get_doc(
				"Out of Office Application", checkin.custom_ooo_application
			)

		if checkin.log_type == "OUT":
			start = frappe.get_all(
				"Employee Checkin",
				filters={
					"employee": checkin.employee,
					"time": ["<", checkin.time],
					"log_type": "IN",
					"custom_attendance_type": "OOO Work",
					"custom_ooo_application": ["is", "set"],
				},
				fields=["custom_ooo_application"],
				order_by="time desc",
				limit=1,
			)
			if start:
				return frappe.get_doc(
					"Out of Office Application",
					start[0].custom_ooo_application,
				)

	extra = {"from_time": ["is", "set"], "to_time": ["is", "not set"]}
	if checkin.log_type == "IN":
		extra = {"from_time": ["is", "not set"]}
	return _active_application(
		"Out of Office Application", checkin.employee, day, extra
	)


def sync_cnr_application_from_checkin(doc, method=None):
	"""Fill exact application times immediately when an Employee Checkin is inserted."""
	if not doc.employee or not doc.time or doc.log_type not in ("IN", "OUT"):
		return

	day = _checkin_day(doc)
	actual_time = _checkin_time(doc)
	attendance_type = (
		getattr(doc, "custom_attendance_type", None) or "Normal"
	).strip()

	if attendance_type != "OOO Work":
		if doc.log_type != "IN":
			return
		application = _active_application(
			"Late Entry Application",
			doc.employee,
			day,
			{"late_entry_time": ["is", "not set"]},
		)
		if application:
			_set_application_actuals(
				application, {"late_entry_time": actual_time}
			)
		return

	application = _ooo_application_for_checkin(doc, day)
	if not application:
		return

	if (
		frappe.get_meta("Employee Checkin").has_field("custom_ooo_application")
		and not getattr(doc, "custom_ooo_application", None)
	):
		doc.db_set(
			"custom_ooo_application",
			application.name,
			update_modified=False,
		)

	if doc.log_type == "IN":
		_set_application_actuals(application, {"from_time": actual_time})
		return

	from_time = application.from_time
	if not from_time:
		return
	hours = flt(_hours_between(actual_time, from_time), 2)
	if hours < 0:
		return
	_set_application_actuals(
		application,
		{"to_time": actual_time, "total_hours": hours},
	)


def _fill_actuals_from_existing_checkins(doc):
	"""Backfill exact times when an application is filed after check-ins."""
	if not doc.employee or not doc.attendance_date:
		return

	day = getdate(doc.attendance_date)
	checkin_meta = frappe.get_meta("Employee Checkin")
	fields = ["time", "log_type", "custom_attendance_type"]
	if checkin_meta.has_field("custom_ooo_application"):
		fields.append("custom_ooo_application")
	logs = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": doc.employee,
			"time": [
				"between",
				[f"{day} 00:00:00", f"{day} 23:59:59"],
			],
		},
		fields=fields,
		order_by="time asc",
	)

	if doc.doctype == "Late Entry Application":
		first_in = next(
			(
				log
				for log in logs
				if log.log_type == "IN"
				and (log.custom_attendance_type or "Normal") != "OOO Work"
			),
			None,
		)
		if first_in:
			doc.late_entry_time = _checkin_time(first_in)
		elif doc.is_new() or doc.status == "Draft":
			# Actual time is system-owned and must never come from the form.
			doc.late_entry_time = None
		return

	if doc.doctype != "Out of Office Application":
		return

	ooo_logs = [
		log
		for log in logs
		if (log.custom_attendance_type or "Normal") == "OOO Work"
		and (
			not getattr(log, "custom_ooo_application", None)
			or getattr(log, "custom_ooo_application", None) == doc.name
		)
	]
	start = next((log for log in ooo_logs if log.log_type == "IN"), None)
	end = next(
		(
			log
			for log in ooo_logs
			if log.log_type == "OUT"
			and (not start or get_datetime(log.time) > get_datetime(start.time))
		),
		None,
	)
	if start:
		doc.from_time = _checkin_time(start)
	elif doc.is_new() or doc.status == "Draft":
		doc.from_time = None
	if end:
		doc.to_time = _checkin_time(end)
	elif doc.is_new() or doc.status == "Draft":
		doc.to_time = None
	if doc.from_time and doc.to_time:
		doc.total_hours = flt(
			_hours_between(doc.to_time, doc.from_time), 2
		)
	elif doc.is_new() or doc.status == "Draft":
		doc.total_hours = 0


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

	if doc.status not in ("Approved", "Rejected"):
		frappe.throw(
			_("Only Approved or Rejected applications can be submitted. Current status: {0}").format(
				_(doc.status)
			)
		)


def _is_new(doc):
	"""Document.is_new(), or for a plain dict, whether it has no name yet."""
	is_new = getattr(doc, "is_new", None)
	return is_new() if callable(is_new) else not doc.get("name")


def _validate_cnr_application_deadline(doc):
	"""Block Late/Early/OOO apps filed after the configured attendance-date window."""
	if doc.doctype not in CNR_APPLICATION_DOCTYPES:
		return
	# The window limits when an employee may file, not when an approver may
	# decide: once the application exists, saving and submitting it stay open.
	if not _is_new(doc):
		return
	# Rejection is not a new filing — do not block it after the deadline.
	if _is_rejected_application(doc):
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
				"{0} cannot be filed for {1}. Applications must be filed within {2} day(s) "
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
	_validate_application_reason(doc)
	_fill_actuals_from_existing_checkins(doc)
	if (
		doc.doctype == "Late Entry Application"
		and doc.meta.has_field("estimated_late_entry_time")
		and not doc.estimated_late_entry_time
		and doc.late_entry_time
	):
		# Preserve existing applications created before estimated time was added.
		doc.estimated_late_entry_time = doc.late_entry_time
	_validate_cnr_application_deadline(doc)
	_validate_cnr_application_time_limit(doc)
	validate_cnr_approval_authority(doc)
	link_application_to_attendance(doc)


def on_submit_late_early_application(doc, method=None):
	if doc.status not in ("Approved", "Rejected"):
		frappe.throw(
			_("Only Approved or Rejected applications can be submitted. Current status: {0}").format(
				_(doc.status)
			)
		)
	if doc.status != "Approved":
		return

	link_application_to_attendance(doc)
	if doc.attendance:
		frappe.db.set_value(doc.doctype, doc.name, "attendance", doc.attendance)
	# Restore Present when Personal (<= max delay) / Office Work excuses the delay
	sync_attendance_after_application(doc)


def on_cancel_late_early_application(doc, method=None):
	sync_attendance_after_application(doc)


def validate_ooo_application(doc, method=None):
	_ensure_company(doc)
	_validate_application_reason(doc)
	_fill_actuals_from_existing_checkins(doc)
	if (
		doc.meta.has_field("estimated_from_time")
		and not doc.estimated_from_time
		and doc.from_time
	):
		doc.estimated_from_time = doc.from_time
	if (
		doc.meta.has_field("estimated_to_time")
		and not doc.estimated_to_time
		and doc.to_time
	):
		doc.estimated_to_time = doc.to_time
	validate_cnr_approval_authority(doc)

	if doc.from_time and doc.to_time:
		doc.total_hours = flt(_hours_between(doc.to_time, doc.from_time), 2)
		if doc.total_hours < 0:
			frappe.throw(_("To Time must be after From Time."))
	else:
		doc.total_hours = 0

	if doc.estimated_from_time and doc.estimated_to_time:
		estimated_hours = flt(
			_hours_between(
				doc.estimated_to_time, doc.estimated_from_time
			),
			2,
		)
		if estimated_hours < 0:
			frappe.throw(
				_("Estimated To Time must be after Estimated From Time.")
			)
	_validate_cnr_application_deadline(doc)
	_validate_cnr_application_time_limit(doc)

	if doc.total_hours:
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
	if doc.status not in ("Approved", "Rejected"):
		frappe.throw(
			_("Only Approved or Rejected applications can be submitted. Current status: {0}").format(
				_(doc.status)
			)
		)
	if doc.status != "Approved":
		return

	link_application_to_attendance(doc)
	if doc.attendance and flt(doc.total_hours) > 0:
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
	elif flt(doc.total_hours) > 0:
		set_attendance_ooo_hours(doc.employee, doc.attendance_date, hours=flt(doc.total_hours, 2))
	sync_attendance_after_application(doc)


def on_cancel_ooo_application(doc, method=None):
	sync_attendance_after_application(doc)
