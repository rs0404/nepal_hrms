# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Bulk C&R Attendance recalculation: preview (dry-run) then apply with comments."""

import frappe
from frappe import _
from frappe.utils import add_months, cint, escape_html, get_datetime, getdate, today

from nepal_hrms.custom_code.attendance_holiday import (
	apply_holiday_sandwich_status,
	clear_cnr_flags,
	skip_late_early_for_status,
)
from nepal_hrms.custom_code.attendance_policy import (
	_cnr_snapshot,
	add_cnr_attendance_comment,
	apply_late_early_to_attendance,
	count_month_pool,
)


BULK_TRACKED_FIELDS = (
	"status",
	"half_day_status",
	"leave_type",
	"late_entry",
	"early_exit",
	"custom_late_mins",
	"custom_early_mins",
	"custom_cnr_unexcused_late",
	"custom_cnr_unexcused_early",
	"custom_cnr_late_in_pool",
	"custom_cnr_early_in_pool",
	"custom_cnr_month_late_pool_count",
	"custom_cnr_month_early_pool_count",
)

_TEXT_FIELDS = ("status", "half_day_status", "leave_type")


def _bulk_snapshot(doc):
	"""Richer snapshot for bulk preview (includes mins, late flags, month counts)."""
	snap = _cnr_snapshot(doc)
	snap.leave_type = getattr(doc, "leave_type", None) or None
	snap.late_entry = cint(getattr(doc, "late_entry", 0))
	snap.early_exit = cint(getattr(doc, "early_exit", 0))
	snap.custom_cnr_month_late_pool_count = cint(
		getattr(doc, "custom_cnr_month_late_pool_count", 0)
	)
	snap.custom_cnr_month_early_pool_count = cint(
		getattr(doc, "custom_cnr_month_early_pool_count", 0)
	)
	return snap


def _bulk_changed(before, after):
	if not before or not after:
		return False
	for field in BULK_TRACKED_FIELDS:
		bv = before.get(field)
		av = after.get(field)
		if field in _TEXT_FIELDS:
			if (bv or None) != (av or None):
				return True
		elif cint(bv) != cint(av):
			return True
	return False


def _snapshot_dict(snap):
	return {f: snap.get(f) for f in BULK_TRACKED_FIELDS}


def _format_field_diff(field, before_val, after_val):
	labels = {
		"status": _("Status"),
		"half_day_status": _("Half Day Status"),
		"leave_type": _("Leave Type"),
		"late_entry": _("Late Entry"),
		"early_exit": _("Early Exit"),
		"custom_late_mins": _("Late Mins"),
		"custom_early_mins": _("Early Mins"),
		"custom_cnr_unexcused_late": _("Unexcused Late"),
		"custom_cnr_unexcused_early": _("Unexcused Early"),
		"custom_cnr_late_in_pool": _("Late In Pool"),
		"custom_cnr_early_in_pool": _("Early In Pool"),
		"custom_cnr_month_late_pool_count": _("Month Late Pool"),
		"custom_cnr_month_early_pool_count": _("Month Early Pool"),
	}
	label = labels.get(field, field)
	return f"{label}: {before_val if before_val not in (None, '') else '—'} → {after_val if after_val not in (None, '') else '—'}"


