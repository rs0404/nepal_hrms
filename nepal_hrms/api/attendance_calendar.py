# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Rich attendance calendar payload for bshrms (status + leave / late / early markers)."""

import frappe
from frappe.utils import (
	add_days,
	cint,
	date_diff,
	get_datetime,
	get_first_day,
	get_last_day,
	getdate,
	today,
)

from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee


def _lwp_leave_types():
	return set(frappe.get_all("Leave Type", filters={"is_lwp": 1}, pluck="name"))


def _grace_after_flags(mins, grace):
	"""Return (within_grace, after_grace) for a late/early minute count."""
	mins = cint(mins)
	if mins <= 0:
		return 0, 0
	if mins <= cint(grace or 15):
		return 1, 0
	return 0, 1


_CNR_APP_RANK = {"Approved": 3, "Draft": 2, "Rejected": 1}
_CNR_APP_FIELDS = (
	("Late Entry Application", "late_app_status", "late"),
	("Early Exit Application", "early_app_status", "early"),
	("Out of Office Application", "ooo_app_status", "ooo"),
)


def _normalize_cnr_app_status(status, docstatus=None):
	status = (status or "").strip()
	if status == "Cancelled" or (docstatus is not None and cint(docstatus) == 2):
		return None
	if status == "Approved":
		return "Approved"
	if status == "Rejected":
		return "Rejected"
	return "Draft"


def _better_cnr_app_status(current, incoming):
	if _CNR_APP_RANK.get(incoming or "", 0) >= _CNR_APP_RANK.get(current or "", 0):
		return incoming
	return current


def _cnr_status_from_links(links, doctype):
	best = None
	for link in links or []:
		if link.get("doctype") != doctype:
			continue
		incoming = _normalize_cnr_app_status(link.get("status"))
		if incoming:
			best = _better_cnr_app_status(best, incoming)
	return best


def _apply_cnr_application_statuses(employee, from_date, to_date, events):
	"""Attach Approved / Draft / Rejected CNR slips to calendar days."""
	for doctype, status_field, marker_field in _CNR_APP_FIELDS:
		if not frappe.db.exists("DocType", doctype):
			continue
		for app in frappe.get_all(
			doctype,
			filters={
				"employee": employee,
				"docstatus": ["<", 2],
				"attendance_date": ["between", [from_date, to_date]],
			},
			fields=["attendance_date", "status", "docstatus"],
		):
			incoming = _normalize_cnr_app_status(app.status, app.docstatus)
			if not incoming:
				continue
			date_str = getdate(app.attendance_date).strftime("%Y-%m-%d")
			info = events.get(date_str)
			if not info:
				info = _blank_calendar_day()
				events[date_str] = info
			info[status_field] = _better_cnr_app_status(info.get(status_field), incoming)


def _shift_midpoint(shift, cache):
	"""Seconds-since-midnight midpoint of a shift, or None for an overnight one."""
	if not shift:
		return None
	if shift not in cache:
		row = frappe.db.get_value(
			"Shift Type", shift, ["start_time", "end_time"], as_dict=True
		)
		mid = None
		if row and row.start_time is not None and row.end_time is not None:
			start, end = row.start_time.total_seconds(), row.end_time.total_seconds()
			# An overnight shift has no meaningful "first half" on one calendar day.
			if end > start:
				mid = start + (end - start) / 2
		cache[shift] = mid
	return cache[shift]


def _worked_half(in_time, shift, cache):
	"""'first' | 'second' | None -- which half of the day was actually worked.

	Attendance.half_day_status records what the *other* half was (Present/Absent),
	never which half of the clock, so the only real signal is when the person
	turned up: a check-in past the shift midpoint means the morning was the
	leave/absent half. Without a shift or a check-in there is nothing to infer
	from, and the caller falls back to "worked half first".
	"""
	mid = _shift_midpoint(shift, cache)
	if mid is None or not in_time:
		return None
	try:
		t = get_datetime(in_time)
	except Exception:
		return None
	secs = t.hour * 3600 + t.minute * 60 + t.second
	return "second" if secs >= mid else "first"


