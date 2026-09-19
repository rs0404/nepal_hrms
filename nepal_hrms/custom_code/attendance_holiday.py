# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Holiday list + sandwich helpers for Recalculate C&R."""

import re

import frappe
from frappe.utils import add_days, cint, get_datetime, getdate

from nepal_hrms.custom_code.policy_escape import has_policy_escape


# Split so a caller can drop the C&R verdict while keeping the raw timing. A
# holiday must not produce a late/early count, but the minutes stay visible on the
# day popup so the reader can still see when the person actually arrived.
CNR_FLAG_FIELDS = (
	"late_entry",
	"early_exit",
	"custom_cnr_unexcused_late",
	"custom_cnr_unexcused_early",
	"custom_cnr_late_in_pool",
	"custom_cnr_early_in_pool",
)
CNR_MINUTE_FIELDS = (
	"custom_late_mins",
	"custom_early_mins",
)
CNR_CLEAR_FIELDS = CNR_FLAG_FIELDS + CNR_MINUTE_FIELDS

# "Saturday Sunday 2083/84" → "Saturday Sunday"
_HOLIDAY_LIST_YEAR_SUFFIX = re.compile(r"\s*\d{2,4}(/\d{2,4})?\s*$")


def _holiday_list_base_name(name):
	if not name:
		return ""
	return _HOLIDAY_LIST_YEAR_SUFFIX.sub("", name).strip()


def get_holiday_list_for_employee_on_date(employee, attendance_date):
	"""
	Holiday List that applies on this date.

	Employee.holiday_list is the *current* FY list. For older attendance dates
	(previous fiscal year), resolve the list whose from_date/to_date covers the
	day — preferring the same series as the employee's current list
	(e.g. Saturday Sunday 2082/83 when assigned Saturday Sunday 2083/84).
	"""
	day = getdate(attendance_date)
	current = frappe.db.get_value("Employee", employee, "holiday_list")
	if current:
		bounds = frappe.db.get_value(
			"Holiday List", current, ["from_date", "to_date"], as_dict=True
		)
		if (
			bounds
			and bounds.from_date
			and bounds.to_date
			and getdate(bounds.from_date) <= day <= getdate(bounds.to_date)
		):
			return current

	candidates = frappe.get_all(
		"Holiday List",
		filters={"from_date": ["<=", day], "to_date": [">=", day]},
		fields=["name", "from_date", "to_date"],
		order_by="from_date desc",
	)
	if not candidates:
		default = None
		# Prefer Company default; HR Settings.default_holiday_list was removed in newer HRMS
		company = frappe.db.get_value("Employee", employee, "company")
		if company:
			default = frappe.db.get_value("Company", company, "default_holiday_list")
		if not default and frappe.get_meta("HR Settings").has_field("default_holiday_list"):
			default = frappe.db.get_single_value("HR Settings", "default_holiday_list")
		if default:
			bounds = frappe.db.get_value(
				"Holiday List", default, ["from_date", "to_date"], as_dict=True
			)
			if (
				bounds
				and bounds.from_date
				and bounds.to_date
				and getdate(bounds.from_date) <= day <= getdate(bounds.to_date)
			):
				return default
		return current or default

	base = _holiday_list_base_name(current)
	if base:
		for c in candidates:
			if _holiday_list_base_name(c.name) == base or c.name.startswith(base):
				return c.name

	# Prefer Sat+Sun lists over Saturday-only when both cover the date
	for c in candidates:
		if "Sunday" in (c.name or ""):
			return c.name
	return candidates[0].name


def get_holiday_list_for_employee(employee):
	"""Current assigned list (not date-scoped). Prefer get_holiday_list_for_employee_on_date."""
	holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")
	if holiday_list:
		return holiday_list
	company = frappe.db.get_value("Employee", employee, "company")
	if company:
		holiday_list = frappe.db.get_value("Company", company, "default_holiday_list")
	if not holiday_list and frappe.get_meta("HR Settings").has_field("default_holiday_list"):
		holiday_list = frappe.db.get_single_value("HR Settings", "default_holiday_list")
	return holiday_list


def holiday_description(value):
	"""Plain-text holiday name.

	Holiday.description is a rich-text field, so it arrives wrapped in editor
	markup ("<div class=\"ql-editor read-mode\"><p>Janai Purnima</p></div>").
	Strip it here rather than at each caller -- none of them may render HTML.
	"""
	text = frappe.utils.strip_html(str(value or "")).strip()
	return " ".join(text.split())


def holiday_info(employee, attendance_date):
	"""Return {is_holiday, weekly_off, description, holiday_list} for a date."""
	day = getdate(attendance_date)
	holiday_list = get_holiday_list_for_employee_on_date(employee, day)
	if not holiday_list:
		return frappe._dict(
			is_holiday=False, weekly_off=False, description="", holiday_list=None
		)

	row = frappe.db.get_value(
		"Holiday",
		{"parent": holiday_list, "holiday_date": day},
		["holiday_date", "weekly_off", "description"],
		as_dict=True,
	)
	if not row:
		return frappe._dict(
			is_holiday=False, weekly_off=False, description="", holiday_list=holiday_list
		)
	return frappe._dict(
		is_holiday=True,
		weekly_off=bool(cint(row.weekly_off)),
		description=holiday_description(row.description),
		holiday_list=holiday_list,
	)


