# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Half-day leave: which half was leave, and how the worked half is judged.

Stock HRMS marks a half-day leave's Attendance "Half Day" with
half_day_status="Present" and modify_half_day_status=1, meaning "the other half
has not been checked against check-ins yet". Its own check-in path then settles
that half and clears the flag; if nothing does, mark_absent_for_half_day_dates
sweeps the half to Absent. nepal_hrms routes check-ins through its own sync,
which skipped every leave row -- so the flag was never cleared and people who
worked their half were swept to Absent. resolve_half_day_other_half() is the
missing step, and keeps stock's meaning of both fields so v16's own
auto-attendance still reads the rows correctly.

Nothing upstream records *which* half was leave (checked through v16 and
develop). custom_half_day_session carries it on Leave Application and
Attendance; the custom_ prefix keeps it clear of any future upstream field.
"""

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate

FIRST_HALF = "First Half"
SECOND_HALF = "Second Half"
SESSIONS = (FIRST_HALF, SECOND_HALF)
SESSION_FIELD = "custom_half_day_session"

SETTINGS = "Nepal HRMS Settings"
SCALE_FIELD = "scale_rules_on_half_day_leave"
SCALE = 0.5


# -- which leave covers the day ------------------------------------------------


def half_day_leave_on(employee, attendance_date):
	"""The approved Leave Application whose half day falls on this date, or None.

	half_day_date is the day that is half; on a multi-day leave the other days
	are whole leave days, so matching on it rather than the from/to range is what
	keeps a full leave day from being read as a half.
	"""
	if not employee or not attendance_date:
		return None
	day = getdate(attendance_date)
	fields = ["name", "leave_type", "half_day_date"]
	if frappe.get_meta("Leave Application").has_field(SESSION_FIELD):
		fields.append(SESSION_FIELD)
	rows = frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"docstatus": 1,
			"status": "Approved",
			"from_date": ["<=", day],
			"to_date": [">=", day],
			"half_day": 1,
			"half_day_date": day,
		},
		fields=fields,
		order_by="modified desc",
		limit=1,
	)
	return rows[0] if rows else None


# -- the scaling switch ----------------------------------------------------------


def scaling_enabled():
	"""Nepal HRMS Settings > Scale Rules on Half-Day Leave Days. On by default.

	Read from tabSingles directly: a Single stores nothing for a field added after
	its first save, and loading the doc turns that missing Check into 0, which
	would read as off on every existing site. No stored row means never saved, so
	the declared default -- on -- is the right answer; the settings controller
	writes it on the next save.
	"""
	# frappe.local is a werkzeug Local: attributes only, no __dict__ to setdefault on.
	cached = getattr(frappe.local, "_nepal_half_day_scaling", None)
	if cached is None:
		row = frappe.db.sql(
			"select value from `tabSingles` where doctype = %s and field = %s",
			(SETTINGS, SCALE_FIELD),
		)
		cached = True if not row else bool(cint(row[0][0]))
		frappe.local._nepal_half_day_scaling = cached
	return cached


def scale_factor(employee=None, attendance_date=None, leave=None):
	"""0.5 on a half-day leave day with scaling on, else 1.0."""
	if not scaling_enabled():
		return 1.0
	if leave is None:
		leave = half_day_leave_on(employee, attendance_date)
	return SCALE if leave else 1.0


# -- which half of the clock -------------------------------------------------------


def shift_window(shift):
	"""(start, midpoint, end) in seconds since midnight, or None.

	None for an overnight shift: it has no single calendar day to split, so a
	half there would be a guess dressed up as a fact.
	"""
	if not shift:
		return None
	cache = getattr(frappe.local, "_nepal_half_day_windows", None)
	if cache is None:
		cache = frappe.local._nepal_half_day_windows = {}
	if shift not in cache:
		row = frappe.db.get_value("Shift Type", shift, ["start_time", "end_time"], as_dict=True)
		window = None
		if row and row.start_time is not None and row.end_time is not None:
			start, end = row.start_time.total_seconds(), row.end_time.total_seconds()
			if end > start:
				window = (start, start + (end - start) / 2, end)
		cache[shift] = window
	return cache[shift]


def worked_half_from_time(in_time, shift):
	"""'first' | 'second' | None -- the half someone turned up for.

	A first check-in past the shift midpoint means the morning was not worked.
	This is the fallback for leaves filed before the session field existed.
	"""
	window = shift_window(shift)
	if not window or not in_time:
		return None
	try:
		t = get_datetime(in_time)
	except Exception:
		return None
	secs = t.hour * 3600 + t.minute * 60 + t.second
	return "second" if secs >= window[1] else "first"


def leave_session(leave, first_in=None, shift=None):
	"""The half covered by leave: the leave's own choice, else inferred, else None."""
	explicit = (leave or {}).get(SESSION_FIELD) if leave else None
	if explicit in SESSIONS:
		return explicit
	worked = worked_half_from_time(first_in, shift)
	if worked == "first":
		return SECOND_HALF
	if worked == "second":
		return FIRST_HALF
	return None


def worked_half_for_session(session):
	"""'first' | 'second' | None -- the half that is *not* leave."""
	if session == FIRST_HALF:
		return "second"
	if session == SECOND_HALF:
		return "first"
	return None


def _fmt(secs):
	secs = int(secs)
	return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}"


