"""C&R attendance helpers: late/early minutes, grace flags, application linking, OOO hours."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, get_time, getdate, time_diff_in_hours


def get_hr_settings():
	"""Return Nepal HRMS Settings without requiring DocType read permission.

	Employees need grace/deadline values when filing Late/Early/OOO applications.
	enable_nepali_date / date_format are overlaid from Nepal Compliance Settings.
	"""
	settings = frappe._dict()
	try:
		if frappe.db.exists("DocType", "Nepal HRMS Settings"):
			settings.update(frappe.db.get_singles_dict("Nepal HRMS Settings") or {})
	except Exception:
		pass
	try:
		if frappe.db.exists("DocType", "Nepal Compliance Settings"):
			nc = frappe.db.get_singles_dict("Nepal Compliance Settings") or {}
			settings.setdefault("enable_nepali_date", nc.get("enable_nepali_date"))
			settings.setdefault("date_format", nc.get("date_format") or "YYYY-MM-DD")
	except Exception:
		pass
	return settings


def get_shift_bounds(employee, attendance_date, shift=None):
	"""Return (shift_start_dt, shift_end_dt) for the employee on a date, or (None, None)."""
	attendance_date = getdate(attendance_date)
	shift_name = shift
	if not shift_name:
		shift_name = frappe.db.get_value(
			"Shift Assignment",
			{
				"employee": employee,
				"start_date": ["<=", attendance_date],
				"docstatus": 1,
				"status": "Active",
			},
			"shift_type",
			order_by="start_date desc",
		)

	if not shift_name:
		shift_name = frappe.db.get_value("Employee", employee, "default_shift")

	if not shift_name:
		return None, None

	start_time, end_time = frappe.db.get_value(
		"Shift Type", shift_name, ["start_time", "end_time"]
	) or (None, None)
	if not start_time or not end_time:
		return None, None

	shift_start = get_datetime(f"{attendance_date} {start_time}")
	shift_end = get_datetime(f"{attendance_date} {end_time}")
	if shift_end <= shift_start:
		from frappe.utils import add_to_date

		shift_end = add_to_date(shift_end, days=1)
	return shift_start, shift_end


def compute_late_early_minutes(employee, attendance_date, in_time=None, out_time=None, shift=None):
	"""Compute late and early minutes vs shift start/end. Returns (late_mins, early_mins)."""
	late_mins = 0
	early_mins = 0
	shift_start, shift_end = get_shift_bounds(employee, attendance_date, shift)
	if not shift_start:
		return late_mins, early_mins

	if in_time:
		in_dt = get_datetime(in_time)
		delta = (in_dt - shift_start).total_seconds() / 60.0
		# Full minutes only — 09:30:54 vs a 09:30 start is on time, not 1 min late.
		if delta >= 1:
			late_mins = int(delta)

	if out_time:
		out_dt = get_datetime(out_time)
		delta = (shift_end - out_dt).total_seconds() / 60.0
		if delta >= 1:
			early_mins = int(delta)

	return late_mins, early_mins


def earliest_arrival(doc):
	"""The day's first check-in, not whichever IN happened to pair with an OUT.

	HRMS records in_time from its own IN/OUT pairing, so a missed lunch punch
	leaves the afternoon IN there and the morning arrival disappears. Lateness
	measured from that is hours wrong -- a minor delay reads as a major one and
	the day is demoted to a half day for a punch nobody missed.
	"""
	stored = getattr(doc, "in_time", None)
	if not doc.employee or not doc.attendance_date:
		return stored
	try:
		from nepal_hrms.overrides.attendance_override import (
			compute_day_hours_from_checkins,
		)

		first_in = compute_day_hours_from_checkins(
			doc.employee, doc.attendance_date
		).first_in
	except Exception:
		return stored
	if not first_in:
		return stored
	if stored and get_datetime(stored) < get_datetime(first_in):
		return stored
	return first_in


def apply_attendance_request_status(doc, request, holiday=None):
	"""Mark the day the way an approved Attendance Request says it should read.

	The request is a manager's ruling that the person was working, so it outranks
	an Absent written by a missing punch or a delay past the max. It does not
	outrank leave or a day off: those are what the person was actually doing.
	"""
	if holiday is not None and getattr(holiday, "is_holiday", False):
		return
	status = (doc.status or "").strip()
	if status in ("On Leave", "Holiday", "Weekly Off"):
		return

	# A half-day leave already holds the other half. Keep it, and let the request
	# account for the half it covers rather than overwriting the leave.
	if getattr(doc, "leave_type", None):
		doc.status = "Half Day"
		if hasattr(doc, "half_day_status"):
			doc.half_day_status = "Present"
		return

	request = request or {}
	half_day_date = request.get("half_day_date")
	if cint(request.get("half_day")) and (
		not half_day_date or getdate(half_day_date) == getdate(doc.attendance_date)
	):
		# HRMS's own convention for a half-day request: the request covers one half,
		# the other is unpaid unless something else claims it.
		doc.status = "Half Day"
		if hasattr(doc, "half_day_status"):
			doc.half_day_status = "Absent"
		return

	doc.status = "Present"
	if hasattr(doc, "half_day_status"):
		doc.half_day_status = None


def _is_genuine_absent(doc):
	"""Absent that is not an occurrence-pool 1P we wrote."""
	if (doc.status or "").strip() != "Absent":
		return False
	if (getattr(doc, "custom_cnr_pool_penalty", None) or "") == "full":
		return False
	if cint(getattr(doc, "custom_cnr_late_in_pool", 0)) or cint(
		getattr(doc, "custom_cnr_early_in_pool", 0)
	):
		return False
	return True


def _protected_status(doc, is_holiday=None):
	"""Do not override leave / genuine absent / WFH / holiday rows.

	is_holiday lets a caller that already resolved the date say so, rather than
	paying for another holiday_info lookup.
	"""
	if is_holiday:
		return True
	if getattr(doc, "leave_type", None):
		return True
	status = (doc.status or "").strip()
	if status in ("On Leave", "Work From Home", "Holiday", "Weekly Off"):
		return True
	return _is_genuine_absent(doc)


def _looks_like_cnr_penalty(doc):
	"""A Half Day / Absent with no leave behind it and a late/early trace on it.

	Late/early penalties are written as Half Day with half_day_status "Absent",
	and Recheck Attendance has not always stored the ½P mark, so neither the mark
	nor a "Present" half is a reliable sign. The delay itself is: a leave row is
	excluded, and a genuine absence has no punches to be late or early with.
	"""
	if getattr(doc, "leave_type", None):
		return False
	if (doc.status or "").strip() not in ("Half Day", "Absent"):
		return False
	if (getattr(doc, "custom_cnr_pool_penalty", None) or "").strip() in ("half", "full"):
		return True
	return any(
		cint(getattr(doc, field, 0))
		for field in (
			"late_entry",
			"early_exit",
			"custom_cnr_unexcused_late",
			"custom_cnr_unexcused_early",
			"custom_cnr_late_in_pool",
			"custom_cnr_early_in_pool",
		)
	)


def _late_early_escaped_dates(employee, start, end):
	from nepal_hrms.custom_code.policy_escape import escaped_dates

	return escaped_dates(employee, "escape_late_early", start, end)


def _has_half_day_leave(employee, attendance_date):
	from nepal_hrms.custom_code.half_day import half_day_leave_on

	return bool(half_day_leave_on(employee, attendance_date))


def delay_excused_for_attendance_status(
	mins, app, employee, attendance_date, grace, max_delay, excuse_half_day_leave=True
):
	"""
	Whether Attendance should stay/restore Present for this late/early delay.

	- Within grace: yes
	- Minor (grace < mins <= max): yes here — later pool logic may still write ½P / 1P on the charged day
	- Office Work approved slip: yes (full excuse, including major)
	- Major + Personal / no slip: only if half-day leave covers the date
	"""
	kind = classify_delay(mins, grace, max_delay)
	if not kind:
		return True
	# Minor delays never force Attendance Half Day (pool / payroll only)
	if kind == "minor":
		return True
	if app and (app.type_of_work or "") == "Office Work":
		return True
	# A half-day leave excuses a major delay -- it covered the missing time. Not
	# when the delay was measured inside the worked half: then nothing covers it.
	return excuse_half_day_leave and _has_half_day_leave(employee, attendance_date)


def delay_in_occurrence_pool(mins, app, grace, max_delay, settings=None):
	"""True when a minor delay counts toward the occurrence pool.

	An approved slip normally keeps the day out of the pool. Personal Work is the
	arguable case: the slip explains where someone was, but the time was theirs,
	not the company's -- so a site can choose to keep counting it. Office Work is
	company time and is never counted, whichever way the setting is set.
	"""
	kind = classify_delay(mins, grace, max_delay)
	if kind != "minor":
		return False
	if not app:
		return True

	if (app.get("type_of_work") or "") != "Personal Work":
		return False

	settings = settings if settings is not None else get_hr_settings()
	return bool(
		cint(getattr(settings, "count_personal_work_in_occurrence_pool", 0) or 0)
	)


def _month_bounds(attendance_date):
	from calendar import monthrange

	d = getdate(attendance_date)
	start = d.replace(day=1)
	end = d.replace(day=monthrange(d.year, d.month)[1])
	return start, end


def _pool_period_bounds(attendance_date, settings=None):
	"""Payroll period containing attendance_date (BS month or Custom Day Range)."""
	from nepal_hrms.custom_code.payroll.period import period_containing

	settings = settings if settings is not None else get_hr_settings()
	start, end, _days = period_containing(getdate(attendance_date), settings)
	if start and end:
		return getdate(start), getdate(end)
	return _month_bounds(attendance_date)


def _iter_periods_intersecting(from_date, to_date, settings=None):
	"""Distinct payroll periods overlapping [from_date, to_date]."""
	settings = settings if settings is not None else get_hr_settings()
	from_date = getdate(from_date)
	to_date = getdate(to_date)
	if to_date < from_date:
		from_date, to_date = to_date, from_date
	seen = set()
	cursor = from_date
	while cursor <= to_date:
		start, end = _pool_period_bounds(cursor, settings)
		key = (start, end)
		if key not in seen:
			seen.add(key)
			yield start, end
		cursor = add_days(end, 1)


def _pool_flags_between(employee, start, end, exclude_name=None, extra=None):
	filters = {
		"employee": employee,
		"attendance_date": ["between", [getdate(start), getdate(end)]],
		"docstatus": ["<", 2],
	}
	if exclude_name:
		filters["name"] = ["!=", exclude_name]
	fields = ["attendance_date"]
	meta = frappe.get_meta("Attendance")
	if meta.has_field("custom_cnr_late_in_pool"):
		fields.append("custom_cnr_late_in_pool")
	if meta.has_field("custom_cnr_early_in_pool"):
		fields.append("custom_cnr_early_in_pool")
	# Penalties are assigned by INDEX over the sorted pool days, so a holiday left
	# in the pool does not merely add a row -- it shifts which working day gets
	# charged. Exclude at the source, not at display time.
	from nepal_hrms.custom_code.attendance_holiday import holiday_dates_between

	# An escaped day is out of the pool for the same reason: it must not shift
	# which of the other days is charged, recalculated yet or not.
	holidays = holiday_dates_between(employee, start, end) | _late_early_escaped_dates(
		employee, start, end
	)
	flags = []
	for row in frappe.get_all("Attendance", filters=filters, fields=fields):
		if getdate(row.attendance_date) in holidays:
			continue
		flags.append(
			(
				row.attendance_date,
				cint(getattr(row, "custom_cnr_late_in_pool", 0) or 0),
				cint(getattr(row, "custom_cnr_early_in_pool", 0) or 0),
			)
		)
	if extra and getdate(extra[0]) not in holidays:
		flags.append(extra)
	return flags


def assign_employee_pool_penalties_for_range(employee, from_date, to_date, settings=None):
	"""Assign ½P/1P using payroll-period pool counts (each period counted separately)."""
	settings = settings if settings is not None else get_hr_settings()
	merged = {}
	for start, end in _iter_periods_intersecting(from_date, to_date, settings):
		flags = _pool_flags_between(employee, start, end)
		merged.update(assign_employee_pool_penalties(flags, settings))
	return merged


def count_month_pool(employee, attendance_date, pool_field, current_in_pool=0, exclude_name=None):
	"""Payroll-period pool size including the current attendance row's contribution."""
	if not frappe.get_meta("Attendance").has_field(pool_field):
		return cint(current_in_pool)
	settings = get_hr_settings()
	start, end = _pool_period_bounds(attendance_date, settings=settings)
	filters = {
		"employee": employee,
		"attendance_date": ["between", [start, end]],
		"docstatus": ["<", 2],
		pool_field: 1,
	}
	if exclude_name:
		filters["name"] = ["!=", exclude_name]
	# db.count cannot be post-filtered, and holiday rows must not inflate the pool
	# (see _pool_flags_between). Row volume is bounded by one payroll period.
	from nepal_hrms.custom_code.attendance_holiday import holiday_dates_between

	holidays = holiday_dates_between(employee, start, end) | _late_early_escaped_dates(
		employee, start, end
	)
	dates = frappe.get_all("Attendance", filters=filters, pluck="attendance_date")
	count = sum(1 for d in dates if getdate(d) not in holidays)
	return cint(count) + (1 if cint(current_in_pool) else 0)


