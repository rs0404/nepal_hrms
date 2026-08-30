# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

from nepal_hrms.custom_code.attendance_policy import (
	_cnr_snapshot,
	_cnr_tracking_changed,
	apply_late_early_to_attendance,
	maybe_comment_cnr_attendance_change,
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


def before_submit_attendance(doc, method=None):
	"""Ensure C&R minutes/status are applied immediately before submit."""
	# validate already applied; only re-apply if somehow skipped, avoid duplicate comments
	if getattr(doc.flags, "cnr_pending_comment", None) is None:
		_apply_and_flag_comment(doc)
	else:
		apply_late_early_to_attendance(doc, apply_unexcused_status=True)


def on_update_attendance(doc, method=None):
	"""Post C&R timeline comment after a successful save."""
	_flush_cnr_comment(doc)


def after_insert_attendance(doc, method=None):
	"""Post C&R timeline comment after first insert (new Attendance)."""
	_flush_cnr_comment(doc)
