# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Rich attendance calendar payload for bshrms (status + leave / late / early markers)."""

import frappe
from frappe.utils import add_days, cint, date_diff, getdate, get_first_day, today

from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee


def _leave_half_day_on(app):
	"""AD date that is the half-day of a Leave Application, or None."""
	if not cint(getattr(app, "half_day", 0)):
		return None
	if getattr(app, "half_day_date", None):
		return getdate(app.half_day_date)
	if getdate(app.from_date) == getdate(app.to_date):
		return getdate(app.from_date)
	return None


def _current_bs_month_start_ad(ad=None):
	"""First AD date of the BS month containing `ad` (default: today)."""
	import nepal_compliance.nepali_date_utils.nepali_date as nepali_date

	nepali_date._ensure_loaded()
	day = getdate(ad or today())
	bs = nepali_date.ad_to_bs(day)
	return nepali_date.bs_to_ad(bs["year"], bs["month"], 1)


@frappe.whitelist()
def get_leave_application_counts(employee=None, from_date=None, to_date=None):
	"""Approved / rejected / pending Leave Application counts overlapping a date range."""
	from frappe import _
	from frappe.utils import flt, get_first_day, get_last_day, getdate, today

	if not employee:
		employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		frappe.throw(_("Employee not found"))

	from nepal_hrms.api.pwa_access import resolve_calendar_employee

	if resolve_calendar_employee(employee) != employee:
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
def get_attendance_request_counts(employee=None, from_date=None, to_date=None):
	"""Approved / rejected / pending Attendance Request counts overlapping a date range."""
	from frappe import _
	from frappe.utils import date_diff, get_first_day, get_last_day, getdate, today

	from nepal_hrms.api.pwa_access import resolve_calendar_employee

	employee = resolve_calendar_employee(employee)
	if not employee:
		frappe.throw(_("Employee not found"))

	start = getdate(from_date) if from_date else get_first_day(getdate(today()))
	end = getdate(to_date) if to_date else get_last_day(getdate(today()))

	fields = ["name", "docstatus", "from_date", "to_date"]
	if frappe.get_meta("Attendance Request").has_field("status"):
		fields.append("status")

	rows = frappe.get_all(
		"Attendance Request",
		filters={
			"employee": employee,
			"docstatus": ["<", 2],
			"from_date": ["<=", end],
			"to_date": [">=", start],
		},
		fields=fields,
	)

	approved = rejected = pending = 0
	days = 0
	for r in rows:
		status = (getattr(r, "status", None) or "").strip()
		if status == "Rejected":
			rejected += 1
			continue
		if r.docstatus == 1 or status == "Approved":
			approved += 1
			overlap_start = max(getdate(r.from_date), start)
			overlap_end = min(getdate(r.to_date), end)
			days += date_diff(overlap_end, overlap_start) + 1
			continue
		pending += 1

	return {
		"total": approved + rejected + pending,
		"approved": approved,
		"rejected": rejected,
		"pending": pending,
		"days": days,
		"from_date": str(start),
		"to_date": str(end),
	}




@frappe.whitelist()
def get_attendance_hours_summary(employee=None, from_date=None, to_date=None):
	"""Worked vs target hours for the PWA attendance tab (same rules as Monthly Attendance Sheet BS)."""
	from frappe import _
	from frappe.utils import get_first_day, get_last_day, getdate, today

	from nepal_hrms.api.pwa_access import resolve_calendar_employee
	from nepal_hrms.nepal_hrms.report.monthly_attendance_sheet_bs.monthly_attendance_sheet_bs import (
		get_attendance_and_leaves,
		get_data,
	)

	employee = resolve_calendar_employee(employee)
	if not employee:
		frappe.throw(_("Employee not found"))

	company = frappe.db.get_value("Employee", employee, "company")
	if not company:
		frappe.throw(_("Company not found for employee"))

	start = getdate(from_date) if from_date else get_first_day(getdate(today()))
	end = getdate(to_date) if to_date else get_last_day(getdate(today()))
	filters = frappe._dict({"company": company, "employee": employee})
	att_data, leave_types = get_attendance_and_leaves(filters, start, end)
	rows = get_data(filters, start, end, att_data, leave_types)
	summary = (rows[0].get("summary") if rows else None) or "0:00 / 0:00"
	parts = [p.strip() for p in str(summary).split("/")]
	worked_label = parts[0] if parts else "0:00"
	target_label = parts[1] if len(parts) > 1 else "0:00"
	return {
		"summary": summary,
		"worked_label": worked_label,
		"target_label": target_label,
		"from_date": str(start),
		"to_date": str(end),
	}


