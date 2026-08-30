# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Rich attendance calendar payload for bshrms (status + leave / late / early markers)."""

import frappe
from frappe.utils import add_days, cint, date_diff, getdate

from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee


@frappe.whitelist()
def get_leave_application_counts(employee=None, from_date=None, to_date=None):
	"""Approved / rejected / pending Leave Application counts overlapping a date range."""
	from frappe import _
	from frappe.utils import flt, get_first_day, get_last_day, getdate, today

	if not employee:
		employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		frappe.throw(_("Employee not found"))

	roles = frappe.get_roles()
	if not ({"HR Manager", "HR User", "System Manager"} & set(roles)):
		session_emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		if employee != session_emp:
			frappe.throw(_("Not permitted"), frappe.PermissionError)

	start = getdate(from_date) if from_date else get_first_day(getdate(today()))
	end = getdate(to_date) if to_date else get_last_day(getdate(today()))

	rows = frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"docstatus": ["<", 2],
			"from_date": ["<=", end],
			"to_date": [">=", start],
		},
		fields=["name", "status", "docstatus", "total_leave_days", "from_date", "to_date"],
	)

	approved = rejected = pending = 0
	days = 0.0
	for r in rows:
		if r.docstatus == 1 and r.status == "Approved":
			approved += 1
			days += flt(r.total_leave_days)
		elif r.status == "Rejected" or (r.docstatus == 1 and r.status == "Rejected"):
			rejected += 1
		elif r.docstatus == 0 or r.status in ("Open", "Draft"):
			pending += 1
		elif r.status == "Cancelled":
			continue
		else:
			# Submitted but not approved/rejected — treat by status string
			if r.status == "Approved":
				approved += 1
				days += flt(r.total_leave_days)
			elif r.status == "Rejected":
				rejected += 1
			else:
				pending += 1

	return {
		"total": approved + rejected + pending,
		"approved": approved,
		"rejected": rejected,
		"pending": pending,
		"days": round(days, 1),
		"from_date": str(start),
		"to_date": str(end),
	}


@frappe.whitelist()
def get_attendance_calendar_details(from_date: str, to_date: str) -> dict:
	"""
	Return per-day calendar details for the logged-in employee.

	Shape:
	  {
	    "YYYY-MM-DD": {
	      "status": "Present" | "Absent" | ... | "Holiday",
	      "leave": 0|1,
	      "late": 0|1,   # minor late day (occurrence)
	      "early": 0|1,  # minor early day (occurrence)
	      "leave_type": str | None,
	    },
	    ...
	  }
	"""
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		return {}

	from_date = getdate(from_date)
	to_date = getdate(to_date)

	attendance_rows = frappe.get_all(
		"Attendance",
		filters={
			"employee": employee,
			"attendance_date": ["between", [from_date, to_date]],
			"docstatus": ["<", 2],
		},
		fields=[
			"attendance_date",
			"status",
			"leave_type",
			"custom_cnr_late_in_pool",
			"custom_cnr_early_in_pool",
		],
	)

	att_by_date = {}
	meta = frappe.get_meta("Attendance")
	has_late = meta.has_field("custom_cnr_late_in_pool")
	has_early = meta.has_field("custom_cnr_early_in_pool")

	for row in attendance_rows:
		d = getdate(row.attendance_date)
		att_by_date[d] = {
			"status": row.status,
			"leave": 1 if (row.status == "On Leave" or row.leave_type) else 0,
			"late": cint(row.custom_cnr_late_in_pool) if has_late else 0,
			"early": cint(row.custom_cnr_early_in_pool) if has_early else 0,
			"leave_type": row.leave_type or None,
		}

	# Approved leave applications covering the range (even if attendance not yet On Leave)
	leave_apps = frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"docstatus": 1,
			"status": "Approved",
			"from_date": ["<=", to_date],
			"to_date": [">=", from_date],
		},
		fields=["from_date", "to_date", "leave_type", "half_day", "half_day_date"],
	)
	for app in leave_apps:
		cur = max(getdate(app.from_date), from_date)
		end = min(getdate(app.to_date), to_date)
		while cur <= end:
			info = att_by_date.setdefault(
				cur,
				{
					"status": "On Leave",
					"leave": 1,
					"late": 0,
					"early": 0,
					"leave_type": app.leave_type,
				},
			)
			info["leave"] = 1
			if not info.get("leave_type"):
				info["leave_type"] = app.leave_type
			if info.get("status") in (None, "Holiday"):
				info["status"] = "On Leave"
			# Half-day leave on that date still marks leave indicator
			cur = add_days(cur, 1)

	holidays = set()
	try:
		holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	except Exception:
		holiday_list = None
	if holiday_list:
		holidays = set(
			frappe.get_all(
				"Holiday",
				filters={
					"parent": holiday_list,
					"holiday_date": ["between", [from_date, to_date]],
				},
				pluck="holiday_date",
			)
		)
		holidays = {getdate(h) for h in holidays}

	# Prefer date-scoped holiday list resolution when available
	try:
		from nepal_hrms.custom_code.attendance_holiday import holiday_info

		use_scoped = True
	except Exception:
		use_scoped = False

	events = {}
	date = from_date
	while date_diff(to_date, date) >= 0:
		date_str = date.strftime("%Y-%m-%d")
		if date in att_by_date:
			events[date_str] = att_by_date[date]
		else:
			is_hol = False
			if use_scoped:
				try:
					is_hol = bool(holiday_info(employee, date).is_holiday)
				except Exception:
					is_hol = date in holidays
			elif date in holidays:
				is_hol = True
			if is_hol:
				info = {
					"status": "Holiday",
					"leave": 0,
					"late": 0,
					"early": 0,
					"leave_type": None,
				}
				# Prefer Weekly Off when the holiday list marks it
				if use_scoped:
					try:
						hi = holiday_info(employee, date)
						if hi.weekly_off:
							info["status"] = "Weekly Off"
					except Exception:
						pass
				events[date_str] = info
		date = add_days(date, 1)

	return events