def _month_pool_flags(employee, attendance_date, exclude_name=None, extra=None):
	settings = get_hr_settings()
	start, end = _pool_period_bounds(attendance_date, settings=settings)
	return _pool_flags_between(employee, start, end, exclude_name=exclude_name, extra=extra)


def _current_doc_pool_penalty(doc, settings):
	att_name = getattr(doc, "name", None)
	exclude = att_name if att_name and not str(att_name).startswith("new-") else None
	assigned = assign_employee_pool_penalties(
		_month_pool_flags(
			doc.employee,
			doc.attendance_date,
			exclude_name=exclude,
			extra=(
				doc.attendance_date,
				cint(getattr(doc, "custom_cnr_late_in_pool", 0) or 0),
				cint(getattr(doc, "custom_cnr_early_in_pool", 0) or 0),
			),
		),
		settings,
	)
	return assigned.get(getdate(doc.attendance_date)) or ""


def _apply_pool_or_major_status(doc, pool_kind, unexcused, was_cnr_half_day, is_holiday=None):
	if _protected_status(doc, is_holiday=is_holiday):
		if hasattr(doc, "custom_cnr_pool_penalty"):
			doc.custom_cnr_pool_penalty = ""
		return
	# A major delay (beyond max delay) is a half-day penalty in its own right, so it
	# carries the same ½P mark as a pool occurrence. That is what puts it under
	# Penalty Days in the BS sheet and on the slip, rather than a separate late /
	# early half-day line the report has no column for.
	if not pool_kind and unexcused:
		pool_kind = "half"
	previous = (getattr(doc, "custom_cnr_pool_penalty", None) or "").strip()
	if hasattr(doc, "custom_cnr_pool_penalty"):
		doc.custom_cnr_pool_penalty = pool_kind or ""
	if pool_kind == "full":
		doc.status = "Absent"
		if hasattr(doc, "half_day_status"):
			doc.half_day_status = None
		return
	if pool_kind == "half":
		doc.status = "Half Day"
		if hasattr(doc, "half_day_status"):
			doc.half_day_status = "Absent"
		return
	if (
		was_cnr_half_day
		or previous in ("half", "full")
		or (
			(doc.status or "") in ("Half Day", "Absent")
			and not getattr(doc, "leave_type", None)
		)
	) and (doc.status or "") in ("Half Day", "Absent", "Present"):
		# Only restore rows we previously marked as pool/major C&R
		if previous in ("half", "full") or was_cnr_half_day:
			doc.status = "Present"
			if hasattr(doc, "half_day_status"):
				doc.half_day_status = None