@frappe.whitelist()
def get_attendance_calendar_details(from_date: str, to_date: str, employee: str = None) -> dict:
	"""
	Return per-day calendar details for the logged-in employee (or another
	employee when the user has the view-others-calendar permission).

	Shape:
	  {
	    "YYYY-MM-DD": {
	      "status": "Present" | "Absent" | "On Leave" | "Leave Pending" | "Leave Rejected" | ...,
	      "leave": 0|1,
	      "late": 0|1,   # minor late day (occurrence)
	      "early": 0|1,  # minor early day (occurrence)
	      "leave_type": str | None,
	      "leave_app_status": "Approved" | "Pending" | "Rejected" | None,
	      "leave_application": str | None,
	    },
	    ...
	  }
	"""
	from nepal_hrms.api.pwa_access import (
		can_view_past_attendance,
		resolve_calendar_employee,
	)

	employee = resolve_calendar_employee(employee)
	if not employee:
		return {}

	from_date = getdate(from_date)
	to_date = getdate(to_date)

	# Own calendar: past months are always allowed.
	# Others' calendar: past months need the settings role.
	# Clamp to the current *BS* month start (not AD), so Shrawan days that
	# fall in the previous English month are not dropped.
	session_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if employee != session_employee and not can_view_past_attendance():
		month_start = _current_bs_month_start_ad()
		if from_date < month_start:
			from_date = month_start
		if to_date < from_date:
			return {}

	attendance_rows = frappe.get_all(
		"Attendance",
		filters={
			"employee": employee,
			"attendance_date": ["between", [from_date, to_date]],
			"docstatus": 1,
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
			"leave": 1 if row.status == "On Leave" else 0,
			"late": cint(row.custom_cnr_late_in_pool) if has_late else 0,
			"early": cint(row.custom_cnr_early_in_pool) if has_early else 0,
			"ooo_required": 0,
			"leave_type": row.leave_type or None,
			"leave_app_status": None,
			"leave_application": None,
			"sandwich": 0,
			"half_day": 0,
		}

	# Leave applications covering the range (Pending / Approved / Rejected)
	# Priority when multiple apps cover a day: Approved > Pending > Rejected
	_LEAVE_STATUS_RANK = {"Approved": 3, "Pending": 2, "Rejected": 1}

	def _normalize_leave_app_status(status, docstatus):
		if status == "Approved" or (cint(docstatus) == 1 and status not in ("Rejected", "Cancelled")):
			return "Approved"
		if status == "Rejected":
			return "Rejected"
		# Draft / Open / etc. → Pending
		return "Pending"

	leave_apps = frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"docstatus": ["<", 2],
			"status": ["!=", "Cancelled"],
			"from_date": ["<=", to_date],
			"to_date": [">=", from_date],
		},
		fields=[
			"name",
			"status",
			"docstatus",
			"from_date",
			"to_date",
			"leave_type",
			"half_day",
			"half_day_date",
		],
	)
	for app in leave_apps:
		app_status = _normalize_leave_app_status(app.status, app.docstatus)
		rank = _LEAVE_STATUS_RANK[app_status]
		cur = max(getdate(app.from_date), from_date)
		end = min(getdate(app.to_date), to_date)
		while cur <= end:
			info = att_by_date.setdefault(
				cur,
				{
					"status": None,
					"leave": 0,
					"late": 0,
					"early": 0,
					"ooo_required": 0,
					"leave_type": None,
					"leave_app_status": None,
					"leave_application": None,
					"sandwich": 0,
					"half_day": 0,
				},
			)
			prev_rank = _LEAVE_STATUS_RANK.get(info.get("leave_app_status") or "", 0)
			has_attendance = info.get("status") not in (
				None,
				"Holiday",
				"Weekly Off",
				"Leave Pending",
				"Leave Rejected",
			)
			# Rejected leave must not overlay Present / Absent / On Leave days
			if app_status == "Rejected" and has_attendance:
				cur = add_days(cur, 1)
				continue
			if rank >= prev_rank:
				info["leave_app_status"] = app_status
				info["leave_application"] = app.name
				if not info.get("leave_type"):
					info["leave_type"] = app.leave_type
				info["half_day"] = 1 if _leave_half_day_on(app) == cur else 0

				if app_status == "Approved":
					info["leave"] = 1
					info["status"] = "On Leave"
				elif app_status == "Pending":
					info["leave"] = 1
					# Don't override Present/Absent/On Leave; use Leave Pending when empty/holiday
					if info.get("status") in (None, "Holiday", "Weekly Off"):
						info["status"] = "Leave Pending"
				elif app_status == "Rejected":
					info["status"] = "Leave Rejected"
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
	holiday_days = set()
	date = from_date
	while date_diff(to_date, date) >= 0:
		date_str = date.strftime("%Y-%m-%d")
		if date in att_by_date:
			events[date_str] = att_by_date[date]
			if use_scoped:
				try:
					if holiday_info(employee, date).is_holiday:
						holiday_days.add(date)
				except Exception:
					if date in holidays:
						holiday_days.add(date)
			elif date in holidays:
				holiday_days.add(date)
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
				holiday_days.add(date)
				info = {
					"status": "Holiday",
					"leave": 0,
					"late": 0,
					"early": 0,
					"ooo_required": 0,
					"leave_type": None,
					"leave_app_status": None,
					"leave_application": None,
					"sandwich": 0,
					"half_day": 0,
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

	# A sandwiched holiday is an absence/leave day, not a payable holiday.
	# Keep this aligned with Monthly Attendance Sheet BS.
	try:
		from nepal_hrms.custom_code.attendance_holiday import (
			covering_leave_application,
			is_sandwiched,
		)

		for date in sorted(holiday_days):
			if is_sandwiched(employee, date):
				leave_application = covering_leave_application(employee, date)
				date_str = date.strftime("%Y-%m-%d")
				info = events.get(date_str) or att_by_date.get(date) or {
					"status": None,
					"leave": 0,
					"late": 0,
					"early": 0,
					"ooo_required": 0,
					"leave_type": None,
					"leave_app_status": None,
					"leave_application": None,
					"sandwich": 0,
					"half_day": 0,
				}
				info["sandwich"] = 1
				if leave_application:
					info["status"] = "On Leave"
					info["leave"] = 1
					info["leave_type"] = leave_application.leave_type
					info["leave_app_status"] = "Approved"
					info["leave_application"] = leave_application.name
				else:
					info["status"] = "Absent"
					info["leave"] = 0
					info["leave_type"] = None
				events[date_str] = info
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			f"BSHRMS attendance calendar sandwich: {employee}",
		)

	# Mid-day OUT→IN gaps beyond grace → Out of Office form required (calendar marker)
	from nepal_hrms.custom_code.attendance_policy import (
		get_hr_settings,
		max_out_in_gap_mins,
	)

	grace_mins = cint(getattr(get_hr_settings(), "late_early_grace_mins", None) or 15)
	all_checkins = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"time": [
				"between",
				[f"{from_date} 00:00:00", f"{to_date} 23:59:59"],
			],
		},
		fields=["time", "log_type"],
		order_by="time asc",
	)
	checkins_by_date = {}
	for c in all_checkins:
		d = getdate(c.time)
		checkins_by_date.setdefault(d, []).append(c)

	ooo_app_dates = set()
	for app in frappe.get_all(
		"Out of Office Application",
		filters={
			"employee": employee,
			"docstatus": ["<", 2],
			"status": ["not in", ["Cancelled", "Rejected"]],
			"attendance_date": ["between", [from_date, to_date]],
		},
		fields=["attendance_date", "status"],
	):
		# Any Draft/Approved OOO filing covers the day
		ooo_app_dates.add(getdate(app.attendance_date))

	for d, day_checkins in checkins_by_date.items():
		if d in ooo_app_dates:
			continue
		if max_out_in_gap_mins(day_checkins) <= grace_mins:
			continue
		date_str = d.strftime("%Y-%m-%d")
		info = events.get(date_str) or att_by_date.get(d)
		if not info:
			info = {
				"status": None,
				"leave": 0,
				"late": 0,
				"early": 0,
				"ooo_required": 0,
				"leave_type": None,
				"leave_app_status": None,
				"leave_application": None,
				"sandwich": 0,
				"half_day": 0,
			}
			events[date_str] = info
		info["ooo_required"] = 1

	return events


