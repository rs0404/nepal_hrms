# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Shift roster for the PWA's Leave tab: who works which shift on which day.

A day can carry more than one shift (two submitted, active Shift Assignments
that both cover it). A day with none falls back to the employee's default
shift, flagged so the app can tell a planned shift from the default. Holidays
and leave are included, since those are what the roster sits next to.
"""

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, getdate

MAX_DAYS = 62
DECIDED_OR_PENDING_LEAVE = ("Approved", "Open")


def _fmt_time(value):
	if value is None:
		return ""
	text = str(value)
	# timedelta renders as "9:30:00"; keep HH:MM.
	hours, _, rest = text.partition(":")
	return f"{int(hours):02d}:{rest[:2]}" if rest else text[:5]


def _employees_for(scope):
	from nepal_hrms.custom_code.approval_authority import LEAVE, SHIFT, approvable_employees

	me = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if scope != "team":
		if not me:
			frappe.throw(_("No Employee is linked to your user."))
		return [me]
	team = set(approvable_employees(kind=LEAVE)) | set(approvable_employees(kind=SHIFT))
	# Your own row first, then the team by name.
	names = sorted(team - {me}, key=lambda n: (frappe.db.get_value("Employee", n, "employee_name") or n))
	return ([me] if me else []) + names


@frappe.whitelist()
def has_team_roster():
	"""Whether the Team view has anyone in it for the current user."""
	from nepal_hrms.custom_code.approval_authority import LEAVE, SHIFT, approvable_employees

	return bool(approvable_employees(kind=LEAVE) or approvable_employees(kind=SHIFT))


@frappe.whitelist()
def get_shift_roster(from_date, to_date, scope="self"):
	from_date, to_date = getdate(from_date), getdate(to_date)
	if to_date < from_date:
		frappe.throw(_("To Date cannot be before From Date"))
	if date_diff(to_date, from_date) + 1 > MAX_DAYS:
		frappe.throw(_("Pick at most {0} days.").format(MAX_DAYS))

	employees = _employees_for(scope)
	days = [add_days(from_date, i) for i in range(date_diff(to_date, from_date) + 1)]
	info = {
		row.name: row
		for row in frappe.get_all(
			"Employee",
			filters={"name": ["in", employees]},
			fields=["name", "employee_name", "designation", "department", "default_shift", "holiday_list", "company"],
		)
	}

	assignments = frappe.get_all(
		"Shift Assignment",
		filters={
			"employee": ["in", employees],
			"docstatus": 1,
			"status": "Active",
			"start_date": ["<=", to_date],
		},
		or_filters=[["end_date", "is", "not set"], ["end_date", ">=", from_date]],
		fields=["employee", "shift_type", "start_date", "end_date"],
		order_by="start_date asc",
	)

	leaves = frappe.get_all(
		"Leave Application",
		filters={
			"employee": ["in", employees],
			"docstatus": ["<", 2],
			"status": ["in", DECIDED_OR_PENDING_LEAVE],
			"from_date": ["<=", to_date],
			"to_date": [">=", from_date],
		},
		fields=["employee", "leave_type", "from_date", "to_date", "half_day", "half_day_date", "status"],
	)

	holidays = _holidays(info, from_date, to_date)

	shift_names = {a.shift_type for a in assignments} | {e.default_shift for e in info.values() if e.default_shift}
	shift_types = {
		row.name: {
			"start": _fmt_time(row.start_time),
			"end": _fmt_time(row.end_time),
			"color": row.color or "",
		}
		for row in frappe.get_all(
			"Shift Type",
			filters={"name": ["in", list(shift_names) or [""]]},
			fields=["name", "start_time", "end_time", "color"],
		)
	}

	rows = []
	for employee in employees:
		emp = info.get(employee)
		if not emp:
			continue
		mine = [a for a in assignments if a.employee == employee]
		my_leaves = [l for l in leaves if l.employee == employee]
		my_holidays = holidays.get(employee, {})
		cells = {}
		for day in days:
			shifts = []
			for a in mine:
				if a.start_date <= day and (not a.end_date or a.end_date >= day) and a.shift_type not in shifts:
					shifts.append(a.shift_type)
			cell = {"shifts": shifts}
			if not shifts and emp.default_shift:
				cell["shifts"] = [emp.default_shift]
				cell["default"] = 1
			if day in my_holidays:
				cell["holiday"] = my_holidays[day]
			leave = next((l for l in my_leaves if l.from_date <= day <= l.to_date), None)
			if leave:
				cell["leave"] = {
					"leave_type": leave.leave_type,
					"status": "Approved" if leave.status == "Approved" else "Pending",
					"half_day": 1
					if leave.half_day and (not leave.half_day_date or getdate(leave.half_day_date) == day)
					else 0,
				}
			cells[str(day)] = cell
		rows.append(
			{
				"employee": employee,
				"employee_name": emp.employee_name,
				"designation": emp.designation or "",
				"cells": cells,
			}
		)

	return {
		"from_date": str(from_date),
		"to_date": str(to_date),
		"days": [str(d) for d in days],
		"shift_types": shift_types,
		"employees": rows,
	}


def _holidays(info, from_date, to_date):
	"""{employee: {date: {weekly_off, description}}}, one query per holiday list."""
	from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee

	from nepal_hrms.custom_code.attendance_holiday import holiday_description

	by_list = {}
	result = {}
	for employee in info:
		holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
		if not holiday_list:
			continue
		if holiday_list not in by_list:
			by_list[holiday_list] = {
				row.holiday_date: {
					"weekly_off": 1 if row.weekly_off else 0,
					"description": holiday_description(row.description),
				}
				for row in frappe.get_all(
					"Holiday",
					filters={"parent": holiday_list, "holiday_date": ["between", [from_date, to_date]]},
					fields=["holiday_date", "weekly_off", "description"],
				)
			}
		result[employee] = by_list[holiday_list]
	return result