def sync_month_pool_penalties(employee, attendance_date, current_name=None):
	"""Rewrite ½P / 1P status on other days in the same payroll period."""
	if not employee or not attendance_date:
		return
	if frappe.flags.get("in_pool_penalty_sync"):
		return
	frappe.flags.in_pool_penalty_sync = True
	try:
		settings = get_hr_settings()
		if not cint(getattr(settings, "enable_late_early_penalty", 0)):
			return
		assigned = assign_employee_pool_penalties(
			_month_pool_flags(employee, attendance_date), settings
		)
		start, end = _pool_period_bounds(attendance_date, settings)
		# Holiday rows stay in the sweep on purpose: this is what clears a stale
		# ½P / 1P off them, via the protected branch in _apply_pool_or_major_status.
		from nepal_hrms.custom_code.attendance_holiday import holiday_dates_between

		holidays = holiday_dates_between(employee, start, end)
		escaped = _late_early_escaped_dates(employee, start, end)
		meta = frappe.get_meta("Attendance")
		fields = [
			"name",
			"attendance_date",
			"status",
			"leave_type",
			"half_day_status",
			"late_entry",
			"early_exit",
			"custom_cnr_unexcused_late",
			"custom_cnr_unexcused_early",
			"custom_cnr_late_in_pool",
			"custom_cnr_early_in_pool",
		]
		if meta.has_field("custom_cnr_pool_penalty"):
			fields.append("custom_cnr_pool_penalty")
		for att in frappe.get_all(
			"Attendance",
			filters={
				"employee": employee,
				"attendance_date": ["between", [start, end]],
				"docstatus": ["<", 2],
			},
			fields=fields,
		):
			if current_name and att.name == current_name:
				continue
			kind = assigned.get(getdate(att.attendance_date)) or ""
			before_penalty = getattr(att, "custom_cnr_pool_penalty", None) or ""
			if getdate(att.attendance_date) in escaped:
				# Its stored flags predate the escape until the day itself is
				# recalculated; never charge it from them, and undo a penalty.
				_apply_pool_or_major_status(
					att, "", 0, _looks_like_cnr_penalty(att), is_holiday=False
				)
			else:
				_apply_pool_or_major_status(
					att,
					kind,
					cint(att.custom_cnr_unexcused_late) or cint(att.custom_cnr_unexcused_early),
					False,
					is_holiday=getdate(att.attendance_date) in holidays,
				)
			values = {}
			if meta.has_field("custom_cnr_pool_penalty"):
				values["custom_cnr_pool_penalty"] = getattr(att, "custom_cnr_pool_penalty", None) or ""
			if (att.status or "") != (frappe.db.get_value("Attendance", att.name, "status") or ""):
				values["status"] = att.status
				if meta.has_field("half_day_status"):
					values["half_day_status"] = getattr(att, "half_day_status", None) or None
			elif values.get("custom_cnr_pool_penalty") != before_penalty:
				if meta.has_field("half_day_status"):
					values["half_day_status"] = getattr(att, "half_day_status", None) or None
			if values:
				frappe.db.set_value("Attendance", att.name, values, update_modified=False)
	finally:
		frappe.flags.in_pool_penalty_sync = False


def _refresh_month_pool_counts(doc, late_in_pool, early_in_pool):
	"""Rewrite the month-to-date pool counters on the doc (in memory).

	The DB count excludes this row, so its own contribution is passed in.
	"""
	att_name = getattr(doc, "name", None)
	exclude = att_name if att_name and not str(att_name).startswith("new-") else None
	if hasattr(doc, "custom_cnr_month_late_pool_count"):
		doc.custom_cnr_month_late_pool_count = count_month_pool(
			doc.employee,
			doc.attendance_date,
			"custom_cnr_late_in_pool",
			current_in_pool=late_in_pool,
			exclude_name=exclude,
		)
	if hasattr(doc, "custom_cnr_month_early_pool_count"):
		doc.custom_cnr_month_early_pool_count = count_month_pool(
			doc.employee,
			doc.attendance_date,
			"custom_cnr_early_in_pool",
			current_in_pool=early_in_pool,
			exclude_name=exclude,
		)


