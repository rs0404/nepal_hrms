# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""PWA helpers for Leave Application."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint


def _session_employee():
	return frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")


@frappe.whitelist()
def cancel_own_leave_application(name: str):
	"""Applicant can withdraw an Open (not yet approved) leave to correct it.

	Unsubmitted Open applications cannot use Frappe cancel (docstatus 2),
	and Employee typically has no Delete permission — so this deletes the draft.
	"""
	if not name:
		frappe.throw(_("Leave Application is required"))

	session_employee = _session_employee()
	if not session_employee:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	doc = frappe.get_doc("Leave Application", name)
	if doc.employee != session_employee:
		frappe.throw(_("You can only cancel your own leave application"))

	if cint(doc.docstatus) != 0:
		frappe.throw(_("Only leave applications waiting for approval can be cancelled"))

	if (doc.status or "Open") != "Open":
		frappe.throw(_("Only leave applications waiting for approval can be cancelled"))

	frappe.delete_doc("Leave Application", name, ignore_permissions=True, force=1)
	return {"ok": True, "name": name}