def clear_holiday_date_cache(employee=None):
	"""Drop the request-local holiday_dates_between cache."""
	cache = getattr(frappe.local, "_nepal_holiday_dates", None)
	if cache is None:
		return
	if employee is None:
		frappe.local._nepal_holiday_dates = {}
		return
	prefix = f"{employee}::"
	for key in [k for k in cache if k.startswith(prefix)]:
		cache.pop(key, None)


def holiday_dates_between(employee, start_date, end_date):
	"""Set of holiday / weekly-off dates for one employee across a range.

	Deliberately built on get_holiday_list_for_employee_on_date rather than
	hrms.hr.utils.get_holiday_dates_for_employee: the hrms helper resolves
	Employee.holiday_list, the *current* fiscal year's list, so for a back-dated
	period it queries a list whose range does not cover those dates and returns an
	empty set -- excluding no holidays at all on exactly the historical periods a
	payroll re-run touches.

	One query per (employee, range), request-cached, so a period-wide sweep does not
	turn into an N+1.
	"""
	start = getdate(start_date)
	end = getdate(end_date)
	if start > end:
		return set()

	cache = getattr(frappe.local, "_nepal_holiday_dates", None)
	if cache is None:
		cache = frappe.local._nepal_holiday_dates = {}
	key = f"{employee}::{start}..{end}"
	if key in cache:
		return cache[key]

	# Two lookups, not one: a Custom Day Range period can straddle a fiscal-year
	# holiday-list boundary even though a BS month never does.
	lists = {
		get_holiday_list_for_employee_on_date(employee, start),
		get_holiday_list_for_employee_on_date(employee, end),
	}
	lists.discard(None)
	lists.discard("")

	dates = set()
	if lists:
		rows = frappe.get_all(
			"Holiday",
			filters={
				"parent": ["in", list(lists)],
				"holiday_date": ["between", [start, end]],
			},
			pluck="holiday_date",
			ignore_permissions=True,
		)
		dates = {getdate(d) for d in rows}

	cache[key] = dates
	return dates


def is_holiday_or_weekend(employee, date_obj):
	"""Date-aware holiday check (uses FY holiday list covering that date)."""
	return bool(holiday_info(employee, date_obj).is_holiday)


def get_adjacent_working_day(employee, date_obj, direction=-1):
	"""Next/previous non-holiday day using date-scoped holiday lists."""
	curr = add_days(getdate(date_obj), direction)
	# Safety bound: do not scan forever
	for _ in range(366):
		if not is_holiday_or_weekend(employee, curr):
			return curr
		curr = add_days(curr, direction)
	return curr


def has_checkins(employee, attendance_date, attendance_name=None):
	"""True if any Employee Checkin exists for the day (or linked to attendance)."""
	if not employee or not attendance_date:
		return False

	day = getdate(attendance_date)
	start = get_datetime(f"{day} 00:00:00")
	end = get_datetime(f"{day} 23:59:59.999999")

	if frappe.db.exists(
		"Employee Checkin",
		{"employee": employee, "time": ["between", [start, end]]},
	):
		return True

	if attendance_name and frappe.db.exists(
		"Employee Checkin", {"attendance": attendance_name}
	):
		return True

	return False


def covering_leave_application(employee, attendance_date):
	"""Approved Leave Application covering the date, if any."""
	day = getdate(attendance_date)
	rows = frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"docstatus": 1,
			"status": "Approved",
			"from_date": ["<=", day],
			"to_date": [">=", day],
		},
		fields=["name", "leave_type", "half_day", "half_day_date"],
		order_by="modified desc",
		limit=1,
	)
	return rows[0] if rows else None


def _is_full_day_leave_application(leave, day):
	"""True when leave covers the day as a full day (not half-day on that date)."""
	if not leave:
		return False
	if not cint(leave.half_day):
		return True
	# Half-day leave only on half_day_date — that day is not a full leave anchor
	if leave.half_day_date and getdate(leave.half_day_date) == getdate(day):
		return False
	return True


def _day_is_full_leave_or_absent(employee, date_obj):
	"""
	True only for full-day leave or Absent on a working day.

	Half Day (including half-day Present / half-day leave), Present, WFH, or
	unmarked days do NOT count — sandwich requires leave/absent both before and
	after the holiday with no present-side attendance on either side.
	"""
	day = getdate(date_obj)

	att = frappe.db.get_value(
		"Attendance",
		{
			"employee": employee,
			"attendance_date": day,
			"docstatus": 1,
		},
		["status", "half_day_status", "leave_type"],
		as_dict=True,
	)
	if att:
		status = (att.status or "").strip()
		# Any present-side or half-day status breaks sandwich on this side
		if status in ("Present", "Work From Home", "Half Day"):
			return False
		if status == "Absent":
			return True
		if status == "On Leave":
			# On Leave is full-day leave attendance
			return True
		# Holiday/Weekly Off on a "working" adjacent day shouldn't happen; not an anchor
		return False

	# No Attendance row — only count approved full-day leave covering the date
	leave = covering_leave_application(employee, day)
	return _is_full_day_leave_application(leave, day)