def apply_late_early_to_attendance(doc, apply_unexcused_status=True):
	"""
	Store custom_late_mins / custom_early_mins and set late_entry / early_exit
	using Nepal Compliance Settings grace minutes (not Shift Type grace alone).

	Minor (grace→max) without approved app: in occurrence pool.
	The Nth pool day (settings) is ½P = Half Day / half_day_status=Absent,
	or 1P = Absent when full-day escalation is on.
	Major unexcused: Half Day (half_day_status=Present) with unexcused flags.
	"""
	if not doc.employee or not doc.attendance_date:
		return

	settings = get_hr_settings()
	grace = cint(getattr(settings, "late_early_grace_mins", None) or 15)
	max_delay = cint(getattr(settings, "late_early_max_delay_mins", None) or 60)
	penalty_on = cint(getattr(settings, "enable_late_early_penalty", None) or 0)

	# C&R Half Day we may restore when an approved slip excuses the delay.
	was_cnr_half_day = (
		(doc.status or "") == "Half Day"
		and not getattr(doc, "leave_type", None)
		and (getattr(doc, "half_day_status", None) or "Present") == "Present"
		and (
			cint(getattr(doc, "custom_cnr_unexcused_late", 0))
			or cint(getattr(doc, "custom_cnr_unexcused_early", 0))
			or cint(getattr(doc, "late_entry", 0))
			or cint(getattr(doc, "early_exit", 0))
		)
	)

	# Half-day leave with scaling on: the worked half is judged as a half-length
	# day -- halved grace and max delay, measured against that half, not the
	# whole shift. None keeps today's rule, where the leave excuses the day.
	from nepal_hrms.custom_code.half_day import late_early_context, minutes_against

	half_ctx = late_early_context(doc)
	if half_ctx:
		grace = flt(grace) * half_ctx.factor
		max_delay = flt(max_delay) * half_ctx.factor
		late_mins, early_mins = minutes_against(
			half_ctx, earliest_arrival(doc), getattr(doc, "out_time", None)
		)
	else:
		late_mins, early_mins = compute_late_early_minutes(
			doc.employee,
			doc.attendance_date,
			in_time=earliest_arrival(doc),
			out_time=getattr(doc, "out_time", None),
			shift=getattr(doc, "shift", None),
		)

	if hasattr(doc, "custom_late_mins"):
		doc.custom_late_mins = late_mins
	if hasattr(doc, "custom_early_mins"):
		doc.custom_early_mins = early_mins

	# Beyond grace => flagged for payroll / C&R rules
	doc.late_entry = 1 if late_mins > grace else 0
	doc.early_exit = 1 if early_mins > grace else 0

	from nepal_hrms.custom_code.attendance_holiday import clear_cnr_flags, holiday_info
	from nepal_hrms.custom_code.policy_escape import has_policy_escape

	# A holiday or weekly off never produces a late entry, an early exit, an
	# occurrence-pool slot or a penalty -- even when the employee actually worked.
	# The test is on the DATE, not the status: apply_holiday_sandwich_status has
	# already rewritten a worked holiday to "Present", so a status check would miss
	# exactly the case this guard exists for.
	holiday = holiday_info(doc.employee, doc.attendance_date)
	if holiday.is_holiday:
		previous_penalty = (getattr(doc, "custom_cnr_pool_penalty", None) or "").strip()
		# keep_minutes: the raw timing stays readable on the day popup.
		# reset_half_day_status=False: do not disturb a genuine half-day leave row.
		clear_cnr_flags(doc, keep_minutes=True, reset_half_day_status=False)
		if hasattr(doc, "custom_cnr_pool_penalty"):
			doc.custom_cnr_pool_penalty = ""
		_refresh_month_pool_counts(doc, 0, 0)
		# custom_cnr_pool_penalty is the only signal the period sweep uses to
		# recognise a status it wrote itself, so clearing it strands any Half Day /
		# Absent we put here. Undo that in the same pass or nothing ever will.
		if apply_unexcused_status and (
			was_cnr_half_day or previous_penalty in ("half", "full")
		):
			from nepal_hrms.custom_code.attendance_holiday import has_checkins

			if has_checkins(doc.employee, doc.attendance_date, getattr(doc, "name", None)):
				doc.status = "Present"
			else:
				doc.status = "Weekly Off" if holiday.weekly_off else "Holiday"
			if hasattr(doc, "half_day_status"):
				doc.half_day_status = None
		return

	escape_late_early = has_policy_escape(
		doc.employee, "escape_late_early", doc.attendance_date
	)

	# Opt-in: an approved Attendance Request fully excuses the day. Gated on
	# penalty_on so the excuse cannot zero core HRMS fields on a site running
	# without the penalty engine.
	attendance_request_excused = False
	attendance_request = None
	if (
		penalty_on
		and not escape_late_early
		and cint(getattr(settings, "excuse_late_early_on_attendance_request", 0) or 0)
	):
		attendance_request = get_approved_attendance_request(
			doc.employee, doc.attendance_date
		)
		if attendance_request:
			attendance_request_excused = True
			escape_late_early = True

	unexcused_late = 0
	unexcused_early = 0
	late_in_pool = 0
	early_in_pool = 0

	if escape_late_early:
		# Read before the flags below are cleared: they are the evidence.
		escaped_penalty = was_cnr_half_day or _looks_like_cnr_penalty(doc)
		if attendance_request_excused:
			# The policy escape deliberately keeps these for visibility; the
			# Attendance Request excuse is a full excuse, so the flags go too.
			doc.late_entry = 0
			doc.early_exit = 0
		# Keep minutes / late_entry flags for visibility; no pool, unexcused, or Half Day
		if hasattr(doc, "custom_cnr_unexcused_late"):
			doc.custom_cnr_unexcused_late = 0
		if hasattr(doc, "custom_cnr_unexcused_early"):
			doc.custom_cnr_unexcused_early = 0
		if hasattr(doc, "custom_cnr_late_in_pool"):
			doc.custom_cnr_late_in_pool = 0
		if hasattr(doc, "custom_cnr_early_in_pool"):
			doc.custom_cnr_early_in_pool = 0
		_refresh_month_pool_counts(doc, 0, 0)
		previous_penalty = (getattr(doc, "custom_cnr_pool_penalty", None) or "").strip()
		if hasattr(doc, "custom_cnr_pool_penalty"):
			doc.custom_cnr_pool_penalty = ""
		if apply_unexcused_status and (escaped_penalty or previous_penalty in ("half", "full")):
			doc.status = "Present"
			if hasattr(doc, "half_day_status"):
				doc.half_day_status = None
		return

	# A leave row is skipped -- unless it is a scaled half-day, whose worked half
	# is judged here. Its status stays out of reach either way: _protected_status
	# keeps penalties off leave rows, so this only sets flags and pool counts.
	if penalty_on and (not getattr(doc, "leave_type", None) or half_ctx) and (
		doc.status or ""
	) not in (
		"On Leave",
		"Work From Home",
	):
		if doc.late_entry:
			lea = get_approved_application(
				"Late Entry Application", doc.employee, doc.attendance_date
			)
			if not delay_excused_for_attendance_status(
				late_mins, lea, doc.employee, doc.attendance_date, grace, max_delay,
				excuse_half_day_leave=not half_ctx,
			):
				unexcused_late = 1
			if delay_in_occurrence_pool(late_mins, lea, grace, max_delay, settings):
				late_in_pool = 1
		if doc.early_exit:
			eea = get_approved_application(
				"Early Exit Application", doc.employee, doc.attendance_date
			)
			if not delay_excused_for_attendance_status(
				early_mins, eea, doc.employee, doc.attendance_date, grace, max_delay,
				excuse_half_day_leave=not half_ctx,
			):
				unexcused_early = 1
			if delay_in_occurrence_pool(early_mins, eea, grace, max_delay, settings):
				early_in_pool = 1

	if hasattr(doc, "custom_cnr_unexcused_late"):
		doc.custom_cnr_unexcused_late = unexcused_late
	if hasattr(doc, "custom_cnr_unexcused_early"):
		doc.custom_cnr_unexcused_early = unexcused_early
	if hasattr(doc, "custom_cnr_late_in_pool"):
		doc.custom_cnr_late_in_pool = late_in_pool
	if hasattr(doc, "custom_cnr_early_in_pool"):
		doc.custom_cnr_early_in_pool = early_in_pool

	# Month-to-date pool counts (include this row; exclude self from DB count)
	_refresh_month_pool_counts(doc, late_in_pool, early_in_pool)

	if not apply_unexcused_status:
		return

	pool_kind = ""
	if penalty_on and not _protected_status(doc):
		pool_kind = _current_doc_pool_penalty(doc, settings) or ""
	_apply_pool_or_major_status(
		doc,
		pool_kind,
		unexcused_late or unexcused_early,
		was_cnr_half_day,
	)