def _blank_calendar_day():
	return {
		"status": None,
		"leave": 0,
		"late": 0,
		"early": 0,
		"late_grace": 0,
		"late_after": 0,
		"early_grace": 0,
		"early_after": 0,
		"late_in_pool": 0,
		"early_in_pool": 0,
		"ooo": 0,
		"ooo_required": 0,
		"late_app_status": None,
		"early_app_status": None,
		"ooo_app_status": None,
		"leave_type": None,
		"leave_app_status": None,
		"leave_application": None,
		"sandwich": 0,
		"half_day": 0,
		# Attendance.half_day_status: what the *other* half was. "Absent" there
		# means the non-worked half is unpaid even when a leave covers this day,
		# which is the only thing that tells the two apart in the cell fill.
		"half_day_status": None,
		"worked_half": None,
		"holiday_name": "",
	}


def _month_pool_penalty(employee, day):
	from nepal_hrms.custom_code.attendance_policy import (
		assign_employee_pool_penalties_for_range,
		get_hr_settings,
		penalty_mark,
	)

	day = getdate(day)
	meta = frappe.get_meta("Attendance")
	if not (
		meta.has_field("custom_cnr_late_in_pool")
		or meta.has_field("custom_cnr_early_in_pool")
	):
		return "", ""
	try:
		settings = get_hr_settings()
	except Exception:
		settings = frappe._dict()
	assigned = assign_employee_pool_penalties_for_range(employee, day, day, settings)
	kind = assigned.get(day) or ""
	return kind, penalty_mark(kind)


def _is_lwp_leave(leave_type, lwp_types=None):
	if not leave_type:
		return 0
	if lwp_types is not None:
		return 1 if leave_type in lwp_types else 0
	name = str(leave_type).strip().lower()
	if "without pay" in name or "lwp" in name or "unpaid" in name:
		return 1
	return cint(frappe.db.get_value("Leave Type", leave_type, "is_lwp") or 0)


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


def _default_payroll_window(from_date=None, to_date=None, ref_date=None):
	"""Explicit dates, else the configured payroll period containing the reference day.

	These counts sit next to the attendance summary on the PWA dashboard, so they
	have to describe the same window; an AD calendar month does not, once the
	payroll basis is a Custom Day Range.
	"""
	from frappe.utils import get_first_day, get_last_day, getdate, today

	if from_date and to_date:
		return getdate(from_date), getdate(to_date)
	day = getdate(ref_date or from_date or today())
	try:
		from nepal_hrms.custom_code.payroll.period import period_containing

		start, end, _days = period_containing(day)
		if start and end:
			return getdate(start), getdate(end)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Nepal HRMS: payroll period resolution")
	return getdate(get_first_day(day)), getdate(get_last_day(day))


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

	start, end = _default_payroll_window(from_date, to_date)

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

	start, end = _default_payroll_window(from_date, to_date)

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


def _resolve_summary_window(from_date, to_date, bs_year, bs_month, ref_date):
	"""Resolve the summary window, preferring the configured payroll period.

	Precedence: explicit dates, then an explicit BS month, then a reference date,
	then today. Never throws -- a broken settings row must not blank the whole
	attendance tab, so it degrades to the raw BS month and finally to an AD month.
	"""
	from frappe.utils import get_first_day, get_last_day

	from nepal_hrms.custom_code.payroll.period import period_containing, resolve_bs_period

	if from_date and to_date:
		return getdate(from_date), getdate(to_date)

	try:
		if bs_year and bs_month:
			# resolve_bs_period names a period by the month it ends in, so the BS
			# month on screen and the period under it now overlap for all but the
			# last few days -- and, more to the point, agree with the report's
			# month filter. period_containing(bs day 1) would give the same window
			# under a 29-28 cycle; this stays explicit about naming the period.
			start, end, _days = resolve_bs_period(cint(bs_year), cint(bs_month))
		else:
			start, end, _days = period_containing(getdate(ref_date or today()))
		if start and end:
			return getdate(start), getdate(end)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Nepal HRMS: payroll period resolution")

	day = getdate(ref_date or today())
	try:
		start = _current_bs_month_start_ad(day)
		if start:
			import nepal_compliance.nepali_date_utils.nepali_date as nepali_date

			nepali_date._ensure_loaded()
			bs = nepali_date.ad_to_bs(getdate(start))
			length = nepali_date._bs_months[bs["year"]][bs["month"] - 1]
			return getdate(start), getdate(nepali_date.bs_to_ad(bs["year"], bs["month"], length))
	except Exception:
		pass
	return getdate(get_first_day(day)), getdate(get_last_day(day))


