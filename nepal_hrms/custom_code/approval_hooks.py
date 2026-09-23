# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Approval checks for Leave Application, Shift Request and Compensatory Leave.

Late / Early / OOO and Attendance Request carry their own checks; all of them
share the rule in approval_authority.
"""

import frappe
from frappe import _
from frappe.utils import cint

from nepal_hrms.custom_code.approval_authority import LEAVE, SHIFT, assert_can_approve

DECISIONS = ("Approved", "Rejected")


def _decision_changed(doc):
	return doc.status in DECISIONS and (doc.is_new() or doc.has_value_changed("status"))


def _prevent_self_leave_approval():
	value = frappe.db.get_single_value("HR Settings", "prevent_self_leave_approval")
	return True if value is None else bool(cint(value))


def check_leave_application_approval(doc, on_submit=False):
	if doc.flags.ignore_permissions:
		return
	from frappe.model.workflow import get_workflow_name

	# A workflow decides who may move the state; it owns approval then.
	if get_workflow_name("Leave Application"):
		return
	if not on_submit and not _decision_changed(doc):
		return
	assert_can_approve(
		doc.employee,
		_("Leave Application"),
		kind=LEAVE,
		on_date=doc.from_date,
		site_allows_self=not _prevent_self_leave_approval(),
	)


def validate_shift_request_approval(doc, method=None):
	if doc.flags.ignore_permissions or not _decision_changed(doc):
		return
	assert_can_approve(doc.employee, _("Shift Request"), kind=SHIFT, on_date=doc.from_date)


def before_submit_shift_request(doc, method=None):
	if doc.flags.ignore_permissions:
		return
	assert_can_approve(doc.employee, _("Shift Request"), kind=SHIFT, on_date=doc.from_date)


def before_submit_compensatory_leave_request(doc, method=None):
	"""Submitting the request is what grants the leave, so it is the approval."""
	if doc.flags.ignore_permissions:
		return
	assert_can_approve(
		doc.employee,
		_("Compensatory Leave Request"),
		kind=LEAVE,
		on_date=doc.work_from_date,
	)
