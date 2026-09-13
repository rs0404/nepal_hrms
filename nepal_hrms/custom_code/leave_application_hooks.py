# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import getdate

from nepal_hrms.custom_code.attendance_holiday import get_adjacent_working_day, is_holiday_or_weekend
from nepal_hrms.custom_code.sandwich_leave import evaluate_leave_sandwich


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