@frappe.whitelist()
def get_attendance_day_details(date: str, employee: str = None) -> dict:
	"""
	Full single-day detail for the bshrms calendar day sheet:
	attendance record, all check-ins/outs, flags, related applications
	and the form actions still available for that day.
	"""
	from frappe import _
	from nepal_hrms.api.pwa_access import resolve_calendar_employee

	employee = resolve_calendar_employee(employee)
	if not employee:
		frappe.throw(_("Employee not found"))

	day = getdate(date)
	day_str = day.strftime("%Y-%m-%d")

	meta = frappe.get_meta("Attendance")
	att_fields = [
		"name",
		"status",
		"in_time",
		"out_time",
		"working_hours",
		"shift",
		"leave_type",
		"attendance_request",
		"leave_application",
	]
	for f in (
		"late_entry",
		"early_exit",
		"custom_cnr_late_in_pool",
		"custom_cnr_early_in_pool",
		"custom_late_mins",
		"custom_early_mins",
	):
		if meta.has_field(f):
			att_fields.append(f)

	attendance = frappe.db.get_value(
		"Attendance",
		{"employee": employee, "attendance_date": day, "docstatus": 1},
		att_fields,
		as_dict=True,
	)

	checkins = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"time": ["between", [f"{day_str} 00:00:00", f"{day_str} 23:59:59"]],
		},
		fields=["name", "time", "log_type", "custom_attendance_type", "custom_reason"],
		order_by="time asc",
	)

	sandwich = False
	sandwich_leave_type = None

	# Holiday/sandwich fallback when there is no submitted Attendance.
	status = attendance.status if attendance else None
	try:
		from nepal_hrms.custom_code.attendance_holiday import (
			covering_leave_application,
			holiday_info,
			is_sandwiched,
		)

		hi = holiday_info(employee, day)
		if hi.is_holiday:
			sandwich = is_sandwiched(employee, day)
			if sandwich:
				covering_leave = covering_leave_application(employee, day)
				if covering_leave:
					status = "On Leave"
					sandwich_leave_type = covering_leave.leave_type
				else:
					status = "Absent"
			elif not status:
				status = "Weekly Off" if hi.weekly_off else "Holiday"
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			f"BSHRMS attendance day sandwich: {employee} {day}",
		)

	# Late/early minutes from check-in vs shift (not the Attendance "marked late" flag alone)
	from nepal_hrms.custom_code.attendance_policy import (
		classify_delay,
		compute_late_early_minutes,
		get_hr_settings,
		max_out_in_gap_mins,
	)

	in_time = None
	out_time = None
	if attendance and attendance.get("in_time"):
		in_time = attendance.in_time
	else:
		for c in checkins:
			if (c.log_type or "").upper() == "IN":
				in_time = c.time
				break
		if not in_time and checkins:
			in_time = checkins[0].time

	if attendance and attendance.get("out_time"):
		out_time = attendance.out_time
	else:
		for c in reversed(checkins):
			if (c.log_type or "").upper() == "OUT":
				out_time = c.time
				break

	shift = attendance.shift if attendance else None
	late_mins, early_mins = compute_late_early_minutes(
		employee, day, in_time=in_time, out_time=out_time, shift=shift
	)
	# Prefer stored minutes when already computed on Attendance
	if attendance and cint(attendance.get("custom_late_mins") or 0):
		late_mins = cint(attendance.custom_late_mins)
	if attendance and cint(attendance.get("custom_early_mins") or 0):
		early_mins = cint(attendance.custom_early_mins)

	settings = get_hr_settings()
	grace_mins = cint(getattr(settings, "late_early_grace_mins", None) or 15)
	max_delay_mins = cint(getattr(settings, "late_early_max_delay_mins", None) or 60)
	late_kind = classify_delay(late_mins, grace_mins, max_delay_mins)  # None | minor | major
	early_kind = classify_delay(early_mins, grace_mins, max_delay_mins)

	# Flags for UI chips: beyond grace counts as late/early
	late = late_kind in ("minor", "major")
	early = early_kind in ("minor", "major")
	leave = bool(status == "On Leave" or (attendance and attendance.leave_type))

	related = get_attendance_related_applications(employee=employee, attendance_date=day_str)
	links = related.get("links", [])

	# Best leave application status for this day (Approved > Pending > Rejected)
	leave_app_status = None
	leave_application_name = None
	_rank = {"Approved": 3, "Pending": 2, "Rejected": 1}
	for link in links:
		if link.get("doctype") != "Leave Application":
			continue
		st = link.get("status") or ""
		if st == "Approved":
			norm = "Approved"
		elif st == "Rejected":
			norm = "Rejected"
		elif st == "Cancelled":
			continue
		else:
			norm = "Pending"
		if _rank.get(norm, 0) > _rank.get(leave_app_status or "", 0):
			leave_app_status = norm
			leave_application_name = link.get("name")

	if leave_app_status == "Approved":
		leave = True
		if status in (None, "Holiday", "Weekly Off", "Absent"):
			status = "On Leave"
	elif leave_app_status == "Pending" and status in (None, "Holiday", "Weekly Off"):
		status = "Leave Pending"
		leave = True
	elif leave_app_status == "Rejected" and status in (None, "Holiday", "Weekly Off"):
		status = "Leave Rejected"

	half_day = 0
	leave_app_type = None
	if leave_application_name:
		leave_app_row = frappe.db.get_value(
			"Leave Application",
			leave_application_name,
			["half_day", "half_day_date", "from_date", "to_date", "leave_type"],
			as_dict=True,
		)
		if leave_app_row:
			leave_app_type = leave_app_row.leave_type
			if _leave_half_day_on(leave_app_row) == day:
				half_day = 1

	# Form actions still available (no existing application of that type for the day)
	existing_doctypes = {link["doctype"] for link in links}
	actions = []

	session_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	is_self = employee == session_employee

	from frappe.utils import today

	today_date = getdate(today())
	is_today = day == today_date
	is_future = day > today_date
	has_checkins = bool(checkins)
	has_normal_in = any(
		(c.log_type or "").upper() == "IN"
		and (c.custom_attendance_type or "Normal") != "OOO Work"
		for c in checkins
	)

	# Late Entry may be informed in advance for today/future dates.
	if (
		is_self
		and "Late Entry Application" not in existing_doctypes
		and (
			late_kind in ("minor", "major")
			or (is_today and not has_normal_in)
			or is_future
		)
	):
		actions.append(
			{
				"doctype": "Late Entry Application",
				"label": _("Apply Late Entry"),
				"route_name": "LateEntryApplicationFormView",
			}
		)

	if is_self and early_kind in ("minor", "major") and "Early Exit Application" not in existing_doctypes:
		actions.append(
			{
				"doctype": "Early Exit Application",
				"label": _("Apply Early Exit"),
				"route_name": "EarlyExitApplicationFormView",
			}
		)

	# Mid-day OUT→IN gap beyond grace → Out of Office Application
	out_in_gap_mins = max_out_in_gap_mins(checkins)
	has_ooo_app = any(
		link.get("doctype") == "Out of Office Application"
		and (link.get("status") or "") not in ("Cancelled", "Rejected")
		for link in links
	)
	ooo_required = out_in_gap_mins > grace_mins and not has_ooo_app
	# OOO may also be informed before leaving, using estimated times.
	if (
		is_self
		and "Out of Office Application" not in existing_doctypes
		and (ooo_required or is_today or is_future)
	):
		actions.append(
			{
				"doctype": "Out of Office Application",
				"label": _("Apply Out of Office"),
				"route_name": "OutOfOfficeApplicationFormView",
			}
		)

	if is_self and status == "Absent" and "Attendance Request" not in existing_doctypes:
		actions.append(
			{
				"doctype": "Attendance Request",
				"label": _("Request Attendance"),
				"route_name": "AttendanceRequestFormView",
			}
		)

	# Leave offers
	leave_blocked_statuses = ("Holiday", "Weekly Off", "On Leave", "Leave Pending")
	can_offer_leave = (
		is_self
		and "Leave Application" not in existing_doctypes
		and status not in leave_blocked_statuses
		and leave_app_status != "Approved"
	)
	if can_offer_leave:
		# Beyond max allowed late → half-day leave (in addition to Late Entry)
		if late_kind == "major":
			actions.append(
				{
					"doctype": "Leave Application",
					"label": _("Apply Half Day Leave"),
					"route_name": "LeaveApplicationFormView",
					"half_day": 1,
				}
			)
		elif status == "Absent" or day > today_date or (is_today and not has_checkins):
			actions.append(
				{
					"doctype": "Leave Application",
					"label": _("Apply for Leave"),
					"route_name": "LeaveApplicationFormView",
				}
			)

	return {
		"employee": employee,
		"date": day_str,
		"status": status,
		"attendance": attendance,
		"checkins": checkins,
		"late_mins": late_mins,
		"early_mins": early_mins,
		"out_in_gap_mins": out_in_gap_mins,
		"grace_mins": grace_mins,
		"max_delay_mins": max_delay_mins,
		"late_kind": late_kind,
		"early_kind": early_kind,
		"flags": {
			"late": late,
			"early": early,
			"leave": leave,
			"ooo_required": 1 if ooo_required else 0,
			"sandwich": 1 if sandwich else 0,
			"leave_type": (
				sandwich_leave_type
				or (attendance.leave_type if attendance else None)
				or leave_app_type
			),
			"leave_app_status": leave_app_status,
			"leave_application": leave_application_name,
			"half_day": half_day,
		},
		"links": links,
		"actions": actions,
	}


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
			{"employee": employee, "attendance_date": getdate(attendance_date), "docstatus": 1},
			["name", "attendance_request", "leave_application"],
			as_dict=True,
		)
		attendance = att_row.name if att_row else attendance
		att_request = att_row.attendance_request if att_row else None
		leave_app = att_row.leave_application if att_row else None

	from nepal_hrms.api.pwa_access import resolve_calendar_employee

	if resolve_calendar_employee(employee) != employee:
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


