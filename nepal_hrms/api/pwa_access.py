# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Settings-driven access control for BSHRMS PWA attendance features.

Role tables on Nepal HRMS Settings (PWA Access Control section):
  - pwa_live_board_roles        → who can see the Live Attendance Board
  - pwa_leave_board_roles       → who can see On Leave / Upcoming / Pending Leaves
  - pwa_calendar_history_roles  → who can pick past dates on Live Board / others' calendars
  - pwa_calendar_view_others_roles → who can view other employees' calendars

The tables are authoritative: an empty table means the feature is OFF for
everyone, except Leave Board which also grants access to Live Attendance Board
roles. (The Administrator user matches any configured role automatically.)
"""

import frappe
from frappe import _

SETTINGS_DOCTYPE = "Nepal HRMS Settings"
ROLE_CHILD_DOCTYPE = "Nepal HRMS Role"


def _settings_roles(fieldname):
	"""Roles configured in a settings role-table field (empty set if none)."""
	if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
		return set()
	rows = frappe.get_all(
		ROLE_CHILD_DOCTYPE,
		filters={"parent": SETTINGS_DOCTYPE, "parentfield": fieldname},
		pluck="role",
	)
	return {r for r in rows if r}


def _user_roles(user=None):
	return set(frappe.get_roles(user or frappe.session.user))


def _role_allowed(fieldname, user=None):
	"""True if the user has a role listed in the settings table (empty = off).

	Administrator always matches when the table is non-empty.
	"""
	allowed = _settings_roles(fieldname)
	if not allowed:
		return False
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(_user_roles(user) & allowed)


def can_view_live_board(user=None):
	"""Live Attendance Board access — only roles listed in settings."""
	return _role_allowed("pwa_live_board_roles", user)


def can_view_leave_board(user=None):
	"""On Leave / Upcoming / Pending Leaves board on the PWA Leaves tab.

	Dedicated Leave Board roles, or anyone already allowed on the Live
	Attendance Board (same company-wide leave lists).
	"""
	if _role_allowed("pwa_leave_board_roles", user):
		return True
	return can_view_live_board(user)


def can_view_past_attendance(user=None):
	"""May pick past dates on Live Board, and browse past months of *others*.

	Own attendance calendar is always allowed to go back; this flag does not
	restrict self-view.
	"""
	return _role_allowed("pwa_calendar_history_roles", user)


def can_view_others_calendar(user=None):
	"""May view other employees' attendance calendar — only listed roles."""
	return _role_allowed("pwa_calendar_view_others_roles", user)


def can_read_employee_attendance(employee, user=None):
	"""Self, HR, or a user with View Others' Calendar may read this employee's attendance."""
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	session_employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if employee and employee == session_employee:
		return True
	if can_view_others_calendar(user):
		return True
	roles = _user_roles(user)
	return bool(roles & {"HR Manager", "HR User", "System Manager"})


def resolve_calendar_employee(employee=None, user=None):
	"""Return the employee whose calendar may be shown to this user.

	Defaults to the session employee. A different employee requires the
	view-others-calendar permission.
	"""
	user = user or frappe.session.user
	session_employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee or employee == session_employee:
		return session_employee
	if not can_view_others_calendar(user):
		frappe.throw(
			_("You are not allowed to view other employees' attendance"),
			frappe.PermissionError,
		)
	if not frappe.db.exists("Employee", employee):
		frappe.throw(_("Employee {0} not found").format(employee))
	return employee


@frappe.whitelist()
def get_pwa_access_permissions():
	"""Single call the PWA makes on load to gate attendance UI features."""
	user = frappe.session.user
	session_employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	return {
		"can_view_live_board": can_view_live_board(user),
		"can_view_leave_board": can_view_leave_board(user),
		"can_view_past_attendance": can_view_past_attendance(user),
		"can_view_others_calendar": can_view_others_calendar(user),
		"session_employee": session_employee,
	}


@frappe.whitelist()
def get_calendar_viewable_employees(search_text=None):
	"""Active employees for the PWA calendar employee picker.

	Only available to users with the view-others-calendar permission;
	returns label/value pairs for the Autocomplete.
	"""
	if not can_view_others_calendar():
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	filters = {"status": "Active"}
	or_filters = None
	if search_text:
		like = f"%{search_text}%"
		or_filters = {"name": ["like", like], "employee_name": ["like", like]}

	rows = frappe.get_all(
		"Employee",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "employee_name", "department"],
		order_by="employee_name asc",
		limit_page_length=50,
	)
	return [
		{
			"label": f"{r.employee_name} : {r.name}" if r.employee_name else r.name,
			"value": r.name,
			"department": r.department,
		}
		for r in rows
	]


@frappe.whitelist()
def get_pwa_live_attendance(attendance_date=None):
	"""Live Attendance Board payload for BSHRMS, gated by PWA Access Control."""
	if not can_view_live_board() and not can_view_leave_board():
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	from nepal_hrms.nepal_hrms.page.live_attendance_boar_1.live_attendance_boar_1 import (
		get_live_data,
	)

	data = get_live_data(attendance_date)
	if can_view_live_board():
		return data

	# Leave-board-only: keep leave columns, drop check-in columns
	return {
		"today_bs": data.get("today_bs"),
		"attendance_date": data.get("attendance_date"),
		"is_today": data.get("is_today"),
		"pending": {},
		"active": {},
		"completed": {},
		"leave": data.get("leave") or {},
		"upcoming": data.get("upcoming") or {},
		"pending_leave": data.get("pending_leave") or {},
		"leave_board_only": True,
	}