def sandwich_rule_enabled():
	try:
		from nepal_hrms.custom_code.attendance_policy import get_hr_settings

		settings = get_hr_settings()
		return bool(cint(getattr(settings, "enable_leave_sandwich_rule", 0)))
	except Exception:
		return False


def is_sandwiched(employee, attendance_date):
	"""
	True when this holiday sits between full leave/absent working days.

	Both the previous and next adjacent working days must be full-day leave or
	Absent. If either side is Present, Half Day (even half-day present), WFH,
	or unmarked without full leave — sandwich does not apply.
	"""
	if not sandwich_rule_enabled():
		return False
	if has_policy_escape(employee, "escape_sandwich", attendance_date):
		return False

	day = getdate(attendance_date)
	if not is_holiday_or_weekend(employee, day):
		return False

	prev_wd = get_adjacent_working_day(employee, day, direction=-1)
	next_wd = get_adjacent_working_day(employee, day, direction=1)
	if not prev_wd or not next_wd:
		return False

	return _day_is_full_leave_or_absent(employee, prev_wd) and _day_is_full_leave_or_absent(
		employee, next_wd
	)


def clear_cnr_flags(doc, keep_minutes=False, reset_half_day_status=True):
	"""Zero late/early/C&R occurrence flags on the Attendance doc (in memory).

	keep_minutes leaves custom_late_mins / custom_early_mins alone, for callers that
	want the day excluded from every count while the raw timing stays readable.
	reset_half_day_status=False spares a legitimate half-day-leave row.
	"""
	fields = CNR_FLAG_FIELDS if keep_minutes else CNR_CLEAR_FIELDS
	for field in fields:
		if hasattr(doc, field):
			setattr(doc, field, 0)
	if hasattr(doc, "custom_cnr_month_late_pool_count"):
		# Keep month counts accurate via caller / apply_late_early; zero contribution
		pass
	if reset_half_day_status and hasattr(doc, "half_day_status"):
		doc.half_day_status = None


def skip_late_early_for_status(doc):
	"""Statuses where late/early C&R should not run."""
	status = (doc.status or "").strip()
	if status in ("On Leave", "Absent", "Work From Home", "Holiday", "Weekly Off"):
		return True
	if getattr(doc, "leave_type", None):
		return True
	return False


def apply_holiday_sandwich_status(doc):
	"""
	Mutate Attendance status for holiday / sandwich / working-day conversion.
	Returns a reason tag or None when no holiday-related status change was applied.
	"""
	if not doc.employee or not doc.attendance_date:
		return None

	employee = doc.employee
	day = getdate(doc.attendance_date)
	info = holiday_info(employee, day)
	checks = has_checkins(employee, day, getattr(doc, "name", None))
	status = (doc.status or "").strip()

	# Pre-existing protected working-day rows (not Holiday/WO): leave alone unless
	# this date is a holiday and sandwich/holiday rules apply below.
	if not info.is_holiday and status in ("On Leave", "Work From Home"):
		return None
	if not info.is_holiday and status == "Absent" and not checks:
		# Keep Absent on working days with no punches (already correct)
		return None

	if info.is_holiday:
		leave = covering_leave_application(employee, day)
		sandwiched = is_sandwiched(employee, day)

		# Approved leave covering this day wins (including weekends included in LA)
		if leave:
			doc.status = "On Leave"
			doc.leave_type = leave.leave_type
			clear_cnr_flags(doc)
			return "sandwich_leave" if sandwiched else "leave_on_holiday"

		if sandwiched:
			doc.status = "Absent"
			doc.leave_type = None
			clear_cnr_flags(doc)
			return "sandwich_absent"

		if checks:
			# Extra work on holiday — Present path; Comp Off is a separate request
			if status in ("Holiday", "Weekly Off", "Absent", ""):
				doc.status = "Present"
			doc.leave_type = None
			if hasattr(doc, "half_day_status") and status in (
				"Holiday",
				"Weekly Off",
				"Absent",
			):
				doc.half_day_status = None
			return "worked_holiday"

		doc.status = "Weekly Off" if info.weekly_off else "Holiday"
		doc.leave_type = None
		clear_cnr_flags(doc)
		return "weekly_off" if info.weekly_off else "holiday"

	# Not on any FY holiday list for this date — convert prior Holiday/WO only when
	# the day is truly a working day (e.g. mid-week that was wrongly marked).
	if status in ("Holiday", "Weekly Off"):
		if checks:
			doc.status = "Present"
			doc.leave_type = None
			if hasattr(doc, "half_day_status"):
				doc.half_day_status = None
			return "working_day"
		doc.status = "Absent"
		doc.leave_type = None
		clear_cnr_flags(doc)
		return "working_day_absent"

	return None