@frappe.whitelist()
def get_half_day_windows(employee=None, date=None):
	"""Clock times of each half for the PWA's 1st / 2nd Half buttons.

	Empty when the employee has no shift that day or it runs overnight -- the
	buttons then show their names alone rather than invented times.
	"""
	if not employee or not date:
		return {}
	# Whitelisted: only someone who may read the employee learns their shift times.
	if not frappe.has_permission("Employee", "read", doc=employee):
		return {}
	from hrms.hr.doctype.shift_assignment.shift_assignment import get_employee_shift

	try:
		details = get_employee_shift(employee, get_datetime(f"{getdate(date)} 12:00:00"), True)
	except Exception:
		details = None
	shift = details.shift_type.name if details and details.get("shift_type") else None
	if not shift:
		shift = frappe.db.get_value("Employee", employee, "default_shift")
	window = shift_window(shift)
	if not window:
		return {}
	start, mid, end = window
	return {
		"shift": shift,
		FIRST_HALF: f"{_fmt(start)}–{_fmt(mid)}",
		SECOND_HALF: f"{_fmt(mid)}–{_fmt(end)}",
	}


# -- settling the worked half --------------------------------------------------------


def compute_half_day_other_half(attendance, computed=None):
	"""What settling the worked half would write -- without writing it.

	Recalculate C&R previews before it applies, so the verdict and the write are
	separate. Returns frappe._dict(writes, computed, session), or None when the
	row is not a half-day leave. (Not "values": on a dict that name is the
	built-in method, and plan.values would never reach the key.)

	half_day_status follows stock: Absent only when the worked hours fall under
	the shift's absent threshold (halved when scaling is on), Present otherwise.
	modify_half_day_status is cleared so the stock sweep leaves the row be. With
	no check-ins at all the flag stays set: then the sweep's Absent is correct,
	because nobody came.
	"""
	if isinstance(attendance, str):
		attendance = frappe.get_doc("Attendance", attendance)
	if (attendance.status or "").strip() != "Half Day" or not attendance.leave_type:
		return None

	from nepal_hrms.overrides.attendance_override import (
		_has_approved_attendance_request,
		_status_from_hours,
		compute_day_hours_from_checkins,
	)

	employee, day = attendance.employee, getdate(attendance.attendance_date)
	leave = half_day_leave_on(employee, day)
	if computed is None:
		computed = compute_day_hours_from_checkins(employee, day)

	shift = computed.shift_name or attendance.shift
	values = {}

	session = leave_session(leave, computed.first_in, shift)
	if session and frappe.get_meta("Attendance").has_field(SESSION_FIELD):
		values[SESSION_FIELD] = session

	if computed.checkin_names:
		if _has_approved_attendance_request(attendance):
			# A manager already ruled on this day; hours refresh, the ruling stands.
			other = attendance.half_day_status or "Present"
		elif computed.unpaired_in:
			# Punched in, never out: the hours are unknown, not zero. Someone came.
			other = "Present"
		else:
			# The row is a half-day leave by construction, so only the switch decides.
			factor = SCALE if scaling_enabled() else 1.0
			status = _status_from_hours(computed.total_hours, shift, factor=factor)
			other = "Absent" if status == "Absent" else "Present"
		values.update(
			{
				"half_day_status": other,
				"modify_half_day_status": 0,
				"working_hours": computed.total_hours,
				"in_time": computed.first_in,
				"out_time": computed.last_out,
			}
		)
		if computed.shift_name:
			values["shift"] = computed.shift_name

	return frappe._dict(writes=values, computed=computed, session=session)


def resolve_half_day_other_half(attendance, computed=None):
	"""Settle the worked half of a half-day leave row from the day's check-ins.

	Returns the values written, or None when the row is not a half-day leave.
	"""
	if isinstance(attendance, str):
		attendance = frappe.get_doc("Attendance", attendance)
	plan = compute_half_day_other_half(attendance, computed)
	if plan is None:
		return None
	if not plan.writes:
		return plan.writes

	before = attendance.half_day_status
	frappe.db.set_value("Attendance", attendance.name, plan.writes, update_modified=True)

	for checkin in plan.computed.checkin_names or []:
		frappe.db.set_value(
			"Employee Checkin",
			checkin,
			{"attendance": attendance.name, "skip_auto_attendance": 0},
			update_modified=False,
		)

	after = plan.writes.get("half_day_status")
	if after and after != before:
		frappe.get_doc("Attendance", attendance.name).add_comment(
			"Comment",
			text=_("Other half set to {0} from check-ins ({1}h worked{2}).").format(
				after,
				plan.computed.total_hours,
				_(", leave on {0}").format(_(plan.session)) if plan.session else "",
			),
		)
	return plan.writes


def on_leave_application_change(doc, method=None):
	"""on_submit / on_update_after_submit: settle the half-day's attendance now.

	HRMS writes the Attendance first (its own on_submit), then these hooks run.
	Without this, check-ins punched before the approval are never looked at
	again, and the next sweep marks the worked half Absent.
	"""
	if not cint(doc.get("half_day")) or not doc.get("half_day_date"):
		return
	if doc.docstatus != 1 or doc.status != "Approved":
		return
	try:
		name = frappe.db.get_value(
			"Attendance",
			{
				"employee": doc.employee,
				"attendance_date": getdate(doc.half_day_date),
				"docstatus": ["<", 2],
			},
			"name",
		)
		if name:
			resolve_half_day_other_half(name)
	except Exception:
		# Approving a leave must never fail on a bookkeeping step.
		frappe.log_error(frappe.get_traceback(), "Nepal half-day attendance resolve failed")