def _change_items(before, after):
	"""Short UI-friendly change chips for preview/confirm."""
	items = []
	for field in BULK_TRACKED_FIELDS:
		bv = before.get(field)
		av = after.get(field)
		changed = False
		if field in _TEXT_FIELDS:
			changed = (bv or None) != (av or None)
			display_b, display_a = bv or "—", av or "—"
		else:
			changed = cint(bv) != cint(av)
			display_b, display_a = cint(bv), cint(av)
		if not changed:
			continue
		# Friendlier wording for common flags
		if field == "custom_cnr_late_in_pool":
			items.append(_("Late pool: {0} → {1}").format(display_b, display_a))
		elif field == "custom_cnr_early_in_pool":
			items.append(_("Early pool: {0} → {1}").format(display_b, display_a))
		elif field == "custom_cnr_unexcused_late":
			items.append(_("Unexcused late: {0} → {1}").format(display_b, display_a))
		elif field == "custom_cnr_unexcused_early":
			items.append(_("Unexcused early: {0} → {1}").format(display_b, display_a))
		elif field == "custom_cnr_month_late_pool_count":
			items.append(_("Month late pool: {0} → {1}").format(display_b, display_a))
		elif field == "custom_cnr_month_early_pool_count":
			items.append(_("Month early pool: {0} → {1}").format(display_b, display_a))
		elif field == "status":
			items.append(_("Status: {0} → {1}").format(display_b, display_a))
		elif field == "half_day_status":
			items.append(_("Half-day status: {0} → {1}").format(display_b, display_a))
		elif field == "leave_type":
			items.append(_("Leave Type: {0} → {1}").format(display_b, display_a))
		else:
			items.append(_format_field_diff(field, display_b, display_a))
	return items


def _is_stale_period(from_date):
	"""True when period start is older than 2 months from today."""
	return getdate(from_date) < add_months(getdate(today()), -2)

def _bs_label(ad_date):
	"""Nepali date string for display (always, independent of settings toggle)."""
	from nepal_compliance.nepali_date_utils.nepali_date import (
		NEPALI_MONTHS,
		ad_to_bs,
		format_bs,
	)

	try:
		bs = ad_to_bs(getdate(ad_date))
		iso = format_bs(ad_date, "YYYY-MM-DD")
		month_name = NEPALI_MONTHS[bs["month"]]
		return {
			"bs": iso,
			"bs_pretty": f"{bs['day']} {month_name} {bs['year']}",
			"ad": str(getdate(ad_date)),
		}
	except Exception:
		ad = str(getdate(ad_date))
		return {"bs": ad, "bs_pretty": ad, "ad": ad}


def _diff_summary(attendance_date, before, after):
	items = _change_items(before, after)
	bs = _bs_label(attendance_date)
	date_str = bs["bs_pretty"]
	if not items:
		return f"{date_str}: {_('no field changes')}"
	return f"{date_str}: " + "; ".join(items)


def _validate_dates(from_date, to_date):
	if not from_date or not to_date:
		frappe.throw(_("From Date and To Date are required"))
	from_date = getdate(from_date)
	to_date = getdate(to_date)
	if to_date < from_date:
		frappe.throw(_("To Date cannot be before From Date"))
	if (to_date - from_date).days > 92:
		frappe.throw(_("Period cannot exceed 92 days"))
	frappe.has_permission("Attendance", "write", throw=True)
	return from_date, to_date


def _parse_employees_arg(employees=None, employee=None):
	"""Normalize employees from JSON list, CSV string, or legacy single employee."""
	names = []
	if employees:
		if isinstance(employees, str):
			try:
				parsed = frappe.parse_json(employees)
			except Exception:
				parsed = [p.strip() for p in employees.split(",") if p.strip()]
			if isinstance(parsed, str):
				names = [parsed]
			elif isinstance(parsed, list):
				names = [str(x).strip() for x in parsed if str(x).strip()]
		elif isinstance(employees, (list, tuple)):
			names = [str(x).strip() for x in employees if str(x).strip()]
	elif employee:
		names = [employee]
	return names


