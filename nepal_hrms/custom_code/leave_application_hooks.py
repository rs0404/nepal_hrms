# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import add_days, cint, format_date, getdate, today

from nepal_hrms.custom_code.attendance_holiday import get_adjacent_working_day, is_holiday_or_weekend
from nepal_hrms.custom_code.sandwich_leave import evaluate_leave_sandwich


def validate_leave_application_reason(doc, method=None):
	if not (doc.description or "").strip():
		frappe.throw(_("Reason is required."))


def validate_half_day_session(doc, method=None):
	"""A new half-day leave must say which half it takes off.

	Only a draft is held to it. A leave already submitted before the field
	existed has none, and refusing its edits would strand it; attendance works
	its half out from the check-in time instead. Unticking Half Day clears the
	choice, so a whole-day leave never carries a stale half.
	"""
	from nepal_hrms.custom_code.half_day import SESSION_FIELD, SESSIONS

	if not doc.meta.has_field(SESSION_FIELD):
		return
	if not cint(doc.get("half_day")):
		if doc.get(SESSION_FIELD):
			doc.set(SESSION_FIELD, None)
		return
	if doc.docstatus != 0 or doc.get(SESSION_FIELD) in SESSIONS:
		return
	day = doc.get("half_day_date") or doc.get("from_date")
	frappe.throw(
		_("Choose which half of {0} you are taking off: First Half or Second Half.").format(
			format_date(day) if day else _("the half day")
		),
		title=_("Half Day Session Required"),
	)


def exempt_leave_types(settings):
	"""Leave types the submission deadline does not apply to."""
	rows = getattr(settings, "leave_types_exempt_from_deadline", None) or []
	names = set()
	for row in rows:
		# get_singles_dict hands back plain dicts; a loaded Single hands back rows.
		leave_type = row.get("leave_type") if isinstance(row, dict) else getattr(row, "leave_type", None)
		if leave_type:
			names.add(leave_type)
	return names


def _is_new(doc):
	"""Document.is_new(), or for a plain dict, whether it has no name yet."""
	is_new = getattr(doc, "is_new", None)
	return is_new() if callable(is_new) else not doc.get("name")


def validate_leave_application_deadline(doc, method=None):
	"""Block back-dated leave once the window has passed, bar the exempt types.

	Sickness is not known in advance, so a site can keep specific types open while
	everything else has to be filed within the configured days of the leave ending.
	"""
	from nepal_hrms.custom_code.attendance_policy import get_hr_settings

	if doc.docstatus == 2 or (doc.status or "") == "Cancelled":
		return
	# Filing is what the window limits. An approver deciding an application that
	# already exists is not held to it.
	if not _is_new(doc):
		return
	if not doc.to_date:
		return

	settings = get_hr_settings()
	if not cint(getattr(settings, "enable_leave_application_deadline", 0) or 0):
		return
	if doc.leave_type in exempt_leave_types(settings):
		return

	from nepal_hrms.custom_code.policy_escape import has_policy_escape

	if doc.employee and has_policy_escape(doc.employee, "escape_applications", doc.to_date):
		return

	max_days = max(cint(getattr(settings, "late_early_application_max_days", None) or 2), 0)
	deadline = add_days(getdate(doc.to_date), max_days)
	if getdate(today()) <= deadline:
		return

	frappe.throw(
		_(
			"{0} leave ending {1} cannot be filed now. It had to be submitted within "
			"{2} day(s) of that date (deadline was {3}). Ask HR to add {0} to the "
			"exempt leave types if it should stay open."
		).format(
			doc.leave_type,
			format_date(doc.to_date),
			max_days,
			format_date(deadline),
		),
		title=_("Leave Submission Deadline Passed"),
	)


def validate_leave_balance_including_drafts(doc, method=None):
	from nepal_hrms.api.leave_application import validate_document_leave_balance

	validate_document_leave_balance(doc)


def validate_sandwich_leave_application(doc, method):
	from nepal_hrms.custom_code.attendance_policy import get_hr_settings

	settings = get_hr_settings()
	if not settings.enable_leave_sandwich_rule:
		return

	from nepal_hrms.custom_code.policy_escape import has_policy_escape

	if doc.employee and has_policy_escape(
		doc.employee, "escape_sandwich", doc.from_date or None
	):
		return

	if doc.half_day:
		frappe.msgprint(
			_(
				"Notice: Half-day leave before/after holidays prevents immediate sandwiching, but if you are absent for the full day on the adjacent working day, Sandwich Rule will consider intervening holidays as Leave/Absent."
			),
			alert=True,
			indicator="orange",
		)
		return

	if not doc.employee or not doc.from_date or not doc.to_date:
		return

	result = evaluate_leave_sandwich(
		doc.employee, getdate(doc.from_date), getdate(doc.to_date), current_leave=doc
	)

	if result["violation"]:
		if settings.block_sandwich_leave_application:
			frappe.throw(result["message"])
		frappe.msgprint(result["message"], alert=True, indicator="orange")
	elif result["warning"]:
		frappe.msgprint(result["warning_message"], alert=True, indicator="orange")


def has_leave_or_absent(employee, date_obj, current_leave_name=None):
	"""Legacy helper: submitted Leave Application covering the date."""
	filters = {
		"employee": employee,
		"docstatus": 1,
		"from_date": ["<=", date_obj],
		"to_date": [">=", date_obj],
	}
	if current_leave_name:
		filters["name"] = ["!=", current_leave_name]

	return bool(frappe.db.exists("Leave Application", filters))
