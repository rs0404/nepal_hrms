# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""BSHRMS PWA delivery for the predefined attendance events.

Raven and the PWA are two channels over one event list. A row in Nepal HRMS
Settings decides whether an event fires and who hears it; this module turns the
rows marked Send to PWA into PWA Notification records. HRMS pushes those to the
device itself on after_insert, so nothing here talks to a browser.

Leave Application is deliberately absent: hrms.mixins.pwa_notifications already
notifies its approver and applicant, and doing it again here would double every
leave notification on the device.
"""

import re

import frappe
from frappe.utils import cint

from nepal_hrms.notifications.events import EVENT_BY_KEY

# after_insert: the application has been raised and wants an approver's eyes.
EVENT_ON_NEW = {
	"Late Entry Application": "late_entry_app_new",
	"Early Exit Application": "early_exit_app_new",
	"Out of Office Application": "ooo_app_new",
}

# on_submit: approval and rejection are both final here -- set_cnr_application_approval
# writes the status and submits in one go, so submit is the moment it is decided.
EVENT_ON_SUBMIT = {
	"Late Entry Application": "late_entry_app_submit",
	"Early Exit Application": "early_exit_app_submit",
	"Out of Office Application": "ooo_app_submit",
}

ATTENDANCE_EVENT_BY_STATUS = {
	"Absent": "attendance_absent",
	"Half Day": "attendance_half_day",
	"Present": "attendance_present",
	"On Leave": "attendance_on_leave",
	"Work From Home": "attendance_wfh",
}


def _pwa_enabled(settings):
	"""Master switch, off until switched on.

	A field default only applies to documents created afterwards, and every site
	already has this Singleton -- so a default of 1 would still read 0 here and
	look broken. Opt-in avoids that entirely: absent and unticked mean the same
	thing, and there is one box to turn the feature on.
	"""
	return bool(cint(settings.get("enable_pwa_notifications") or 0))


def _settings_row(event_key):
	"""The Nepal HRMS Settings row for this event, or None when it is off."""
	try:
		settings = frappe.get_cached_doc("Nepal HRMS Settings")
	except Exception:
		return None

	if not _pwa_enabled(settings):
		return None

	for row in settings.get("raven_notifications") or []:
		if row.event_key != event_key:
			continue
		if not cint(row.get("enabled")):
			return None
		# A site that has not synced the field yet simply sends nothing to the
		# PWA, rather than erroring on every attendance submit.
		if not cint(row.get("send_to_pwa") or 0):
			return None
		return row
	return None


def _employee_user(employee):
	return frappe.db.get_value("Employee", employee, "user_id") if employee else None


def _reports_to_user(employee):
	manager = frappe.db.get_value("Employee", employee, "reports_to") if employee else None
	return _employee_user(manager)


def _approver_user(doc):
	"""Document field first, then the employee's leave approver -- as Raven does."""
	approver = doc.get("leave_approver") if doc.meta.has_field("leave_approver") else None
	if approver:
		return approver
	return frappe.db.get_value("Employee", doc.employee, "leave_approver") if doc.employee else None


def _recipients(doc, row):
	"""Users to notify, deduplicated, per this row's Employee/Reports To/Approver."""
	users = []
	if cint(row.get("send_to_employee")):
		users.append(_employee_user(doc.employee))
	if cint(row.get("send_to_reports_to")):
		users.append(_reports_to_user(doc.employee))
	if cint(row.get("send_to_approver")):
		users.append(_approver_user(doc))

	seen = set()
	out = []
	for user in users:
		if not user or user in seen or user == "Administrator":
			continue
		seen.add(user)
		out.append(user)
	return out


def _render(event, doc, override=None):
	"""Event template, rendered. Raven writes **bold**; the PWA renders HTML."""
	template = (override or "").strip() or event.get("message") or ""
	if not template:
		return ""
	try:
		text = frappe.render_template(template, {"doc": doc})
	except Exception:
		# A bad override must not stop a document from saving.
		frappe.log_error(frappe.get_traceback(), "Nepal PWA notification render failed")
		return ""
	return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def notify(event_key, doc):
	"""Create one PWA Notification per recipient for this event."""
	event = EVENT_BY_KEY.get(event_key)
	if not event:
		return 0

	row = _settings_row(event_key)
	if not row:
		return 0

	message = _render(event, doc, row.get("message"))
	if not message:
		return 0

	from_user = frappe.session.user
	sent = 0
	for to_user in _recipients(doc, row):
		# The person who acted already knows; HRMS skips this case too.
		if to_user == from_user:
			continue
		frappe.get_doc(
			{
				"doctype": "PWA Notification",
				"from_user": from_user,
				"to_user": to_user,
				"message": message,
				"reference_document_type": doc.doctype,
				"reference_document_name": doc.name,
			}
		).insert(ignore_permissions=True)
		sent += 1
	return sent


def _guard(fn):
	"""A notification must never be the reason a document fails to save."""

	def wrapper(doc, method=None):
		try:
			return fn(doc)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Nepal PWA notification failed")

	return wrapper


@_guard
def notify_application_created(doc):
	"""New application -> the approver, so it does not sit unseen."""
	key = EVENT_ON_NEW.get(doc.doctype)
	return notify(key, doc) if key else 0


@_guard
def notify_application_decided(doc):
	"""Approved or rejected -> the employee who raised it."""
	key = EVENT_ON_SUBMIT.get(doc.doctype)
	return notify(key, doc) if key else 0


@_guard
def notify_attendance(doc):
	"""Attendance submitted. Absent is the one that matters; the rest are opt-in."""
	key = ATTENDANCE_EVENT_BY_STATUS.get(doc.status or "")
	return notify(key, doc) if key else 0