def _resolve_employees(selection_mode=None, employees=None, employee=None, department=None):
	"""
	selection_mode:
	  - employees (default): explicit list / legacy single employee
	  - department: all Active employees in department
	  - all_active: all Active employees
	"""
	mode = (selection_mode or "employees").strip().lower()
	frappe.has_permission("Attendance", "write", throw=True)

	if mode == "all_active":
		names = frappe.get_all(
			"Employee", filters={"status": "Active"}, pluck="name", order_by="employee_name"
		)
	elif mode == "department":
		if not department:
			frappe.throw(_("Department is required"))
		names = frappe.get_all(
			"Employee",
			filters={"status": "Active", "department": department},
			pluck="name",
			order_by="employee_name",
		)
		if not names:
			frappe.throw(_("No active employees found in department {0}").format(department))
	else:
		names = _parse_employees_arg(employees=employees, employee=employee)
		if not names:
			frappe.throw(_("Select at least one employee"))

	# De-dupe preserving order
	seen = set()
	unique = []
	for n in names:
		if n not in seen:
			seen.add(n)
			unique.append(n)
	names = unique

	if len(names) > 200:
		frappe.throw(
			_("Too many employees ({0}). Please select at most 200 at a time.").format(len(names))
		)

	missing = [n for n in names if not frappe.db.exists("Employee", n)]
	if missing:
		frappe.throw(_("Employee not found: {0}").format(", ".join(missing[:5])))

	return names


def _employee_label(employee):
	return frappe.db.get_value("Employee", employee, "employee_name") or employee


def _format_punch_time(dt):
	if not dt:
		return "—"
	try:
		return get_datetime(dt).strftime("%H:%M")
	except Exception:
		return str(dt)


def _checkins_for_attendance(employee, attendance_date, attendance_name=None):
	"""All Employee Checkin punches for the day (same-day + linked), ordered by time."""
	if not employee or not attendance_date:
		return []

	day = getdate(attendance_date)
	start = get_datetime(f"{day} 00:00:00")
	end = get_datetime(f"{day} 23:59:59.999999")

	by_name = {}

	day_rows = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"time": ["between", [start, end]],
		},
		fields=["name", "time", "log_type"],
		order_by="time asc",
	)
	for row in day_rows:
		by_name[row.name] = row

	if attendance_name:
		linked = frappe.get_all(
			"Employee Checkin",
			filters={"attendance": attendance_name},
			fields=["name", "time", "log_type"],
			order_by="time asc",
		)
		for row in linked:
			by_name[row.name] = row

	ordered = sorted(
		by_name.values(),
		key=lambda r: get_datetime(r.time) if r.time else get_datetime("1900-01-01"),
	)
	return [
		{
			"name": r.name,
			"log_type": (r.log_type or "").upper() or "—",
			"time": str(r.time) if r.time else None,
			"time_display": _format_punch_time(r.time),
		}
		for r in ordered
	]


def _applications_for_attendance(employee, attendance_date, attendance_name=None):
	"""Late Entry / Early Exit / OOO apps for the day (any status), for preview display."""
	if not employee or not attendance_date:
		return []

	day = getdate(attendance_date)
	specs = (
		("Late Entry Application", "LEA", ["name", "status", "type_of_work", "docstatus", "attendance"]),
		("Early Exit Application", "EEA", ["name", "status", "type_of_work", "docstatus", "attendance"]),
		("Out of Office Application", "OOO", ["name", "status", "type_of_work", "docstatus", "attendance", "total_hours"]),
	)
	rows = []
	for doctype, short, fields in specs:
		if not frappe.db.exists("DocType", doctype):
			continue
		found = {}
		day_rows = frappe.get_all(
			doctype,
			filters={
				"employee": employee,
				"attendance_date": day,
				"docstatus": ["<", 2],
			},
			fields=fields,
			order_by="modified desc",
		)
		for r in day_rows:
			found[r.name] = r
		if attendance_name:
			linked = frappe.get_all(
				doctype,
				filters={"attendance": attendance_name, "docstatus": ["<", 2]},
				fields=fields,
				order_by="modified desc",
			)
			for r in linked:
				found[r.name] = r
		for r in found.values():
			status = (r.status or "Draft").strip() or "Draft"
			# Treat Cancelled docstatus separately if any slip through
			if cint(r.docstatus) == 2:
				status = "Cancelled"
			entry = {
				"doctype": doctype,
				"short": short,
				"name": r.name,
				"status": status,
				"type_of_work": getattr(r, "type_of_work", None) or "",
				"docstatus": cint(r.docstatus),
			}
			if short == "OOO" and hasattr(r, "total_hours"):
				entry["total_hours"] = r.total_hours
			rows.append(entry)

	# LEA, EEA, then OOO; Approved first within type
	order = {"LEA": 0, "EEA": 1, "OOO": 2}
	status_rank = {"Approved": 0, "Draft": 1, "Rejected": 2, "Cancelled": 3}
	rows.sort(
		key=lambda r: (
			order.get(r["short"], 9),
			status_rank.get(r["status"], 9),
			r["name"],
		)
	)
	return rows