def get_attendance_for_employee_date(employee, attendance_date):
	return frappe.db.get_value(
		"Attendance",
		{
			"employee": employee,
			"attendance_date": getdate(attendance_date),
			"docstatus": ["<", 2],
		},
		"name",
	)


def fill_application_from_attendance(doc):
	"""When Attendance is linked (e.g. from Connections), copy employee/date/company/times."""
	if not doc.meta.has_field("attendance") or not doc.attendance:
		return

	att = frappe.db.get_value(
		"Attendance",
		doc.attendance,
		["employee", "attendance_date", "company", "in_time", "out_time", "docstatus"],
		as_dict=True,
	)
	if not att or cint(att.docstatus) == 2:
		return

	if not doc.employee:
		doc.employee = att.employee
	if not doc.attendance_date:
		doc.attendance_date = att.attendance_date
	if doc.meta.has_field("company") and not doc.company and att.company:
		doc.company = att.company

	if doc.doctype == "Late Entry Application" and doc.meta.has_field("late_entry_time") and att.in_time:
		doc.late_entry_time = get_time(att.in_time)
	if doc.doctype == "Early Exit Application" and doc.meta.has_field("early_exit_time") and att.out_time:
		doc.early_exit_time = get_time(att.out_time)

	# Keep employee/date consistent with linked Attendance
	if doc.employee and doc.employee != att.employee:
		frappe.throw(
			_("Employee must match linked Attendance {0}").format(doc.attendance)
		)
	if doc.attendance_date and getdate(doc.attendance_date) != getdate(att.attendance_date):
		frappe.throw(
			_("Attendance Date must match linked Attendance {0}").format(doc.attendance)
		)


def link_application_to_attendance(doc):
	"""Resolve and set Attendance link on Late/Early/OOO applications."""
	fill_application_from_attendance(doc)

	if not doc.employee or not doc.attendance_date:
		return

	attendance_name = get_attendance_for_employee_date(doc.employee, doc.attendance_date)
	if attendance_name:
		doc.attendance = attendance_name
	elif doc.meta.has_field("attendance") and not doc.attendance:
		# Leave empty if attendance not marked yet; payroll still matches by date
		pass


def sync_attendance_after_application(doc):
	"""Recompute linked Attendance status/flags after LEA/EEA/OOO submit or cancel."""
	attendance_name = getattr(doc, "attendance", None)
	if not attendance_name and doc.employee and doc.attendance_date:
		attendance_name = get_attendance_for_employee_date(doc.employee, doc.attendance_date)
	if not attendance_name:
		return
	recompute_attendance_late_early(attendance_name, update_status=True, source_doc=doc)


def _cnr_snapshot(doc):
	"""Status/flag fields used to decide whether a timeline comment is needed."""
	return frappe._dict(
		status=(doc.status or "").strip() or None,
		half_day_status=getattr(doc, "half_day_status", None) or None,
		late_entry=cint(getattr(doc, "late_entry", 0)),
		early_exit=cint(getattr(doc, "early_exit", 0)),
		custom_cnr_unexcused_late=cint(getattr(doc, "custom_cnr_unexcused_late", 0)),
		custom_cnr_unexcused_early=cint(getattr(doc, "custom_cnr_unexcused_early", 0)),
		custom_cnr_late_in_pool=cint(getattr(doc, "custom_cnr_late_in_pool", 0)),
		custom_cnr_early_in_pool=cint(getattr(doc, "custom_cnr_early_in_pool", 0)),
		custom_cnr_pool_penalty=getattr(doc, "custom_cnr_pool_penalty", None) or "",
		custom_late_mins=cint(getattr(doc, "custom_late_mins", 0)),
		custom_early_mins=cint(getattr(doc, "custom_early_mins", 0)),
	)


def _cnr_tracking_changed(before, after):
	if not before or not after:
		return False
	return (
		(before.status or None) != (after.status or None)
		or cint(before.late_entry) != cint(after.late_entry)
		or cint(before.early_exit) != cint(after.early_exit)
		or cint(before.custom_cnr_unexcused_late) != cint(after.custom_cnr_unexcused_late)
		or cint(before.custom_cnr_unexcused_early) != cint(after.custom_cnr_unexcused_early)
		or cint(before.custom_cnr_late_in_pool) != cint(after.custom_cnr_late_in_pool)
		or cint(before.custom_cnr_early_in_pool) != cint(after.custom_cnr_early_in_pool)
		or cint(before.custom_late_mins) != cint(after.custom_late_mins)
		or cint(before.custom_early_mins) != cint(after.custom_early_mins)
	)


