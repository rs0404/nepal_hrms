import frappe
from frappe import _
from frappe.utils import format_date, get_link_to_form, getdate

from nepal_hrms.custom_code.attendance_policy import (
	_cnr_snapshot,
	_cnr_tracking_changed,
	apply_late_early_to_attendance,
	maybe_comment_cnr_attendance_change,
	sync_month_pool_penalties,
)


def _apply_and_flag_comment(doc):
	"""Apply C&R rules and stash a pending timeline comment if status/flags changed."""
	if doc.is_new():
		before = _cnr_snapshot(doc)
	else:
		before_doc = doc.get_doc_before_save()
		before = _cnr_snapshot(before_doc) if before_doc else _cnr_snapshot(doc)

	apply_late_early_to_attendance(doc, apply_unexcused_status=True)
	after = _cnr_snapshot(doc)

	if _cnr_tracking_changed(before, after):
		doc.flags.cnr_pending_comment = (before, after)


def _flush_cnr_comment(doc):
	pending = getattr(doc.flags, "cnr_pending_comment", None)
	if not pending or not doc.name:
		return
	before, after = pending
	doc.flags.cnr_pending_comment = None
	maybe_comment_cnr_attendance_change(
		doc.name,
		before,
		after,
		employee=doc.employee,
		attendance_date=doc.attendance_date,
	)


def validate_attendance(doc, method=None):
	"""Recompute late/early minutes, flags, and unexcused Half Day status."""
	_apply_and_flag_comment(doc)


def guard_duplicate_attendance(doc, method=None):
	"""Refuse a second submitted Attendance for one employee and date.

	HRMS inserts leave-driven Attendance with flags.ignore_validate set, which skips
	validate() and with it its own validate_duplicate_record(). A Leave Application
	whose lookup misses an existing row then inserts a second one, and both are
	counted -- a half-day leave billed twice. before_submit still runs, so the check
	belongs here where nothing can bypass it.
	"""
	if not doc.employee or not doc.attendance_date:
		return

	duplicate = frappe.db.get_value(
		"Attendance",
		{
			"employee": doc.employee,
			"attendance_date": getdate(doc.attendance_date),
			"docstatus": 1,
			"name": ["!=", doc.name],
		},
		"name",
	)
	if not duplicate:
		return

	frappe.throw(
		_("Attendance for {0} on {1} is already submitted: {2}").format(
			frappe.bold(doc.employee),
			frappe.bold(format_date(doc.attendance_date)),
			get_link_to_form("Attendance", duplicate),
		),
		title=_("Duplicate Attendance"),
	)


def before_submit_attendance(doc, method=None):
	"""Ensure C&R minutes/status are applied immediately before submit."""
	guard_duplicate_attendance(doc)
	# validate already applied; only re-apply if somehow skipped, avoid duplicate comments
	if getattr(doc.flags, "cnr_pending_comment", None) is None:
		_apply_and_flag_comment(doc)
	else:
		apply_late_early_to_attendance(doc, apply_unexcused_status=True)


def on_update_attendance(doc, method=None):
	"""Post C&R timeline comment after a successful save."""
	_flush_cnr_comment(doc)
	sync_month_pool_penalties(doc.employee, doc.attendance_date, current_name=doc.name)


def after_insert_attendance(doc, method=None):
	"""Post C&R timeline comment after first insert (new Attendance)."""
	_flush_cnr_comment(doc)
	sync_month_pool_penalties(doc.employee, doc.attendance_date, current_name=doc.name)