@frappe.whitelist()
def get_attendance_period_summary(
	employee=None, from_date=None, to_date=None, bs_year=None, bs_month=None, ref_date=None
):
	"""Attendance totals for one employee over one payroll period.

	Same numbers as the Monthly Attendance Sheet BS report, by construction -- both
	go through custom_code.attendance_summary.summarize_period. The PWA renders
	these instead of counting days in the browser.
	"""
	from frappe import _

	from nepal_hrms.api.pwa_access import can_view_past_attendance, resolve_calendar_employee
	from nepal_hrms.custom_code.attendance_summary import summarize_period

	employee = resolve_calendar_employee(employee)
	if not employee:
		return {"found": False}

	start, end = _resolve_summary_window(from_date, to_date, bs_year, bs_month, ref_date)

	# summarize_period reaches a loader whose role scoping an explicit employee
	# filter overrides, so the history clamp has to be applied here or this endpoint
	# becomes a read-around for exactly the past that get_attendance_calendar_details
	# hides from viewers without the role.
	session_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if employee != session_employee and not can_view_past_attendance():
		month_start = getdate(_current_bs_month_start_ad())
		if start < month_start:
			start = month_start
		if end < start:
			return {"found": False, "period": _period_payload(start, end)}

	if date_diff(end, start) > 120:
		frappe.throw(_("Summary window cannot exceed 120 days."))

	result = summarize_period(employee, start, end)
	result.setdefault("period", {})
	result["period"].update(_period_payload(start, end))
	return result


def _period_payload(start, end):
	"""The window, labelled -- the PWA draws its calendar grid from exactly this.

	bs_year / bs_month name the period rather than describing `start`: a period is
	named by the month it ends in, so the PWA can page to the neighbouring period
	by stepping this month without re-deriving the payroll cycle in JavaScript.
	"""
	payload = {
		"from_date": str(start),
		"to_date": str(end),
		"bs_from": _bs_label(start),
		"bs_to": _bs_label(end),
	}
	try:
		import nepal_compliance.nepali_date_utils.nepali_date as nepali_date

		nepali_date._ensure_loaded()
		bs_end = nepali_date.ad_to_bs(getdate(end))
		payload["bs_year"] = cint(bs_end["year"])
		payload["bs_month"] = cint(bs_end["month"])
	except Exception:
		pass
	return payload