def add_cnr_attendance_comment(name, message):
	"""Write a Comment on Attendance for C&R status tracking."""
	if not name or not message:
		return
	try:
		frappe.get_doc("Attendance", name).add_comment("Comment", text=message)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "C&R Attendance Comment Failed")


def _source_app_label(source_doc):
	if not source_doc:
		return None
	work = getattr(source_doc, "type_of_work", None) or ""
	label = f"{source_doc.doctype} {source_doc.name}"
	if work:
		label = f"{label} ({work})"
	return label


def _source_app_event(source_doc):
	"""submit | cancel | None — based on docstatus after the triggering hook."""
	if not source_doc:
		return None
	ds = cint(getattr(source_doc, "docstatus", 0))
	if ds == 2:
		return "cancel"
	if ds == 1:
		return "submit"
	return None


def build_cnr_attendance_comment(before, after, source_doc=None, employee=None, attendance_date=None):
	"""
	Build a single timeline message when status/unexcused/pool flags change.
	Returns None if nothing meaningful changed.
	"""
	if not _cnr_tracking_changed(before, after):
		return None

	old_status = before.status or "—"
	new_status = after.status or "—"
	late_mins = cint(after.custom_late_mins)
	early_mins = cint(after.custom_early_mins)
	parts = [_("Rechecked: Status {0} → {1}.").format(old_status, new_status)]

	source_label = _source_app_label(source_doc)
	event = _source_app_event(source_doc)

	became_half = new_status == "Half Day" and old_status != "Half Day"
	restored_present = new_status == "Present" and old_status == "Half Day"
	flags_only = old_status == new_status

	late_pool_cleared = cint(before.custom_cnr_late_in_pool) and not cint(after.custom_cnr_late_in_pool)
	early_pool_cleared = cint(before.custom_cnr_early_in_pool) and not cint(after.custom_cnr_early_in_pool)
	late_pool_added = not cint(before.custom_cnr_late_in_pool) and cint(after.custom_cnr_late_in_pool)
	early_pool_added = not cint(before.custom_cnr_early_in_pool) and cint(after.custom_cnr_early_in_pool)

	delay_bits = []
	if late_mins:
		delay_bits.append(_("late {0} mins").format(late_mins))
	if early_mins:
		delay_bits.append(_("early {0} mins").format(early_mins))
	delay_txt = ", ".join(delay_bits) if delay_bits else _("no recorded delay minutes")

	def _cap(s):
		return s[:1].upper() + s[1:] if s else s

	if late_pool_cleared or early_pool_cleared:
		pool_bits = []
		if late_pool_cleared:
			pool_bits.append(_("late"))
		if early_pool_cleared:
			pool_bits.append(_("early"))
		pool_label = " / ".join(pool_bits)
		if source_label and event == "submit":
			parts.append(
				_(
					"{0} pool cleared: {1} approved. Removed from monthly occurrence count."
				).format(_cap(pool_label), source_label)
			)
		elif source_label:
			parts.append(
				_("{0} pool cleared via {1}. Removed from monthly occurrence count.").format(
					_cap(pool_label), source_label
				)
			)
		else:
			parts.append(
				_("{0} pool cleared. Removed from monthly occurrence count.").format(
					_cap(pool_label)
				)
			)

	if late_pool_added or early_pool_added:
		pool_bits = []
		if late_pool_added:
			pool_bits.append(_("late"))
		if early_pool_added:
			pool_bits.append(_("early"))
		pool_label = " / ".join(pool_bits)
		if source_label and event == "cancel":
			parts.append(
				_(
					"{0} pool restored: {1} cancelled. Added back to monthly occurrence count."
				).format(_cap(pool_label), source_label)
			)
		else:
			parts.append(
				_("{0} counted in monthly occurrence pool ({1}).").format(
					_cap(pool_label), delay_txt
				)
			)

	if restored_present:
		excuse_label = source_label
		if not excuse_label and employee and attendance_date:
			for dt in ("Late Entry Application", "Early Exit Application"):
				app = get_approved_application(dt, employee, attendance_date)
				if app:
					work = app.type_of_work or ""
					excuse_label = f"{dt} {app.name}" + (f" ({work})" if work else "")
					break
		if excuse_label:
			parts.append(_("Excused by {0}. {1}.").format(excuse_label, _cap(delay_txt)))
		else:
			parts.append(_("Delay excused ({0}).").format(delay_txt))
	elif became_half or (
		flags_only
		and (after.custom_cnr_unexcused_late or after.custom_cnr_unexcused_early)
		and not (late_pool_cleared or early_pool_cleared or late_pool_added or early_pool_added)
	):
		reasons = []
		if after.custom_cnr_unexcused_late:
			reasons.append(_("unexcused late {0} mins").format(late_mins))
		if after.custom_cnr_unexcused_early:
			reasons.append(_("unexcused early {0} mins").format(early_mins))
		if reasons:
			parts.append(_cap(", ".join(reasons)) + ".")
		if source_label and event == "cancel":
			parts.append(
				_("{0} cancelled or no longer excuses this delay.").format(source_label)
			)
		elif not source_label:
			parts.append(_("No approved Late Entry / Early Exit Application."))
		else:
			parts.append(_("Related: {0}.").format(source_label))
	elif (
		source_label
		and not (late_pool_cleared or early_pool_cleared or late_pool_added or early_pool_added)
	):
		parts.append(_("Related: {0} ({1}).").format(source_label, delay_txt))
	elif not (late_pool_cleared or early_pool_cleared or late_pool_added or early_pool_added):
		parts.append(_("Updated late/early flags ({0}).").format(delay_txt))

	return " ".join(parts)


def maybe_comment_cnr_attendance_change(
	name, before, after, source_doc=None, employee=None, attendance_date=None
):
	"""Post a Comment when status or unexcused flags changed."""
	message = build_cnr_attendance_comment(
		before,
		after,
		source_doc=source_doc,
		employee=employee,
		attendance_date=attendance_date,
	)
	if message:
		add_cnr_attendance_comment(name, message)
	return message