def _change_row(item, employee=None, employee_name=None):
	bs = _bs_label(item["attendance_date"])
	before, after = item["before"], item["after"]
	in_time = item.get("in_time")
	out_time = item.get("out_time")
	if in_time is None and out_time is None and item.get("name"):
		times = frappe.db.get_value(
			"Attendance", item["name"], ["in_time", "out_time"], as_dict=True
		) or {}
		in_time = times.get("in_time")
		out_time = times.get("out_time")

	checkins = item.get("checkins")
	if checkins is None:
		checkins = _checkins_for_attendance(
			employee, item["attendance_date"], attendance_name=item.get("name")
		)

	applications = item.get("applications")
	if applications is None:
		applications = _applications_for_attendance(
			employee, item["attendance_date"], attendance_name=item.get("name")
		)

	return {
		"name": item["name"],
		"employee": employee,
		"employee_name": employee_name,
		"attendance_date": str(item["attendance_date"]),
		"attendance_date_bs": bs["bs"],
		"attendance_date_bs_pretty": bs["bs_pretty"],
		"in_time": str(in_time) if in_time else None,
		"out_time": str(out_time) if out_time else None,
		"in_time_display": _format_punch_time(in_time),
		"out_time_display": _format_punch_time(out_time),
		"checkins": checkins,
		"applications": applications,
		"reason": item.get("reason"),
		"before": _snapshot_dict(before),
		"after": _snapshot_dict(after),
		"changes": _change_items(before, after),
		"summary": _diff_summary(item["attendance_date"], before, after),
	}


def _list_attendance_names(employee, from_date, to_date):
	return frappe.get_all(
		"Attendance",
		filters={
			"employee": employee,
			"attendance_date": ["between", [from_date, to_date]],
			"docstatus": ["<", 2],
		},
		fields=["name", "attendance_date", "status", "leave_type", "docstatus"],
		order_by="attendance_date asc",
	)


def _pool_period_key(attendance_date):
	from nepal_hrms.custom_code.attendance_policy import _pool_period_bounds, get_hr_settings

	settings = get_hr_settings()
	return _pool_period_bounds(attendance_date, settings=settings)


def _outside_batch_month_pool(employee, attendance_date, pool_field, batch_names):
	"""DB pool count for the payroll period, excluding every Attendance in this batch."""
	from nepal_hrms.custom_code.attendance_policy import _pool_period_bounds, get_hr_settings

	if not frappe.get_meta("Attendance").has_field(pool_field):
		return 0
	settings = get_hr_settings()
	start, end = _pool_period_bounds(attendance_date, settings=settings)
	filters = {
		"employee": employee,
		"attendance_date": ["between", [start, end]],
		"docstatus": ["<", 2],
		pool_field: 1,
	}
	if batch_names:
		filters["name"] = ["not in", list(batch_names)]
	return cint(frappe.db.count("Attendance", filters))


