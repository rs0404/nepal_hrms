# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""The PWA's team approval queue, and the two steps that clear it.

Deciding and submitting are separate on purpose: Approve or Reject only sets
the status, and Submit makes it final. Until then the request stays in the
queue, so a wrong tap can still be changed.

The queue is split by whose desk the request landed on: requests whose
designated approver is the user, and requests that reach the user only because
the approver reports to them. Authority is approval_authority's either way,
and is checked here, so someone higher up the chain needs no document
permission to act.
"""

import frappe
from frappe import _
from frappe.utils import cint

from nepal_hrms.custom_code.approval_authority import (
	LEAVE,
	SHIFT,
	_same_user,
	approvable_employees,
	designated_approver,
)

CNR_DOCTYPES = ("Late Entry Application", "Early Exit Application", "Out of Office Application")
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
	"owner",
	"estimated_late_entry_time",
	"estimated_from_time",
	"estimated_to_time",
	"late_entry_time",
	"early_exit_time",
	"from_time",
	"to_time",
	"total_hours",
]

# undecided: the status a request is filed with. decided: statuses that may be
# submitted. A rejected Attendance Request is final as a draft -- it has no
# attendance to create -- so it never waits for Submit.
SPECS = {
	"Leave Application": {
		"kind": LEAVE,
		"date": "from_date",
		"undecided": "Open",
		"decided": ("Approved", "Rejected"),
		"fields": [
			"name",
			"posting_date",
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
	},
	"Attendance Request": {
		"kind": LEAVE,
		"date": "from_date",
		"undecided": "Open",
		"decided": ("Approved",),
		"fields": [
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
			"modified",
			"status",
			"custom_rejection_reason",
			"explanation",
			"owner",
		],
	},
	"Shift Request": {
		"kind": SHIFT,
		"date": "from_date",
		"undecided": "Draft",
		"decided": ("Approved", "Rejected"),
		"fields": [
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
	},
	**{
		doctype: {
			"kind": LEAVE,
			"date": "attendance_date",
			"undecided": "Draft",
			"decided": ("Approved", "Rejected"),
			"fields": CNR_FIELDS,
		}
		for doctype in CNR_DOCTYPES
	},
}


def _spec(doctype):
	spec = SPECS.get(doctype)
	if not spec:
		frappe.throw(_("{0} is not approved from here.").format(doctype))
	return spec


def _can_decide(doc):
	"""The approval rule each doctype already enforces, including its self-approval setting."""
	if doc.doctype == "Attendance Request":
		from nepal_hrms.overrides.attendance_request import _can_approve_attendance_request

		return _can_approve_attendance_request(doc.employee, doc.from_date)
	if doc.doctype in CNR_DOCTYPES:
		from nepal_hrms.custom_code.application_hooks import can_approve_cnr_application

		return can_approve_cnr_application(doc.employee, doc.attendance_date)

	from nepal_hrms.custom_code.approval_authority import can_approve

	if doc.doctype == "Leave Application":
		from nepal_hrms.custom_code.approval_hooks import _prevent_self_leave_approval

		return can_approve(
			doc.employee, LEAVE, doc.from_date, site_allows_self=not _prevent_self_leave_approval()
		)
	return can_approve(doc.employee, SHIFT, doc.from_date)


def _assert_can_decide(doc):
	if not _can_decide(doc):
		frappe.throw(
			_("Only {0}'s approver, or someone above them in Reports To, can do this.").format(
				doc.get("employee_name") or doc.employee
			),
			frappe.PermissionError,
		)


@frappe.whitelist()
def get_team_pending_requests(limit=50):
	"""Undecided and decided-but-unsubmitted requests the user may act on.

	Each row carries assigned_to_me (the user is its designated approver) and
	awaiting_submit (decided, Submit still to come).
	"""
	user = frappe.session.user
	limit = cint(limit) or 50
	team = {kind: approvable_employees(user, kind) for kind in (LEAVE, SHIFT)}
	approver_of = {}

	rows = []
	for doctype, spec in SPECS.items():
		employees = team[spec["kind"]]
		if not employees or not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		statuses = [spec["undecided"], *spec["decided"]]
		# The queue is narrowed to the user's own team above, and someone higher
		# up the chain may hold no permission on these documents.
		for row in frappe.get_all(
			doctype,
			filters={"docstatus": 0, "status": ["in", statuses], "employee": ["in", employees]},
			fields=[f for f in spec["fields"] if f in ("name", "docstatus", "creation", "modified") or meta.has_field(f)],
			order_by="modified desc",
			limit_page_length=limit,
		):
			key = (row.employee, spec["kind"])
			if key not in approver_of:
				approver_of[key] = designated_approver(row.employee, spec["kind"])
			row.doctype = doctype
			row.assigned_to_me = _same_user(approver_of[key], user)
			row.awaiting_submit = row.status in spec["decided"]
			rows.append(row)
	return rows


@frappe.whitelist()
def can_decide_team_request(doctype, name):
	_spec(doctype)
	return bool(_can_decide(frappe.get_doc(doctype, name)))


@frappe.whitelist(methods=["POST"])
def decide_team_request(doctype, name, status, rejection_reason=None):
	"""Step one: set Approved or Rejected. Nothing is final until Submit.

	A request that is still a draft may be decided again, which is how a wrong
	tap is put right.
	"""
	spec = _spec(doctype)
	status = (status or "").strip()
	if status not in ("Approved", "Rejected"):
		frappe.throw(_("Invalid status"))

	doc = frappe.get_doc(doctype, name)
	_assert_can_decide(doc)
	if doc.docstatus != 0:
		frappe.throw(_("This request is already submitted."))

	reason = (rejection_reason or "").strip()
	if status == "Rejected" and not reason:
		frappe.throw(_("Rejection Reason is required"))

	doc.status = status
	if doc.meta.has_field("custom_rejection_reason"):
		doc.custom_rejection_reason = reason if status == "Rejected" else None
	doc.flags.ignore_permissions = True
	doc.save()
	if status == "Rejected" and not doc.meta.has_field("custom_rejection_reason"):
		doc.add_comment("Comment", _("Rejected: {0}").format(reason))
	return {"name": doc.name, "status": doc.status, "awaiting_submit": status in spec["decided"]}


@frappe.whitelist(methods=["POST"])
def submit_team_request(doctype, name):
	"""Step two: submit a decided request."""
	spec = _spec(doctype)
	doc = frappe.get_doc(doctype, name)
	_assert_can_decide(doc)
	if doc.docstatus != 0:
		frappe.throw(_("This request is already submitted."))
	if doc.status not in spec["decided"]:
		frappe.throw(_("Approve or reject this request before submitting it."))

	doc.flags.ignore_permissions = True
	doc.submit()
	return {"name": doc.name, "status": doc.status, "docstatus": doc.docstatus}


ATTENDANCE_FIELDS = (
	"name",
	"attendance_date",
	"status",
	"half_day_status",
	"in_time",
	"out_time",
	"working_hours",
	"shift",
	"leave_type",
	"late_entry",
	"early_exit",
	"custom_late_mins",
	"custom_early_mins",
	"docstatus",
)
CHECKIN_FIELDS = ("time", "log_type", "custom_attendance_type", "custom_reason", "device_id")
MAX_EVIDENCE_DAYS = 31


@frappe.whitelist()
def get_attendance_request_evidence(name):
	"""What already happened on each day an Attendance Request asks about.

	The attendance record (if any) and every check-in, so the approver can see
	whether the request is needed and what it would correct, without leaving
	the request.
	"""
	from frappe.utils import add_days, date_diff, getdate

	from nepal_hrms.custom_code.approval_authority import is_own

	doc = frappe.get_doc("Attendance Request", name)
	hr = set(frappe.get_roles()) & {"HR Manager", "HR User", "System Manager"}
	if not (hr or is_own(doc.employee) or _can_decide(doc)):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	start = getdate(doc.from_date)
	end = getdate(doc.to_date)
	if date_diff(end, start) >= MAX_EVIDENCE_DAYS:
		end = add_days(start, MAX_EVIDENCE_DAYS - 1)

	att_meta = frappe.get_meta("Attendance")
	attendance = {
		getdate(row.attendance_date): row
		for row in frappe.get_all(
			"Attendance",
			filters={
				"employee": doc.employee,
				"attendance_date": ["between", [start, end]],
				"docstatus": ["<", 2],
			},
			fields=[f for f in ATTENDANCE_FIELDS if f in ("name", "docstatus") or att_meta.has_field(f)],
			order_by="docstatus desc",
		)
	}
	checkin_meta = frappe.get_meta("Employee Checkin")
	checkins = {}
	for row in frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": doc.employee,
			"time": ["between", [f"{start} 00:00:00", f"{end} 23:59:59"]],
		},
		fields=[f for f in CHECKIN_FIELDS if f == "time" or checkin_meta.has_field(f)],
		order_by="time asc",
	):
		checkins.setdefault(getdate(row.time), []).append(row)

	days = []
	day = start
	while day <= end:
		days.append({"date": str(day), "attendance": attendance.get(day), "checkins": checkins.get(day, [])})
		day = add_days(day, 1)
	return days