@frappe.whitelist()
def check_leave_sandwich(from_date: str, to_date: str) -> dict:
	"""
	Non-blocking sandwich-rule precheck for the bshrms calendar leave flow.

	Mirrors validate_sandwich_leave_application (which throws on submit) so the
	app can warn the user while they are still picking dates.
	"""
	from frappe import _

	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		frappe.throw(_("Employee not found"))

	from nepal_hrms.custom_code.attendance_policy import get_hr_settings

	settings = get_hr_settings()
	if not settings.enable_leave_sandwich_rule:
		return {"enabled": False, "violation": False}

	from nepal_hrms.custom_code.policy_escape import has_policy_escape
	from nepal_hrms.custom_code.sandwich_leave import evaluate_leave_sandwich

	from_d = getdate(from_date)
	to_d = getdate(to_date)
	if to_d < from_d:
		from_d, to_d = to_d, from_d

	if has_policy_escape(employee, "escape_sandwich", from_d):
		return {"enabled": True, "violation": False, "warning": False, "escape": True}

	block = bool(settings.block_sandwich_leave_application)
	result = evaluate_leave_sandwich(employee, from_d, to_d, current_leave=None)

	message = None
	if result["violation"]:
		message = result["message"]
		if block:
			message += " " + _(
				"This application will be rejected on submission unless you include those days in a single leave request."
			)
	elif result["warning"]:
		message = result["warning_message"]

	return {
		"enabled": True,
		"block": block,
		"violation": result["violation"],
		"warning": result["warning"],
		"holiday_span": result.get("holiday_span"),
		"message": message,
		"warning_message": result.get("warning_message"),
	}