def _simulated_month_pool_count(
	employee, attendance_date, pool_field, batch_names, simulated_flags, as_of_date
):
	"""
	Payroll-period pool as it would look after applying the batch in date order.
	= outside-batch DB pool days in the period
	  + simulated in-pool batch days in the same period with date <= as_of_date
	"""
	outside = _outside_batch_month_pool(employee, attendance_date, pool_field, batch_names)
	period = _pool_period_key(attendance_date)
	as_of = getdate(as_of_date)
	flag_key = "late" if pool_field.endswith("late_in_pool") else "early"
	sim = 0
	for _name, info in simulated_flags.items():
		if _pool_period_key(info["attendance_date"]) != period:
			continue
		if getdate(info["attendance_date"]) > as_of:
			continue
		if cint(info.get(flag_key)):
			sim += 1
	return outside + sim


def _refresh_month_pool_counts(doc):
	"""Set month pool counters after flags were cleared without running late/early."""
	att_name = getattr(doc, "name", None)
	exclude = att_name if att_name and not str(att_name).startswith("new-") else None
	if hasattr(doc, "custom_cnr_month_late_pool_count"):
		doc.custom_cnr_month_late_pool_count = count_month_pool(
			doc.employee,
			doc.attendance_date,
			"custom_cnr_late_in_pool",
			current_in_pool=0,
			exclude_name=exclude,
		)
	if hasattr(doc, "custom_cnr_month_early_pool_count"):
		doc.custom_cnr_month_early_pool_count = count_month_pool(
			doc.employee,
			doc.attendance_date,
			"custom_cnr_early_in_pool",
			current_in_pool=0,
			exclude_name=exclude,
		)


def _dry_run_one(name):
	"""
	Apply holiday/sandwich status then C&R in memory.
	Returns (doc, before, after, protected, reason).
	protected=True only when pre-existing leave/absent/WFH was left untouched.
	"""
	doc = frappe.get_doc("Attendance", name)
	before = _bulk_snapshot(doc)
	prior_status = (doc.status or "").strip()
	prior_leave = getattr(doc, "leave_type", None)

	reason = apply_holiday_sandwich_status(doc)

	# A half-day leave row is still protected from C&R, but its worked half is
	# recalculated here -- this is how rows the old check-in sync swept to
	# Absent get repaired, a month at a time, from the Recalculate dialog.
	if reason is None and prior_status == "Half Day" and prior_leave:
		from nepal_hrms.custom_code.half_day import compute_half_day_other_half

		plan = compute_half_day_other_half(doc)
		settled = (plan.writes or {}).get("half_day_status") if plan else None
		if settled and settled != (doc.half_day_status or None):
			doc.half_day_status = settled
			doc.flags.nepal_half_day_values = plan.writes
			return doc, before, _bulk_snapshot(doc), False, "half_day_leave"
		return doc, before, before, True, None

	# Pre-existing protected rows with no holiday/sandwich/working conversion
	if reason is None and (
		prior_status in ("On Leave", "Absent", "Work From Home") or prior_leave
	):
		return doc, before, before, True, None

	if skip_late_early_for_status(doc):
		# Holiday / sandwich / working-day Absent — ensure C&R cleared + month counts
		if reason in (
			"holiday",
			"weekly_off",
			"sandwich_leave",
			"sandwich_absent",
			"leave_on_holiday",
			"working_day_absent",
		):
			clear_cnr_flags(doc)
			_refresh_month_pool_counts(doc)
		after = _bulk_snapshot(doc)
		return doc, before, after, False, reason

	apply_late_early_to_attendance(doc, apply_unexcused_status=True)
	after = _bulk_snapshot(doc)
	return doc, before, after, False, reason or "cnr"


def _persist_recalc_doc(doc):
	"""Write status / leave_type / C&R fields from an in-memory Attendance doc."""
	meta = frappe.get_meta("Attendance")
	values = {
		"status": doc.status,
		"late_entry": cint(getattr(doc, "late_entry", 0)),
		"early_exit": cint(getattr(doc, "early_exit", 0)),
	}
	if meta.has_field("leave_type"):
		values["leave_type"] = getattr(doc, "leave_type", None) or None
	if meta.has_field("half_day_status"):
		values["half_day_status"] = getattr(doc, "half_day_status", None) or None
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
	# A settled half-day leave also clears the stock "not yet checked" flag and
	# records which half was leave; without the flag the next sweep would undo it.
	half_day_values = doc.flags.get("nepal_half_day_values") or {}
	for field in ("modify_half_day_status", "custom_half_day_session", "working_hours", "in_time", "out_time"):
		if field in half_day_values and meta.has_field(field):
			values[field] = half_day_values[field]
	frappe.db.set_value("Attendance", doc.name, values, update_modified=False)