def _bs_label(ad_date):
	try:
		import nepal_compliance.nepali_date_utils.nepali_date as nepali_date

		nepali_date._ensure_loaded()
		bs = nepali_date.ad_to_bs(getdate(ad_date))
		return f"{bs['year']}-{bs['month']:02d}-{bs['day']:02d}"
	except Exception:
		return str(ad_date)


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
	      "late": 0|1,         # any late minutes, including within grace
	      "late_grace": 0|1,   # delay still inside late_early_grace_mins
	      "late_after": 0|1,   # delay past grace (pool / major)
	      "early": 0|1,
	      "early_grace": 0|1,
	      "early_after": 0|1,
	      "late_app_status": "Approved" | "Draft" | "Rejected" | None,
	      "early_app_status": "Approved" | "Draft" | "Rejected" | None,
	      "ooo_app_status": "Approved" | "Draft" | "Rejected" | None,
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

	lwp_types = _lwp_leave_types()

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
			"half_day_status",
			"leave_type",
			"in_time",
			"out_time",
			"shift",
			"custom_cnr_late_in_pool",
			"custom_cnr_early_in_pool",
			"custom_late_mins",
			"custom_early_mins",
		],
	)

	att_by_date = {}
	meta = frappe.get_meta("Attendance")
	has_late = meta.has_field("custom_cnr_late_in_pool")
	has_early = meta.has_field("custom_cnr_early_in_pool")
	from nepal_hrms.custom_code.attendance_policy import (
		compute_late_early_minutes,
		get_hr_settings,
	)

	try:
		settings = get_hr_settings()
	except Exception:
		settings = frappe._dict()
	grace_mins = cint(getattr(settings, "late_early_grace_mins", None) or 15)
	shift_mid_cache = {}

	for row in attendance_rows:
		d = getdate(row.attendance_date)
		late_pool = cint(row.custom_cnr_late_in_pool) if has_late else 0
		early_pool = cint(row.custom_cnr_early_in_pool) if has_early else 0
		late_mins = cint(getattr(row, "custom_late_mins", 0) or 0)
		early_mins = cint(getattr(row, "custom_early_mins", 0) or 0)
		if row.in_time or row.out_time:
			calc_late, calc_early = compute_late_early_minutes(
				employee,
				d,
				in_time=row.in_time,
				out_time=row.out_time,
				shift=row.shift,
			)
			if row.in_time:
				late_mins = calc_late
			if row.out_time:
				early_mins = calc_early
		late_grace, late_after = _grace_after_flags(late_mins, grace_mins)
		early_grace, early_after = _grace_after_flags(early_mins, grace_mins)
		info = _blank_calendar_day()
		info.update(
			{
				"status": row.status,
				"half_day_status": row.half_day_status or None,
				"worked_half": _worked_half(row.in_time, row.shift, shift_mid_cache),
				"leave": 1 if row.status == "On Leave" else 0,
				"late": 1 if late_grace or late_after else 0,
				"early": 1 if early_grace or early_after else 0,
				"late_grace": late_grace,
				"late_after": late_after,
				"early_grace": early_grace,
				"early_after": early_after,
				"late_in_pool": late_pool,
				"early_in_pool": early_pool,
				"leave_type": row.leave_type or None,
			}
		)
		att_by_date[d] = info

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
			info = att_by_date.setdefault(cur, _blank_calendar_day())
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
				info = _blank_calendar_day()
				info["status"] = "Holiday"
				# Prefer Weekly Off when the holiday list marks it
				if use_scoped:
					try:
						hi = holiday_info(employee, date)
						if hi.weekly_off:
							info["status"] = "Weekly Off"
						# Same lookup already ran; carrying the name costs nothing
						# and lets a day say which holiday it is.
						info["holiday_name"] = hi.description
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
				info = events.get(date_str) or att_by_date.get(date) or _blank_calendar_day()
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
			info = _blank_calendar_day()
			events[date_str] = info
		info["ooo_required"] = 1
		info["ooo"] = 1

	_apply_cnr_application_statuses(employee, from_date, to_date, events)

	for info in events.values():
		info["is_lwp"] = _is_lwp_leave(info.get("leave_type"), lwp_types)

	from nepal_hrms.custom_code.attendance_policy import (
		assign_employee_pool_penalties_for_range,
		get_hr_settings,
		penalty_mark,
	)

	try:
		settings = get_hr_settings()
	except Exception:
		settings = frappe._dict()
	assigned = assign_employee_pool_penalties_for_range(
		employee, from_date, to_date, settings
	)
	for date_str, info in events.items():
		kind = assigned.get(getdate(date_str)) or ""
		info["pool_penalty"] = kind
		info["penalty_mark"] = penalty_mark(kind)

	return events


COMPENSATORY_ATTENDANCE_STATUSES = ("Present", "Work From Home", "Half Day")