def calculate_ooo_hours_from_checkins(employee, attendance_date, approved_only=True):
	"""Sum OOO Work IN/OUT pair hours for a day. By default only approved OOO counts."""
	attendance_date = getdate(attendance_date)
	filters = {
		"employee": employee,
		"time": ["between", [f"{attendance_date} 00:00:00", f"{attendance_date} 23:59:59"]],
		"custom_attendance_type": "OOO Work",
	}
	if approved_only:
		filters["custom_is_approved"] = 1

	checkins = frappe.get_all(
		"Employee Checkin",
		filters=filters,
		fields=["time", "log_type", "custom_is_approved"],
		order_by="time asc",
	)

	total_hours = 0.0
	last_in = None
	for c in checkins:
		if c.log_type == "IN":
			last_in = c.time
		elif c.log_type == "OUT" and last_in:
			total_hours += time_diff_in_hours(c.time, last_in)
			last_in = None
	return flt(total_hours, 2)


def max_out_in_gap_mins(checkins) -> int:
	"""Return the largest gap in minutes between an OUT and the next IN."""
	if not checkins:
		return 0

	max_gap = 0
	last_out = None
	for checkin in checkins:
		log_type = (
			getattr(checkin, "log_type", None)
			or (checkin.get("log_type") if hasattr(checkin, "get") else None)
			or ""
		).upper()
		timestamp = getattr(checkin, "time", None) or (
			checkin.get("time") if hasattr(checkin, "get") else None
		)
		if not timestamp:
			continue
		timestamp = get_datetime(timestamp)
		if log_type == "OUT":
			last_out = timestamp
		elif log_type == "IN" and last_out:
			max_gap = max(
				max_gap,
				cint(round((timestamp - last_out).total_seconds() / 60.0)),
			)
			last_out = None
	return max_gap


def ooo_required_from_checkins(checkins, grace_mins=None) -> bool:
	"""Return whether a mid-day OUT→IN gap exceeds the configured grace."""
	if grace_mins is None:
		settings = get_hr_settings()
		grace_mins = cint(getattr(settings, "late_early_grace_mins", None) or 15)
	return max_out_in_gap_mins(checkins) > cint(grace_mins)


def set_attendance_ooo_hours(employee, attendance_date, hours=None):
	"""Persist custom_ooo_hours on Attendance when field exists."""
	attendance_name = get_attendance_for_employee_date(employee, attendance_date)
	if not attendance_name:
		return

	if not frappe.get_meta("Attendance").has_field("custom_ooo_hours"):
		return

	if hours is None:
		hours = calculate_ooo_hours_from_checkins(employee, attendance_date)

	frappe.db.set_value("Attendance", attendance_name, "custom_ooo_hours", flt(hours, 2))


def get_approved_application(doctype, employee, attendance_date):
	return frappe.db.get_value(
		doctype,
		{
			"employee": employee,
			"attendance_date": getdate(attendance_date),
			"status": "Approved",
			"docstatus": 1,
		},
		["name", "type_of_work"],
		as_dict=True,
	)


def _attendance_request_is_approved(row):
	"""Submitted requests predating the custom status field carry SQL NULL.

	A ["in", ["Approved", ""]] filter would not match those, so approval is decided
	in Python. before_submit sets Approved on submit, so docstatus 1 implies it.
	Mirrors _application_bucket in the Monthly Attendance Sheet BS report.
	"""
	return ((row.get("status") if isinstance(row, dict) else getattr(row, "status", None)) or "Approved") == "Approved"


def get_approved_attendance_request(employee, attendance_date):
	"""Approved Attendance Request covering this date, or None.

	Separate from get_approved_application because Attendance Request is ranged
	(from_date / to_date), not a single attendance_date column.
	"""
	if not employee or not attendance_date:
		return None
	day = getdate(attendance_date)
	rows = frappe.get_all(
		"Attendance Request",
		filters={
			"employee": employee,
			"docstatus": 1,
			"from_date": ["<=", day],
			"to_date": [">=", day],
		},
		fields=["name", "status", "from_date", "to_date", "half_day", "half_day_date"],
		ignore_permissions=True,
	)
	for row in rows:
		if _attendance_request_is_approved(row):
			return row
	return None


def approved_attendance_request_dates(employee, start_date, end_date):
	"""Set of dates in [start, end] covered by an approved Attendance Request.

	One query per (employee, range), request-cached -- the payroll and report paths
	iterate whole periods and must not call the single-date lookup per day.
	"""
	start = getdate(start_date)
	end = getdate(end_date)
	if not employee or start > end:
		return set()

	cache = getattr(frappe.local, "_nepal_approved_attendance_requests", None)
	if cache is None:
		cache = frappe.local._nepal_approved_attendance_requests = {}
	key = f"{employee}::{start}..{end}"
	if key in cache:
		return cache[key]

	rows = frappe.get_all(
		"Attendance Request",
		filters={
			"employee": employee,
			"docstatus": 1,
			"from_date": ["<=", end],
			"to_date": [">=", start],
		},
		fields=["name", "status", "from_date", "to_date"],
		ignore_permissions=True,
	)

	dates = set()
	for row in rows:
		if not _attendance_request_is_approved(row):
			continue
		day = max(getdate(row.from_date), start)
		last = min(getdate(row.to_date), end)
		while day <= last:
			dates.add(day)
			day = add_days(day, 1)

	cache[key] = dates
	return dates


def clear_attendance_request_cache(employee=None):
	"""Drop the request-local approved_attendance_request_dates cache."""
	cache = getattr(frappe.local, "_nepal_approved_attendance_requests", None)
	if cache is None:
		return
	if employee is None:
		frappe.local._nepal_approved_attendance_requests = {}
		return
	prefix = f"{employee}::"
	for key in [k for k in cache if k.startswith(prefix)]:
		cache.pop(key, None)


def classify_delay(mins, grace, max_delay):
	"""
	Return None (within grace), 'minor', or 'major'.
	mins must already be raw minutes from shift start/end.
	"""
	mins = cint(mins)
	# flt, not cint: a half-day's grace is half the setting, and 15 → 7.5 must not
	# round to 7 and start charging a minute early.
	grace = flt(grace)
	max_delay = flt(max_delay)
	if mins <= grace:
		return None
	if mins > max_delay:
		return "major"
	return "minor"


PENALTY_HALF_MARK = "½P"
PENALTY_FULL_MARK = "1P"