def _run_batch_dry_runs(employee, rows):
	"""
	Dry-run all rows in date order and fix month pool counts using simulated batch state
	so preview/apply summaries accumulate correctly (Jul 20 → 1, Jul 21 → 2, …).
	Returns list of dicts: name, attendance_date, before, after, protected, reason, doc
	"""
	batch_names = [r.name for r in rows]
	simulated = {}
	results = []

	for row in rows:
		_doc, before, after, protected, reason = _dry_run_one(row.name)
		att_date = getdate(row.attendance_date)
		in_time = getattr(_doc, "in_time", None)
		out_time = getattr(_doc, "out_time", None)

		if protected:
			simulated[row.name] = {
				"attendance_date": att_date,
				"late": cint(before.custom_cnr_late_in_pool),
				"early": cint(before.custom_cnr_early_in_pool),
			}
			results.append(
				{
					"name": row.name,
					"attendance_date": att_date,
					"before": before,
					"after": after,
					"protected": True,
					"reason": reason,
					"doc": _doc,
					"in_time": in_time,
					"out_time": out_time,
				}
			)
			continue

		# Record simulated pool flags for this day, then overwrite month counts
		simulated[row.name] = {
			"attendance_date": att_date,
			"late": cint(after.custom_cnr_late_in_pool),
			"early": cint(after.custom_cnr_early_in_pool),
		}
		after.custom_cnr_month_late_pool_count = _simulated_month_pool_count(
			employee,
			att_date,
			"custom_cnr_late_in_pool",
			batch_names,
			simulated,
			att_date,
		)
		after.custom_cnr_month_early_pool_count = _simulated_month_pool_count(
			employee,
			att_date,
			"custom_cnr_early_in_pool",
			batch_names,
			simulated,
			att_date,
		)
		# Keep in-memory doc month counts in sync for persist
		if hasattr(_doc, "custom_cnr_month_late_pool_count"):
			_doc.custom_cnr_month_late_pool_count = after.custom_cnr_month_late_pool_count
		if hasattr(_doc, "custom_cnr_month_early_pool_count"):
			_doc.custom_cnr_month_early_pool_count = after.custom_cnr_month_early_pool_count

		results.append(
			{
				"name": row.name,
				"attendance_date": att_date,
				"before": before,
				"after": after,
				"protected": False,
				"reason": reason,
				"doc": _doc,
				"in_time": in_time,
				"out_time": out_time,
			}
		)

	return results