@frappe.whitelist()
def get_attendance_related_applications(employee=None, attendance_date=None, attendance=None):
	"""
	Related Leave / Attendance Request / Late / Early / OOO applications for an
	Attendance row (or employee + date). Used by desk form + bshrms detail sheet.
	"""
	from frappe import _

	if attendance and not (employee and attendance_date):
		row = frappe.db.get_value(
			"Attendance",
			attendance,
			["employee", "attendance_date", "attendance_request", "leave_application"],
			as_dict=True,
		)
		if not row:
			return {"links": []}
		employee = row.employee
		attendance_date = row.attendance_date
		att_request = row.attendance_request
		leave_app = row.leave_application
	else:
		if not employee:
			employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		if not employee or not attendance_date:
			frappe.throw(_("Employee and attendance date are required"))
		att_row = frappe.db.get_value(
			"Attendance",
			{"employee": employee, "attendance_date": getdate(attendance_date), "docstatus": ["<", 2]},
			["name", "attendance_request", "leave_application"],
			as_dict=True,
		)
		attendance = att_row.name if att_row else attendance
		att_request = att_row.attendance_request if att_row else None
		leave_app = att_row.leave_application if att_row else None

	roles = frappe.get_roles()
	if not ({"HR Manager", "HR User", "System Manager"} & set(roles)):
		session_emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		if employee != session_emp:
			frappe.throw(_("Not permitted"), frappe.PermissionError)

	day = getdate(attendance_date)
	links = []

	def _add(doctype, name, label=None, status=None):
		if not name:
			return
		links.append(
			{
				"doctype": doctype,
				"name": name,
				"label": label or name,
				"status": status,
				"route_name": doctype.replace(" ", "") + "DetailView",
			}
		)

	if att_request:
		st = frappe.db.get_value("Attendance Request", att_request, "docstatus")
		_add(
			"Attendance Request",
			att_request,
			att_request,
			"Submitted" if cint(st) == 1 else "Draft" if cint(st) == 0 else None,
		)
	if leave_app:
		st = frappe.db.get_value("Leave Application", leave_app, "status")
		_add("Leave Application", leave_app, leave_app, st)

	# Covering leave apps by date (even if Attendance.leave_application empty)
	for app in frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"docstatus": ["<", 2],
			"from_date": ["<=", day],
			"to_date": [">=", day],
		},
		fields=["name", "status"],
	):
		if leave_app and app.name == leave_app:
			continue
		_add("Leave Application", app.name, app.name, app.status)

	# Attendance Request overlapping this date (from_date/to_date)
	for app in frappe.get_all(
		"Attendance Request",
		filters={
			"employee": employee,
			"docstatus": ["<", 2],
			"from_date": ["<=", day],
			"to_date": [">=", day],
		},
		fields=["name", "docstatus"],
	):
		if att_request and app.name == att_request:
			continue
		_add(
			"Attendance Request",
			app.name,
			app.name,
			"Submitted" if cint(app.docstatus) == 1 else "Draft",
		)

	for doctype in (
		"Late Entry Application",
		"Early Exit Application",
		"Out of Office Application",
	):
		filters = {
			"employee": employee,
			"docstatus": ["<", 2],
			"attendance_date": day,
		}
		if attendance:
			rows = frappe.get_all(
				doctype,
				filters={
					"employee": employee,
					"docstatus": ["<", 2],
					"attendance": attendance,
				},
				fields=["name", "status"],
			)
			if not rows:
				rows = frappe.get_all(
					doctype, filters=filters, fields=["name", "status"]
				)
		else:
			rows = frappe.get_all(doctype, filters=filters, fields=["name", "status"])
		for app in rows:
			_add(doctype, app.name, app.name, app.status)

	# Dedupe by doctype+name
	seen = set()
	unique = []
	for row in links:
		k = (row["doctype"], row["name"])
		if k in seen:
			continue
		seen.add(k)
		unique.append(row)

	return {
		"employee": employee,
		"attendance_date": str(day),
		"attendance": attendance,
		"attendance_request": att_request,
		"leave_application": leave_app,
		"links": unique,
	}
