# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""One employee's attendance totals for one window, using the report's own rules.

The Monthly Attendance Sheet BS report is the reference implementation of "how many
days was this person present". This wraps it for a single employee so the PWA can
render the same numbers instead of counting them again in JavaScript and getting a
different answer.

It deliberately reuses the report's batched loaders rather than reimplementing the
day loop -- forking that logic is the bug this module exists to remove.
"""

import frappe
from frappe.utils import add_days, cint, flt, getdate, today

from nepal_hrms.custom_code.attendance_classification import DAY_COUNT_DATE_FIELDS

# Allowlist, not a denylist. The raw report row carries one day_YYYY_MM_DD JSON blob
# per day, each holding bar_data with per-minute segments -- easily 150 KB for a
# month, none of which a summary consumer reads. An allowlist also means a new
# day_* field added to the report later cannot start leaking into API responses.
TOTAL_FIELDS = (
	"total_days_in_period",
	"total_present", "present_full", "present_half",
	"total_absent", "absent_full", "absent_half",
	"penalty_days", "penalty_full", "penalty_half",
	"penalty_full_days", "penalty_half_days", "penalty_paid_deduction",
	"lwp_days", "lwp_full", "lwp_half",
	"paid_leave_days", "paid_leave_full", "paid_leave_half",
	"annual_home_leave_days", "sick_leave_days", "other_paid_leave_days",
	"total_holiday", "holiday_extra_present", "holiday_extra_hours",
	"total_no_of_days", "paid_flag", "unmarked", "unclassified_leave",
	"sandwich", "sandwich_absent",
	"payable_days", "payable_days_policy", "payable_days_mismatch",
	"paid_days_period_method", "paid_days_component_method", "paid_days_daily_method",
)

LATE_EARLY_FIELDS = (
	"total_late_entry", "total_early_exit", "total_grace_late", "total_unexcused_late",
)

BREAKDOWN_FIELDS = {
	"paid_leave": "leave_breakdown",
	"lwp": "lwp_breakdown",
	"other_paid": "other_paid_breakdown",
	"unconfigured_paid_leave": "unconfigured_paid_leave_breakdown",
}


def _empty_totals():
	return {field: 0 for field in TOTAL_FIELDS}


def _upcoming_leave(leave_day_map, employee, current_date):
	"""Approved / pending leave on days the audit has not reached.

	Held apart from the totals on purpose: the report excludes future days, and
	quietly folding them in is one of the ways the PWA used to disagree with it.

	The cut is `day > today()`, not `day > audit_through_date`. A day excluded from
	the audit *because it is an unmarked today* is neither audited nor upcoming --
	it is today, and genuinely undetermined. That one-day gap is intentional.
	"""
	out = {
		"approved_leave_days": 0.0,
		"pending_leave_days": 0.0,
		"approved_leave_types": {},
		"pending_leave_types": {},
	}
	for (emp, day), details in (leave_day_map or {}).items():
		if emp != employee or getdate(day) <= current_date or not details:
			continue
		# Same "first application wins" rule the report's day loop uses.
		detail = details[0]
		bucket = detail.get("status")
		if bucket not in ("approved", "pending"):
			continue
		half_day_date = detail.get("half_day_date")
		units = 0.5 if (cint(detail.get("half_day")) and half_day_date == str(day)) else 1.0
		out[f"{bucket}_leave_days"] = flt(out[f"{bucket}_leave_days"]) + units
		leave_type = detail.get("leave_type") or "Leave"
		types = out[f"{bucket}_leave_types"]
		types[leave_type] = flt(types.get(leave_type)) + units
	return out


def summarize_period(employee, from_date, to_date, company=None):
	"""Finalized Monthly Attendance Sheet BS row for ONE employee over one window.

	Roughly 15 queries, flat in the number of days -- but that is *per employee*.
	Never call this in a loop; a multi-employee caller should call the report's
	get_data() once with a company or department filter instead.

	Applies no permission check of its own. get_attendance_and_leaves lets an
	explicit employee filter override its role scoping, so the caller must have
	already established that this user may read this employee's attendance.
	"""
	from nepal_hrms.nepal_hrms.report.monthly_attendance_sheet_bs.monthly_attendance_sheet_bs import (
		get_attendance_and_leaves,
		get_data,
	)

	start = getdate(from_date)
	end = getdate(to_date)
	company = company or frappe.db.get_value("Employee", employee, "company")
	if not company:
		return {"found": False, "employee": employee, "totals": _empty_totals()}

	# show_details=0 skips the per-day in/out/working-hour columns we throw away.
	filters = frappe._dict({"company": company, "employee": employee, "show_details": 0})
	att_data, leave_types = get_attendance_and_leaves(filters, start, end)
	if not (att_data.get("employees") or []):
		# Relieved or inactive: an honest empty summary beats an error toast.
		return {"found": False, "employee": employee, "totals": _empty_totals()}

	rows = get_data(filters, start, end, att_data, leave_types)
	if not rows:
		return {"found": False, "employee": employee, "totals": _empty_totals()}

	row = rows[0]
	current_date = getdate(today())
	audit_through = row.get("audit_through_date")
	upcoming = _upcoming_leave(att_data.get("leave_day_map"), employee, current_date)
	upcoming_start = add_days(getdate(audit_through), 1) if audit_through else start
	# A fully-audited past window has nothing upcoming; do not print a backwards range.
	upcoming["from_date"] = str(min(getdate(upcoming_start), end))
	upcoming["to_date"] = str(end)
	upcoming["days_remaining"] = max((end - getdate(upcoming_start)).days + 1, 0)

	summary = str(row.get("summary") or "0:00 / 0:00")
	parts = [p.strip() for p in summary.split("/")]

	return {
		"found": True,
		"employee": employee,
		"employee_name": row.get("employee_name"),
		"period": {
			"from_date": str(start),
			"to_date": str(end),
			"days": cint(row.get("selected_period_days")),
			"audit_through_date": row.get("audit_through_date"),
			"future_days_excluded": cint(row.get("future_days_excluded")),
			"unmarked_today_excluded": cint(row.get("unmarked_today_excluded")),
		},
		"totals": {field: row.get(field, 0) for field in TOTAL_FIELDS},
		"upcoming": upcoming,
		"hours": {
			"summary": summary,
			"worked_label": parts[0] if parts else "0:00",
			"target_label": parts[1] if len(parts) > 1 else "0:00",
		},
		"breakdowns": {
			key: (row.get(field) or {}) for key, field in BREAKDOWN_FIELDS.items()
		},
		"day_dates": {field: (row.get(field) or []) for field in DAY_COUNT_DATE_FIELDS},
		"late_early": {
			**{field: row.get(field, 0) for field in LATE_EARLY_FIELDS},
			"cnr_counts": row.get("cnr_counts") or {},
			"occurrence_audit": row.get("occurrence_audit") or {},
		},
	}