@frappe.whitelist()
def preview_recalculate_attendance_period(
	employee=None,
	from_date=None,
	to_date=None,
	employees=None,
	selection_mode=None,
	department=None,
):
	"""Dry-run C&R recompute for one or more employees; return detailed diffs with BS dates."""
	from_date, to_date = _validate_dates(from_date, to_date)
	emp_list = _resolve_employees(selection_mode, employees, employee, department)

	all_changes = []
	unchanged_count = 0
	skipped_protected_count = 0
	total_rows = 0
	by_employee = []

	for emp in emp_list:
		rows = _list_attendance_names(emp, from_date, to_date)
		total_rows += len(rows)
		results = _run_batch_dry_runs(emp, rows)
		emp_name = _employee_label(emp)
		emp_changes = []
		emp_unchanged = 0
		emp_skipped = 0

		for item in results:
			if item["protected"]:
				skipped_protected_count += 1
				emp_skipped += 1
				continue
			before, after = item["before"], item["after"]
			if not _bulk_changed(before, after):
				unchanged_count += 1
				emp_unchanged += 1
				continue
			row = _change_row(item, employee=emp, employee_name=emp_name)
			emp_changes.append(row)
			all_changes.append(row)

		by_employee.append(
			{
				"employee": emp,
				"employee_name": emp_name,
				"change_count": len(emp_changes),
				"unchanged_count": emp_unchanged,
				"skipped_protected_count": emp_skipped,
				"changes": emp_changes,
			}
		)

	from_bs = _bs_label(from_date)
	to_bs = _bs_label(to_date)
	return {
		"employees": [
			{"employee": e, "employee_name": _employee_label(e)} for e in emp_list
		],
		"employee_count": len(emp_list),
		"employee": emp_list[0] if len(emp_list) == 1 else None,
		"employee_name": _employee_label(emp_list[0]) if len(emp_list) == 1 else None,
		"from_date": str(from_date),
		"to_date": str(to_date),
		"from_date_bs": from_bs["bs"],
		"to_date_bs": to_bs["bs"],
		"from_date_bs_pretty": from_bs["bs_pretty"],
		"to_date_bs_pretty": to_bs["bs_pretty"],
		"stale_period": _is_stale_period(from_date),
		"total": total_rows,
		"change_count": len(all_changes),
		"unchanged_count": unchanged_count,
		"skipped_protected_count": skipped_protected_count,
		"changes": all_changes,
		"by_employee": by_employee,
	}


@frappe.whitelist()
def apply_recalculate_attendance_period(
	employee=None,
	from_date=None,
	to_date=None,
	employees=None,
	selection_mode=None,
	department=None,
):
	"""Apply C&R recompute for period; comment diffs + bulk attribution on changed rows."""
	from_date, to_date = _validate_dates(from_date, to_date)
	emp_list = _resolve_employees(selection_mode, employees, employee, department)

	updated = []
	unchanged = 0
	skipped = 0
	user = frappe.session.user
	from_bs = _bs_label(from_date)
	to_bs = _bs_label(to_date)
	period_label = f"{from_bs['bs_pretty']} – {to_bs['bs_pretty']}"

	for emp in emp_list:
		rows = _list_attendance_names(emp, from_date, to_date)
		results = _run_batch_dry_runs(emp, rows)
		emp_name = _employee_label(emp)

		for item in results:
			if item["protected"]:
				skipped += 1
				continue
			before, after = item["before"], item["after"]
			if not _bulk_changed(before, after):
				unchanged += 1
				continue

			# Persist holiday/sandwich + C&R from the same dry-run doc (not late/early-only)
			_persist_recalc_doc(item["doc"])
			change_lines = _change_items(before, after)
			if change_lines:
				changes_html = "<br>".join(escape_html(line) for line in change_lines)
			else:
				changes_html = escape_html(_("fields updated"))
			reason = item.get("reason")
			reason_note = ""
			if reason:
				reason_note = "<br>" + escape_html(_("Reason: {0}").format(reason))
			comment_msg = _(
				"<b>Recalculate C&R for Period</b> by {0}<br>"
				"Period: {1}{2}<br>"
				"Changes:<br>{3}"
			).format(
				escape_html(user),
				escape_html(period_label),
				reason_note,
				changes_html,
			)
			add_cnr_attendance_comment(item["name"], comment_msg)
			updated.append(_change_row(item, employee=emp, employee_name=emp_name))

	return {
		"ok": 1,
		"employee_count": len(emp_list),
		"from_date": str(from_date),
		"to_date": str(to_date),
		"from_date_bs_pretty": from_bs["bs_pretty"],
		"to_date_bs_pretty": to_bs["bs_pretty"],
		"updated": len(updated),
		"unchanged": unchanged,
		"skipped": skipped,
		"changes": updated,
	}