def occurrence_half_days(count, initial_grace, subsequent_step):
	"""
	C&R occurrence pool:
	- First `initial_grace` lates are free (default 2 → first 2 free, 3rd half-day).
	- Next occurrence after the free pool => 1 half-day.
	- Next `subsequent_step` occurrences are free after that penalty (default 2).
	- Then another half-day, and the pattern repeats every (subsequent_step + 1).
	"""
	count = cint(count)
	initial_grace = cint(initial_grace) or 2
	subsequent_step = cint(subsequent_step) or 2
	if count <= initial_grace:
		return 0
	# Distance past the free pool; penalties every (step + 1) starting at 1
	return 1 + ((count - initial_grace - 1) // (subsequent_step + 1))


def occurrence_is_penalty(index, initial_grace, subsequent_step):
	"""True when the 1-based pool occurrence is a penalty slot (3rd, 6th, …)."""
	index = cint(index)
	initial_grace = cint(initial_grace) or 2
	subsequent_step = cint(subsequent_step) or 2
	if index <= 0 or index <= initial_grace:
		return False
	return ((index - initial_grace - 1) % (subsequent_step + 1)) == 0


def assign_pool_penalty_dates(occurrences, initial_grace, subsequent_step, escalated=False):
	"""Map occurrence dates to half/full penalty marks. Dates may repeat."""
	assigned = {}
	kind = "full" if escalated else "half"
	for i, day in enumerate(occurrences, start=1):
		if not occurrence_is_penalty(i, initial_grace, subsequent_step):
			continue
		day = getdate(day)
		if assigned.get(day) != "full":
			assigned[day] = kind
	return assigned


def assign_employee_pool_penalties(day_flags, settings):
	"""
	Assign ½P / 1P to pool days for one employee.

	day_flags: iterable of (date, late_in_pool, early_in_pool)
	Returns {date: "half"|"full"}.
	"""
	initial = cint(getattr(settings, "initial_grace_occurrences", 2) or 2)
	step = cint(getattr(settings, "subsequent_grace_step_occurrences", 2) or 2)
	combine = cint(getattr(settings, "combine_late_and_early_pool", 0) or 0)
	escalate = cint(getattr(settings, "enable_late_full_day_escalation", 0) or 0)
	after = cint(getattr(settings, "late_full_day_after_occurrences", 5) or 5)

	rows = sorted(
		(
			(getdate(day), cint(late), cint(early))
			for day, late, early in (day_flags or [])
			if cint(late) or cint(early)
		),
		key=lambda item: item[0],
	)
	if combine:
		occurrences = []
		for day, late, early in rows:
			if late:
				occurrences.append(day)
			if early:
				occurrences.append(day)
		return assign_pool_penalty_dates(
			occurrences, initial, step, bool(escalate and len(occurrences) > after)
		)

	late_map = assign_pool_penalty_dates(
		[day for day, late, _early in rows if late],
		initial,
		step,
		bool(escalate and sum(late for _day, late, _early in rows if late) > after),
	)
	early_map = assign_pool_penalty_dates(
		[day for day, _late, early in rows if early],
		initial,
		step,
		bool(escalate and sum(early for _day, _late, early in rows if early) > after),
	)
	merged = dict(late_map)
	for day, kind in early_map.items():
		if merged.get(day) != "full":
			merged[day] = kind
	return merged


def penalty_mark(kind):
	if kind == "full":
		return PENALTY_FULL_MARK
	if kind == "half":
		return PENALTY_HALF_MARK
	return ""


def split_occurrence_penalty(
	minor_count,
	major_count,
	initial_grace,
	subsequent_step,
	enable_full_day_escalation=0,
	full_day_after_occurrences=5,
):
	"""Return payroll-aligned half/full-day penalty equivalents for one pool."""
	minor_count = cint(minor_count)
	major_count = cint(major_count)
	minor_penalty = occurrence_half_days(
		minor_count, initial_grace, subsequent_step
	)
	escalated = bool(
		cint(enable_full_day_escalation)
		and minor_count > cint(full_day_after_occurrences)
	)
	if escalated:
		return frappe._dict(
			half_days=float(major_count),
			full_days=float(minor_penalty),
			minor_penalty=float(minor_penalty),
			escalated=True,
		)
	return frappe._dict(
		half_days=float(major_count + minor_penalty),
		full_days=0.0,
		minor_penalty=float(minor_penalty),
		escalated=False,
	)


def free_occurrences_remaining(count, initial_grace, subsequent_step):
	"""How many more free pool slots before the next half-day penalty."""
	count = cint(count)
	initial_grace = cint(initial_grace) or 2
	subsequent_step = cint(subsequent_step) or 2
	if count < initial_grace:
		return initial_grace - count
	# past=0 when count == initial_grace → next occurrence is the first half-day
	past = count - initial_grace
	if past == 0:
		return 0
	# After first threshold: repeating (1 penalty + subsequent_step free)
	idx = (past - 1) % (subsequent_step + 1)
	if idx == 0:
		return subsequent_step
	return subsequent_step - idx


def recompute_attendance_late_early(name, update_status=True, source_doc=None, post_comment=True):
	"""
	Recompute late/early minutes and C&R flags for an Attendance (including submitted).
	Uses db.set_value so submitted docs can be fixed without cancel/amend.
	Posts a timeline Comment when status, unexcused, or pool flags change
	(unless post_comment=False — e.g. bulk Recalculate writes its own comment).
	Returns the values written.
	"""
	doc = frappe.get_doc("Attendance", name)
	before = _cnr_snapshot(doc)
	apply_late_early_to_attendance(doc, apply_unexcused_status=update_status)
	after = _cnr_snapshot(doc)

	meta = frappe.get_meta("Attendance")
	values = {
		"late_entry": cint(doc.late_entry),
		"early_exit": cint(doc.early_exit),
	}
	for field in (
		"custom_late_mins",
		"custom_early_mins",
		"custom_cnr_unexcused_late",
		"custom_cnr_unexcused_early",
		"custom_cnr_late_in_pool",
		"custom_cnr_early_in_pool",
		"custom_cnr_month_late_pool_count",
		"custom_cnr_month_early_pool_count",
	):
		if meta.has_field(field):
			values[field] = cint(getattr(doc, field, 0))
	if meta.has_field("custom_cnr_pool_penalty"):
		values["custom_cnr_pool_penalty"] = getattr(doc, "custom_cnr_pool_penalty", None) or ""

	if update_status and not _protected_status(doc):
		values["status"] = doc.status
		if hasattr(doc, "half_day_status"):
			values["half_day_status"] = doc.half_day_status or None

	frappe.db.set_value("Attendance", name, values, update_modified=False)
	if update_status:
		sync_month_pool_penalties(doc.employee, doc.attendance_date, current_name=name)

	if update_status and post_comment:
		maybe_comment_cnr_attendance_change(
			name,
			before,
			after,
			source_doc=source_doc,
			employee=doc.employee,
			attendance_date=doc.attendance_date,
		)

	return values


@frappe.whitelist()
def recalculate_attendance_late_early(name):
	"""Desk button: recompute minutes/flags/status for one Attendance."""
	if not name:
		frappe.throw(_("Attendance name is required"))
	frappe.has_permission("Attendance", "write", throw=True)
	values = recompute_attendance_late_early(name, update_status=True)
	return {"ok": 1, "values": values}
