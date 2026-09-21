# -*- coding: utf-8 -*-
"""Leave Application sandwich rule (aligned with attendance is_sandwiched)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate

from nepal_hrms.custom_code.attendance_holiday import (
	_day_is_full_leave_or_absent,
	get_adjacent_working_day,
	is_holiday_or_weekend,
)


def day_is_full_leave_or_absent_for_sandwich(employee, date_obj, current_leave=None):
	"""Full-day leave or absent on a working day; includes the in-flight Leave Application range."""
	day = getdate(date_obj)
	if current_leave and current_leave.get("from_date") and current_leave.get("to_date"):
		from_d = getdate(current_leave["from_date"])
		to_d = getdate(current_leave["to_date"])
		if from_d <= day <= to_d:
			if cint(current_leave.get("half_day")):
				half_day_date = current_leave.get("half_day_date") or current_leave.get("from_date")
				if half_day_date and getdate(half_day_date) == day:
					return False
			return True

	return _day_is_full_leave_or_absent(employee, day)


def _current_leave_payload(doc):
	if not doc:
		return None
	if isinstance(doc, dict):
		return doc
	return {
		"name": doc.name,
		"from_date": doc.from_date,
		"to_date": doc.to_date,
		"half_day": doc.half_day,
		"half_day_date": doc.half_day_date,
	}


def _format_holiday_ranges(dates):
	if not dates:
		return ""
	dates = sorted({getdate(d) for d in dates})
	ranges = []
	range_start = dates[0]
	prev = dates[0]
	for day in dates[1:]:
		if (day - prev).days == 1:
			prev = day
			continue
		ranges.append((range_start, prev))
		range_start = day
		prev = day
	ranges.append((range_start, prev))

	parts = []
	for start, end in ranges:
		parts.append(str(start) if start == end else f"{start} to {end}")
	return ", ".join(parts)


def evaluate_leave_sandwich(employee, from_date, to_date, current_leave=None):
	"""
	Return sandwich evaluation for a Leave Application date range.

	violation: uncovered holiday/weekend sandwiched between leave/absent on both sides,
		where *this* application is one of the two anchors. A sandwich standing
		entirely on other days is pre-existing — it belongs to the attendance side
		and must not block an unrelated application filed nearby.
	warning: leave touches a weekend/holiday but no true sandwich violation
	"""
	from_d = getdate(from_date)
	to_d = getdate(to_date)
	if to_d < from_d:
		from_d, to_d = to_d, from_d

	leave_ctx = _current_leave_payload(current_leave)
	uncovered = []

	scan_start = add_days(from_d, -14)
	scan_end = add_days(to_d, 14)
	day = scan_start
	while day <= scan_end:
		if is_holiday_or_weekend(employee, day) and not (from_d <= day <= to_d):
			prev_wd = get_adjacent_working_day(employee, day, direction=-1)
			next_wd = get_adjacent_working_day(employee, day, direction=1)
			# Only this application's own sandwiches are its problem: at least one
			# anchoring working day has to sit inside the range being validated.
			anchored_here = (from_d <= prev_wd <= to_d) or (from_d <= next_wd <= to_d)
			if (
				anchored_here
				and day_is_full_leave_or_absent_for_sandwich(employee, prev_wd, leave_ctx)
				and day_is_full_leave_or_absent_for_sandwich(employee, next_wd, leave_ctx)
			):
				uncovered.append(day)
		day = add_days(day, 1)

	violation = bool(uncovered)
	holiday_span = _format_holiday_ranges(uncovered)

	message = None
	if violation:
		message = _(
			"Sandwich Rule Violation: weekend/holiday dates ({0}) fall between leave or absence on both sides. Include those days in this Leave Application."
		).format(holiday_span)

	is_prev_holiday = is_holiday_or_weekend(employee, add_days(from_d, -1))
	is_next_holiday = is_holiday_or_weekend(employee, add_days(to_d, 1))
	warning = not violation and (is_prev_holiday or is_next_holiday)
	warning_message = None
	if warning:
		warning_message = _(
			"Notice: This leave starts or ends next to a weekend/holiday. If you also take leave on the adjacent working day, intervening holidays may count as leave under the Sandwich Rule."
		)

	return {
		"violation": violation,
		"warning": warning,
		"uncovered_holidays": [str(d) for d in sorted({getdate(d) for d in uncovered})],
		"holiday_span": holiday_span,
		"message": message,
		"warning_message": warning_message,
	}