@frappe.whitelist()
def get_bs_date_presets():
	"""Today + current Nepali month first/last day (AD values for Date fields + BS labels)."""
	from frappe.utils import today
	import nepal_compliance.nepali_date_utils.nepali_date as nepali_date

	nepali_date._ensure_loaded()
	today_ad = getdate(today())
	bs = nepali_date.ad_to_bs(today_ad)
	y, m = bs["year"], bs["month"]
	days = nepali_date._bs_months[y][m - 1]
	month_start_ad = nepali_date.bs_to_ad(y, m, 1)
	month_end_ad = nepali_date.bs_to_ad(y, m, days)
	today_lbl = _bs_label(today_ad)
	start_lbl = _bs_label(month_start_ad)
	end_lbl = _bs_label(month_end_ad)
	month_name = nepali_date.NEPALI_MONTHS[m]
	return {
		"today": {
			"ad": str(today_ad),
			"bs": today_lbl["bs"],
			"bs_pretty": today_lbl["bs_pretty"],
		},
		"bs_month": {
			"year": y,
			"month": m,
			"month_name": month_name,
			"from_date": str(month_start_ad),
			"to_date": str(month_end_ad),
			"from_date_bs": start_lbl["bs"],
			"to_date_bs": end_lbl["bs"],
			"from_date_bs_pretty": start_lbl["bs_pretty"],
			"to_date_bs_pretty": end_lbl["bs_pretty"],
			"label": f"{month_name} {y}",
		},
	}


@frappe.whitelist()
def resolve_monthly_sheet_bs_period(filters=None):
	"""Resolve AD from/to dates from Monthly Attendance Sheet BS filters for the bulk dialog."""
	import nepal_compliance.nepali_date_utils.nepali_date as nepali_date
	from nepal_hrms.nepal_hrms.report.monthly_attendance_sheet_bs.monthly_attendance_sheet_bs import (
		get_bs_date_with_offset,
	)

	if isinstance(filters, str):
		filters = frappe.parse_json(filters) or {}
	filters = frappe._dict(filters or {})
	nepali_date._ensure_loaded()

	if filters.get("filter_based_on") == "BS Date Range":
		from_bs = filters.get("from_bs_date")
		to_bs = filters.get("to_bs_date")
		if not from_bs or not to_bs:
			frappe.throw(_("Please provide both From and To BS Dates"))
		f_y, f_m, f_d = map(int, str(from_bs).split("-"))
		t_y, t_m, t_d = map(int, str(to_bs).split("-"))
		start_ad = nepali_date.bs_to_ad(f_y, f_m, f_d)
		end_ad = nepali_date.bs_to_ad(t_y, t_m, t_d)
	else:
		bs_year = int(filters.get("bs_year") or 2081)
		bs_month = int(filters.get("bs_month") or 1)
		if bs_year not in nepali_date._bs_months:
			frappe.throw(_("Selected BS Year {0} is out of bounds.").format(bs_year))
		if filters.get("use_custom_period"):
			s_day = int(filters.get("custom_start_day") or 1)
			s_type = filters.get("start_month_type")
			e_day = int(filters.get("custom_end_day") or 30)
			e_type = filters.get("end_month_type")
			s_offset = -1 if s_type == "Previous Month" else 0
			e_offset = 1 if e_type == "Next Month" else 0
			start_ad = get_bs_date_with_offset(bs_year, bs_month, s_day, s_offset)
			end_ad = get_bs_date_with_offset(bs_year, bs_month, e_day, e_offset)
		else:
			days_in_month = nepali_date._bs_months[bs_year][bs_month - 1]
			start_ad = nepali_date.bs_to_ad(bs_year, bs_month, 1)
			end_ad = nepali_date.bs_to_ad(bs_year, bs_month, days_in_month)

	emp = filters.get("employee") or ""
	return {
		"from_date": str(getdate(start_ad)),
		"to_date": str(getdate(end_ad)),
		"employee": emp,
		"employees": [emp] if emp else [],
	}
