# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Shift roster for the PWA's Leave tab: who works which shift on which day.

The roster pages by payroll period, the same windows salary is worked out on.

A day can carry more than one shift (two submitted, active Shift Assignments
that both cover it). A day with none falls back to the employee's default
shift, flagged so the app can tell a planned shift from the default.

On a holiday or weekly off nobody is rostered by default: an open-ended or
multi-day assignment does not put anyone to work on it. Only an assignment made
for that day alone (holiday duty) shows there.

Pending Shift Requests are included so an employee sees what they have asked
for before it is approved.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, getdate, today

MAX_SHIFTS_PER_REQUEST = 2

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


def payroll_period(offset=0):
	"""(from_date, to_date) of the payroll period `offset` periods from today's."""
	from frappe.utils import add_months, get_first_day, get_last_day

	from nepal_hrms.custom_code.payroll.period import get_settings, period_containing

	offset = cint(offset)
	settings = get_settings()
	start, end, _days = period_containing(today(), settings)
	if not start:
		# No BS calendar to name periods by: fall back to AD months.
		month = add_months(today(), offset)
		return getdate(get_first_day(month)), getdate(get_last_day(month))
	for _i in range(abs(offset)):
		anchor = add_days(end, 1) if offset > 0 else add_days(start, -1)
		start, end, _days = period_containing(anchor, settings)
	return getdate(start), getdate(end)


@frappe.whitelist()
def get_shift_roster(from_date=None, to_date=None, scope="self", period_offset=0):
	if not (from_date and to_date):
		from_date, to_date = payroll_period(period_offset)
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

	pending = frappe.get_all(
		"Shift Request",
		filters={
			"employee": ["in", employees],
			"docstatus": 0,
			"status": "Draft",
			"from_date": ["<=", to_date],
		},
		or_filters=[["to_date", "is", "not set"], ["to_date", ">=", from_date]],
		fields=["name", "employee", "shift_type", "from_date", "to_date"],
	)

	shift_names = (
		{a.shift_type for a in assignments}
		| {e.default_shift for e in info.values() if e.default_shift}
		| {p.shift_type for p in pending}
	)
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
		my_pending = [p for p in pending if p.employee == employee]
		my_leaves = [l for l in leaves if l.employee == employee]
		my_holidays = holidays.get(employee, {})
		cells = {}
		for day in days:
			is_holiday = day in my_holidays
			shifts = []
			for a in mine:
				covers = a.start_date <= day and (not a.end_date or a.end_date >= day)
				# A holiday is off unless this assignment was made for that day alone.
				if is_holiday and not (a.start_date == day and a.end_date == day):
					covers = False
				if covers and a.shift_type not in shifts:
					shifts.append(a.shift_type)
			cell = {"shifts": shifts}
			if not shifts and emp.default_shift and not is_holiday:
				cell["shifts"] = [emp.default_shift]
				cell["default"] = 1
			requested = [
				p.shift_type
				for p in my_pending
				if p.from_date <= day and (not p.to_date or p.to_date >= day) and p.shift_type not in shifts
			]
			if requested:
				cell["requested"] = requested
			if is_holiday:
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
		"period_offset": cint(period_offset),
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


def configured_frequent_shift_types():
	if not frappe.db.exists("DocType", "Nepal HRMS Frequent Shift Type"):
		return []
	return frappe.get_all(
		"Nepal HRMS Frequent Shift Type",
		filters={"parent": "Nepal HRMS Settings", "parentfield": "frequent_shift_types"},
		pluck="shift_type",
		order_by="idx asc",
	)


@frappe.whitelist()
def get_frequent_shift_types():
	"""The shifts Nepal HRMS Settings lists as quick choices, with their times and colour."""
	names = configured_frequent_shift_types()
	if not names:
		return []
	rows = {
		row.name: row
		for row in frappe.get_all(
			"Shift Type",
			filters={"name": ["in", names]},
			fields=["name", "start_time", "end_time", "color"],
		)
	}
	return [
		{
			"shift_type": name,
			"start": _fmt_time(rows[name].start_time),
			"end": _fmt_time(rows[name].end_time),
			"color": rows[name].color or "",
		}
		for name in names
		if name in rows
	]


@frappe.whitelist(methods=["POST"])
def request_shifts(shift_types, from_date, to_date=None):
	"""Raise one Shift Request per chosen shift (at most two) for the session employee.

	Two shifts for the same day are allowed as long as their timings do not
	overlap; Frappe HR's own overlap check refuses the second otherwise, and
	the whole call is rolled back with it.
	"""
	from nepal_hrms.custom_code.approval_authority import SHIFT, designated_approver

	if isinstance(shift_types, str):
		shift_types = json.loads(shift_types) if shift_types.strip().startswith("[") else [shift_types]
	shift_types = list(dict.fromkeys(s for s in shift_types if s))
	if not shift_types:
		frappe.throw(_("Pick a shift."))
	if len(shift_types) > MAX_SHIFTS_PER_REQUEST:
		frappe.throw(_("Pick at most {0} shifts for a day.").format(MAX_SHIFTS_PER_REQUEST))

	employee = frappe.db.get_value(
		"Employee", {"user_id": frappe.session.user}, ["name", "company"], as_dict=True
	)
	if not employee:
		frappe.throw(_("No Employee is linked to your user."))
	approver = designated_approver(employee.name, SHIFT)
	if not approver:
		frappe.throw(_("No shift approver is set for you. Ask HR to set one."))

	created = []
	for shift_type in shift_types:
		doc = frappe.get_doc(
			{
				"doctype": "Shift Request",
				"employee": employee.name,
				"company": employee.company,
				"shift_type": shift_type,
				"from_date": getdate(from_date),
				"to_date": getdate(to_date or from_date),
				"approver": approver,
				"status": "Draft",
			}
		)
		doc.insert()
		created.append(doc.name)
	return {"created": created}