def _compensatory_leave_action(employee, day, attendance_status):
	"""The day sheet's Apply Compensatory Leave offer, or None when it does not apply."""
	from frappe import _

	if attendance_status not in COMPENSATORY_ATTENDANCE_STATUSES:
		return None
	if not frappe.db.exists("Leave Type", {"is_compensatory": 1}):
		return None
	if frappe.db.exists(
		"Compensatory Leave Request",
		{
			"employee": employee,
			"docstatus": ["<", 2],
			"work_from_date": ["<=", day],
			"work_end_date": [">=", day],
		},
	):
		return None
	return {
		"doctype": "Compensatory Leave Request",
		"label": _("Apply Compensatory Leave"),
		"route_name": "CompensatoryLeaveRequestFormView",
		# Half a day worked earns half a day; Frappe HR refuses a full-day claim.
		"half_day": 1 if attendance_status == "Half Day" else 0,
	}


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
		"half_day_status",
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
	# Initialised outside the try: the block below logs and swallows its errors,
	# so the response must still have this key when the lookup fails.
	holiday_detail = {
		"is_holiday": 0,
		"weekly_off": 0,
		"description": "",
		"holiday_list": "",
	}

	# Holiday/sandwich fallback when there is no submitted Attendance.
	status = attendance.status if attendance else None
	try:
		from nepal_hrms.custom_code.attendance_holiday import (
			covering_leave_application,
			holiday_info,
			is_sandwiched,
		)

		hi = holiday_info(employee, day)
		holiday_detail.update(
			{
				"is_holiday": 1 if hi.is_holiday else 0,
				"weekly_off": 1 if hi.weekly_off else 0,
				"description": hi.description or "",
				"holiday_list": hi.holiday_list or "",
			}
		)
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
	# Stored minutes are a fallback when this day's in/out times are missing.
	if not in_time and attendance:
		late_mins = cint(attendance.get("custom_late_mins") or 0)
	if not out_time and attendance:
		early_mins = cint(attendance.get("custom_early_mins") or 0)

	settings = get_hr_settings()
	grace_mins = cint(getattr(settings, "late_early_grace_mins", None) or 15)
	max_delay_mins = cint(getattr(settings, "late_early_max_delay_mins", None) or 60)
	late_kind = classify_delay(late_mins, grace_mins, max_delay_mins)  # None | minor | major
	early_kind = classify_delay(early_mins, grace_mins, max_delay_mins)

	late_grace, late_after = _grace_after_flags(late_mins, grace_mins)
	early_grace, early_after = _grace_after_flags(early_mins, grace_mins)
	late = late_grace or late_after
	early = early_grace or early_after
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

	# A past working day with no attendance at all is an absence too: the
	# calendar paints it Absent, but there is no record to say so, so status is
	# still None here.
	shows_absent = status == "Absent" or (status is None and day < today_date)
	if is_self and shows_absent and "Attendance Request" not in existing_doctypes:
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
	pool_penalty, penalty_label = _month_pool_penalty(employee, day)
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

	# Worked a holiday or weekly off: the day earns compensatory leave. Offered
	# only where Frappe HR will accept it -- a holiday with submitted attendance
	# of Present, Work From Home or Half Day -- and once per day.
	if is_self and holiday_detail.get("is_holiday") and attendance:
		comp_action = _compensatory_leave_action(employee, day, attendance.status)
		if comp_action:
			actions.append(comp_action)

	if is_self and "Shift Request" not in existing_doctypes:
		actions.append(
			{
				"doctype": "Shift Request",
				"label": _("Request Shift"),
				"route_name": "ShiftRequestFormView",
			}
		)

	return {
		"employee": employee,
		"date": day_str,
		"status": status,
		"holiday": holiday_detail,
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
			"late_grace": late_grace,
			"late_after": late_after,
			"early": early,
			"early_grace": early_grace,
			"early_after": early_after,
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
			"half_day_status": (attendance.get("half_day_status") if attendance else None) or None,
			"is_lwp": _is_lwp_leave(
				sandwich_leave_type
				or (attendance.leave_type if attendance else None)
				or leave_app_type
			),
			"pool_penalty": pool_penalty,
			"penalty_mark": penalty_label,
			"late_app_status": _cnr_status_from_links(links, "Late Entry Application"),
			"early_app_status": _cnr_status_from_links(links, "Early Exit Application"),
			"ooo_app_status": _cnr_status_from_links(links, "Out of Office Application"),
		},
		"links": links,
		"actions": actions,
	}


# Each application says "why" in its own field, and Attendance Request splits it
# across two: a Select (Work From Home / On Duty) plus free text.
_REASON_FIELDS = {
	"Leave Application": ("description",),
	"Attendance Request": ("reason", "explanation"),
	"Late Entry Application": ("reason",),
	"Early Exit Application": ("reason",),
	"Out of Office Application": ("reason",),
}


def _reason_fieldnames(doctype):
	"""Reason fields this site actually has, plus the rejection note where present."""
	try:
		meta = frappe.get_meta(doctype)
	except Exception:
		return []
	fields = [f for f in _REASON_FIELDS.get(doctype, ()) if meta.has_field(f)]
	if meta.has_field("custom_rejection_reason"):
		fields.append("custom_rejection_reason")
	return fields


def _reason_text(row):
	"""One line of "why", collapsing Attendance Request's Select + explanation."""
	if not row:
		return ""
	parts = []
	for field in ("reason", "explanation", "description"):
		value = str(row.get(field) or "").strip()
		if value and value not in parts:
			parts.append(value)
	return " · ".join(parts)


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

	def _add(doctype, name, label=None, status=None, row=None):
		if not name:
			return
		links.append(
			{
				"doctype": doctype,
				"name": name,
				"label": label or name,
				"status": status,
				"reason": _reason_text(row),
				"rejection_reason": (row or {}).get("custom_rejection_reason") or "",
				"route_name": doctype.replace(" ", "") + "DetailView",
			}
		)

	if att_request:
		row = frappe.db.get_value(
			"Attendance Request",
			att_request,
			["docstatus"] + _reason_fieldnames("Attendance Request"),
			as_dict=True,
		) or frappe._dict()
		st = row.get("docstatus")
		_add(
			"Attendance Request",
			att_request,
			att_request,
			"Submitted" if cint(st) == 1 else "Draft" if cint(st) == 0 else None,
			row,
		)
	if leave_app:
		row = frappe.db.get_value(
			"Leave Application",
			leave_app,
			["status"] + _reason_fieldnames("Leave Application"),
			as_dict=True,
		) or frappe._dict()
		_add("Leave Application", leave_app, leave_app, row.get("status"), row)

	# Covering leave apps by date (even if Attendance.leave_application empty)
	for app in frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"docstatus": ["<", 2],
			"from_date": ["<=", day],
			"to_date": [">=", day],
		},
		fields=["name", "status"] + _reason_fieldnames("Leave Application"),
	):
		if leave_app and app.name == leave_app:
			continue
		_add("Leave Application", app.name, app.name, app.status, app)

	# Attendance Request overlapping this date (from_date/to_date)
	for app in frappe.get_all(
		"Attendance Request",
		filters={
			"employee": employee,
			"docstatus": ["<", 2],
			"from_date": ["<=", day],
			"to_date": [">=", day],
		},
		fields=["name", "docstatus"] + _reason_fieldnames("Attendance Request"),
	):
		if att_request and app.name == att_request:
			continue
		_add(
			"Attendance Request",
			app.name,
			app.name,
			"Submitted" if cint(app.docstatus) == 1 else "Draft",
			app,
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
		app_fields = ["name", "status"] + _reason_fieldnames(doctype)
		if attendance:
			rows = frappe.get_all(
				doctype,
				filters={
					"employee": employee,
					"docstatus": ["<", 2],
					"attendance": attendance,
				},
				fields=app_fields,
			)
			if not rows:
				rows = frappe.get_all(doctype, filters=filters, fields=app_fields)
		else:
			rows = frappe.get_all(doctype, filters=filters, fields=app_fields)
		for app in rows:
			_add(doctype, app.name, app.name, app.status, app)

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
