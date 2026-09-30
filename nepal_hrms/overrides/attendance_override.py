"""
Override for mark_attendance_and_link_log from HRMS.
When unapproved OOO Work check-ins are present:
  - Attendance is Draft (or held) with custom_ooo_hold=1
  - Working hours exclude unapproved OOO until Leave Approver approves
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate, time_diff_in_hours

from hrms.hr.doctype.employee_checkin.employee_checkin import (
	mark_attendance_and_link_log as original_mark_attendance_and_link_log,
	skip_attendance_in_checkins,
	update_attendance_in_checkins,
	handle_attendance_exception,
	get_existing_half_day_attendance,
	calculate_working_hours,
)
from nepal_hrms.custom_code.attendance_policy import (
	apply_late_early_to_attendance,
	calculate_ooo_hours_from_checkins,
	compute_late_early_minutes,
	get_approved_application,
	get_attendance_for_employee_date,
	get_hr_settings,
)


def custom_mark_attendance_and_link_log(
	logs,
	attendance_status,
	attendance_date,
	working_hours=None,
	late_entry=False,
	early_exit=False,
	in_time=None,
	out_time=None,
	shift=None,
):
	"""
	If any logs are unapproved OOO Work, create/update Attendance on hold and
	exclude those OOO hours until Leave Approver approval.
	"""
	log_names = [x.name for x in logs]
	employee = logs[0].employee

	if attendance_status == "Skip":
		skip_attendance_in_checkins(log_names)
		return None

	existing_name = frappe.db.exists(
		"Attendance",
		{
			"employee": employee,
			"attendance_date": getdate(attendance_date),
			"docstatus": ["<", 2],
		},
	)
	if existing_name:
		existing_status = frappe.db.get_value("Attendance", existing_name, "status")
		if existing_status == "On Leave":
			skip_attendance_in_checkins(log_names)
			return None
		synced = sync_attendance_hours_from_checkins(employee, attendance_date)
		update_attendance_in_checkins(log_names, existing_name)
		return synced or frappe.get_doc("Attendance", existing_name)

	has_unapproved_ooo = _check_unapproved_ooo_logs(log_names)

	if has_unapproved_ooo and attendance_status in ("Present", "Absent", "Half Day"):
		# Hours / status based on Normal + approved OOO only
		counted_hours, counted_in, counted_out = _hours_excluding_unapproved_ooo(
			logs, shift
		)
		late_entry, early_exit = _apply_cnr_grace(
			employee,
			attendance_date,
			counted_in,
			counted_out,
			shift,
			late_entry,
			early_exit,
		)
		status_for_hold = _status_from_hours(counted_hours, shift) or attendance_status
		return _create_ooo_hold_attendance(
			logs,
			log_names,
			employee,
			status_for_hold,
			attendance_date,
			counted_hours,
			late_entry,
			early_exit,
			counted_in,
			counted_out,
			shift,
		)

	# Align late/early flags with Nepal Compliance grace before creating attendance
	late_entry, early_exit = _apply_cnr_grace(
		employee, attendance_date, in_time, out_time, shift, late_entry, early_exit
	)

	return original_mark_attendance_and_link_log(
		logs,
		attendance_status,
		attendance_date,
		working_hours,
		late_entry,
		early_exit,
		in_time,
		out_time,
		shift,
	)


def _apply_cnr_grace(employee, attendance_date, in_time, out_time, shift, late_entry, early_exit):
	settings = get_hr_settings()
	grace = cint(getattr(settings, "late_early_grace_mins", None) or 15)
	late_mins, early_mins = compute_late_early_minutes(
		employee, attendance_date, in_time=in_time, out_time=out_time, shift=shift
	)
	return (1 if late_mins > grace else 0), (1 if early_mins > grace else 0)


def _check_unapproved_ooo_logs(log_names):
	if not log_names:
		return False
	return bool(
		frappe.db.count(
			"Employee Checkin",
			filters={
				"name": ["in", list(log_names)],
				"custom_attendance_type": "OOO Work",
				"custom_is_approved": 0,
			},
		)
	)


def _enrich_logs(logs):
	"""Ensure logs have custom_attendance_type / custom_is_approved from DB."""
	names = [getattr(l, "name", None) for l in logs if getattr(l, "name", None)]
	if not names:
		return list(logs)
	meta = {
		r.name: r
		for r in frappe.get_all(
			"Employee Checkin",
			filters={"name": ["in", names]},
			fields=[
				"name",
				"employee",
				"log_type",
				"time",
				"shift",
				"shift_start",
				"shift_end",
				"custom_attendance_type",
				"custom_is_approved",
			],
		)
	}
	enriched = []
	for log in logs:
		row = meta.get(getattr(log, "name", None))
		if not row:
			enriched.append(log)
			continue
		# Merge into a simple namespace/dict-like object for calculate_working_hours
		enriched.append(frappe._dict(row))
	return enriched


def _log_counts_for_hours(log):
	att_type = (getattr(log, "custom_attendance_type", None) or "Normal").strip()
	if att_type != "OOO Work":
		return True
	return cint(getattr(log, "custom_is_approved", 0)) == 1


def _hours_excluding_unapproved_ooo(logs, shift_name=None):
	"""Working hours / in / out using Normal + approved OOO only."""
	enriched = _enrich_logs(logs)
	counted = [l for l in enriched if _log_counts_for_hours(l)]
	if not counted:
		return 0.0, None, None

	check_in_out_type = "Alternating entries as IN and OUT during the same shift"
	working_hours_calc = "First Check-in and Last Check-out"
	if shift_name:
		cfg = frappe.db.get_value(
			"Shift Type",
			shift_name,
			["determine_check_in_and_check_out", "working_hours_calculation_based_on"],
			as_dict=True,
		)
		if cfg:
			check_in_out_type = (
				cfg.determine_check_in_and_check_out or check_in_out_type
			)
			working_hours_calc = (
				cfg.working_hours_calculation_based_on or working_hours_calc
			)

	total_hours, in_time, out_time = calculate_working_hours(
		counted, check_in_out_type, working_hours_calc
	)
	return flt(total_hours), in_time, out_time


def _status_from_hours(working_hours, shift_name=None, factor=1.0):
	"""Map hours to Present/Half Day/Absent using shift thresholds when available.

	factor scales both thresholds: 0.5 judges the worked half of a half-day leave
	day as a half-length day (see custom_code/half_day.py).
	"""
	hours = flt(working_hours)
	absent_th = half_th = 0
	if shift_name:
		absent_th, half_th = frappe.db.get_value(
			"Shift Type",
			shift_name,
			["working_hours_threshold_for_absent", "working_hours_threshold_for_half_day"],
		) or (0, 0)
		absent_th = flt(absent_th) * flt(factor)
		half_th = flt(half_th) * flt(factor)
	if absent_th and hours < absent_th:
		return "Absent"
	if half_th and hours < half_th:
		return "Half Day"
	if hours <= 0 and not absent_th:
		return "Absent"
	return "Present"


def _create_ooo_hold_attendance(
	logs,
	log_names,
	employee,
	attendance_status,
	attendance_date,
	working_hours,
	late_entry,
	early_exit,
	in_time,
	out_time,
	shift,
):
	"""
	Create/update Attendance with OOO hold. Do not include unapproved OOO in hours.
	Do not submit until Leave Approver approves.
	"""
	try:
		frappe.db.savepoint("ooo_attendance_creation")

		late_mins, early_mins = compute_late_early_minutes(
			employee, attendance_date, in_time=in_time, out_time=out_time, shift=shift
		)

		existing_half = get_existing_half_day_attendance(employee, attendance_date)
		if existing_half:
			frappe.db.set_value(
				"Attendance",
				existing_half.name,
				{
					"working_hours": working_hours,
					"shift": shift,
					"late_entry": late_entry,
					"early_exit": early_exit,
					"in_time": in_time,
					"out_time": out_time,
					"custom_ooo_hold": 1,
					"custom_has_ooo_logs": 1,
					"custom_late_mins": late_mins,
					"custom_early_mins": early_mins,
				},
			)
			update_attendance_in_checkins(log_names, existing_half.name)
			return existing_half

		existing_name = frappe.db.exists(
			"Attendance",
			{
				"employee": employee,
				"attendance_date": getdate(attendance_date),
				"docstatus": ["<", 2],
			},
		)

		if existing_name:
			# Keep current submitted/draft status; mark hold and do not add OOO hours yet
			values = {
				"custom_ooo_hold": 1,
				"custom_has_ooo_logs": 1,
			}
			# Only overwrite hours/status when still Draft (safe to recalculate without OOO)
			docstatus = frappe.db.get_value("Attendance", existing_name, "docstatus")
			if cint(docstatus) == 0:
				values.update(
					{
						"status": attendance_status,
						"working_hours": working_hours,
						"late_entry": late_entry,
						"early_exit": early_exit,
						"in_time": in_time,
						"out_time": out_time,
						"custom_late_mins": late_mins,
						"custom_early_mins": early_mins,
						"shift": shift,
					}
				)
			frappe.db.set_value("Attendance", existing_name, values)
			update_attendance_in_checkins(log_names, existing_name)
			return frappe.get_doc("Attendance", existing_name)

		# New Draft attendance on hold (not submitted)
		attendance = frappe.new_doc("Attendance")
		attendance.update(
			{
				"employee": employee,
				"attendance_date": attendance_date,
				"status": attendance_status,
				"working_hours": working_hours,
				"shift": shift,
				"late_entry": late_entry,
				"early_exit": early_exit,
				"in_time": in_time,
				"out_time": out_time,
				"custom_ooo_hold": 1,
				"custom_has_ooo_logs": 1,
				"custom_late_mins": late_mins,
				"custom_early_mins": early_mins,
			}
		)
		apply_late_early_to_attendance(attendance)
		attendance.insert()
		# Do NOT submit — Leave Approver must approve OOO first

		update_attendance_in_checkins(log_names, attendance.name)

		frappe.msgprint(
			_(
				"Attendance for {0} on {1} created as Draft (OOO Hold). "
				"Leave Approver must approve OOO check-ins before hours are counted."
			).format(employee, attendance_date),
			alert=True,
			indicator="orange",
		)
		return attendance

	except frappe.ValidationError as e:
		handle_attendance_exception(log_names, e)


def compute_hours_from_checkin_rows(rows, shift_name=None):
	"""Pair IN/OUT logs. Normal always counts; OOO counts only when approved and not rejected."""
	total_seconds = 0
	last_in_time = None
	first_in = None
	last_out = None
	has_normal = False
	has_ooo = False
	has_unapproved_ooo = False

	for row in rows or []:
		att_type = (getattr(row, "custom_attendance_type", None) or "Normal").strip()
		if att_type == "OOO Work":
			has_ooo = True
			if cint(getattr(row, "custom_ooo_rejected", 0)):
				continue
			if not cint(getattr(row, "custom_is_approved", 0)):
				has_unapproved_ooo = True
				continue
		else:
			has_normal = True

		if not shift_name and getattr(row, "shift", None):
			shift_name = row.shift

		log_type = (getattr(row, "log_type", None) or "").upper()
		when = getattr(row, "time", None)
		if not when:
			continue
		when = get_datetime(when)

		if log_type == "IN":
			last_in_time = when
			if first_in is None:
				first_in = when
		elif log_type == "OUT" and last_in_time:
			total_seconds += (when - last_in_time).total_seconds()
			last_out = when
			last_in_time = None

	total_hours = round(total_seconds / 3600.0, 2)
	status = _status_from_hours(total_hours, shift_name)
	if not has_normal and total_hours > 0:
		status = "Present"

	return frappe._dict(
		total_hours=total_hours,
		first_in=first_in,
		last_out=last_out,
		shift_name=shift_name,
		has_normal=has_normal,
		has_ooo=has_ooo,
		has_unapproved_ooo=has_unapproved_ooo,
		# An IN with no OUT after it. The hours are unknowable, not zero: someone who
		# punched in was here. Callers must not read the resulting status as absence.
		unpaired_in=last_in_time is not None,
		status=status,
	)


def compute_day_hours_from_checkins(employee, attendance_date):
	"""Load a day's check-ins and compute countable hours / in / out / status."""
	attendance_date = getdate(attendance_date)
	fields = [
		"name",
		"time",
		"log_type",
		"shift",
		"custom_attendance_type",
		"custom_is_approved",
	]
	meta = frappe.get_meta("Employee Checkin")
	if meta.has_field("custom_ooo_rejected"):
		fields.append("custom_ooo_rejected")

	rows = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"time": ["between", [f"{attendance_date} 00:00:00", f"{attendance_date} 23:59:59"]],
		},
		fields=fields,
		order_by="time asc",
	)
	computed = compute_hours_from_checkin_rows(rows)
	computed.ooo_hours = calculate_ooo_hours_from_checkins(
		employee, attendance_date, approved_only=True
	)
	computed.checkin_names = [row.name for row in rows]
	return computed


def _has_approved_attendance_request(attendance):
	"""True when this Attendance row was written by a submitted Attendance Request."""
	request = getattr(attendance, "attendance_request", None)
	if not request:
		return False
	return cint(frappe.db.get_value("Attendance Request", request, "docstatus")) == 1


def sync_attendance_hours_from_checkins(employee, attendance_date):
	"""
	Rewrite Attendance hours/status from all punches that day.

	Used when a late biometric IN arrives after OOO-only attendance was already marked.
	Does not override On Leave, nor a status an approved Attendance Request set.
	"""
	attendance_date = getdate(attendance_date)
	attendance_name = get_attendance_for_employee_date(employee, attendance_date)
	if not attendance_name:
		return None

	attendance = frappe.get_doc("Attendance", attendance_name)
	if (attendance.status or "").strip() == "On Leave":
		return attendance
	if attendance.leave_type:
		# A half-day leave row still owes a verdict on the half that was worked.
		# Returning here untouched is what left modify_half_day_status set, and the
		# stock sweep then marked people who had checked in Absent for that half.
		from nepal_hrms.custom_code.half_day import resolve_half_day_other_half

		resolve_half_day_other_half(attendance)
		return frappe.get_doc("Attendance", attendance_name)

	computed = compute_day_hours_from_checkins(employee, attendance_date)
	before_status = attendance.status
	before_hours = flt(attendance.working_hours)

	# Two cases where the computed status must not overwrite the stored one. An
	# approved Attendance Request is a manager's ruling on the day. An unpaired IN
	# means the punch record is incomplete, not that nobody came -- treating the
	# resulting 0 hours as absence marks present people absent and silently undoes
	# any correction. Hours and times still refresh in both cases.
	keep_status = _has_approved_attendance_request(attendance) or computed.unpaired_in
	status = attendance.status if keep_status else computed.status

	values = {
		"working_hours": computed.total_hours,
		"status": status,
		"in_time": computed.first_in,
		"out_time": computed.last_out,
		"late_entry": attendance.late_entry,
		"early_exit": attendance.early_exit,
	}
	if computed.shift_name:
		values["shift"] = computed.shift_name

	meta = frappe.get_meta("Attendance")
	if meta.has_field("custom_ooo_hours"):
		values["custom_ooo_hours"] = computed.ooo_hours
	if meta.has_field("custom_has_ooo_logs"):
		values["custom_has_ooo_logs"] = 1 if computed.has_ooo else 0
	if meta.has_field("custom_ooo_hold"):
		values["custom_ooo_hold"] = 1 if computed.has_unapproved_ooo else 0

	for key, val in values.items():
		setattr(attendance, key, val)
	apply_late_early_to_attendance(attendance)

	values["status"] = attendance.status
	values["late_entry"] = cint(attendance.late_entry)
	values["early_exit"] = cint(attendance.early_exit)
	for field in (
		"custom_late_mins",
		"custom_early_mins",
		"custom_cnr_unexcused_late",
		"custom_cnr_unexcused_early",
		"custom_cnr_late_in_pool",
		"custom_cnr_early_in_pool",
		"custom_cnr_month_late_pool_count",
		"custom_cnr_month_early_pool_count",
		"half_day_status",
	):
		if meta.has_field(field):
			values[field] = getattr(attendance, field, None)

	frappe.db.set_value("Attendance", attendance_name, values, update_modified=True)

	for checkin_name in computed.checkin_names:
		frappe.db.set_value(
			"Employee Checkin",
			checkin_name,
			{"attendance": attendance_name, "skip_auto_attendance": 0},
			update_modified=False,
		)

	if before_status != attendance.status or flt(before_hours) != flt(computed.total_hours):
		attendance.add_comment(
			"Comment",
			text=_(
				"Hours recalculated from all check-ins for the day "
				"({0}h → {1}h, {2} → {3})."
			).format(before_hours, computed.total_hours, before_status, attendance.status),
		)

	return frappe.get_doc("Attendance", attendance_name)


def sync_existing_attendance_on_checkin(doc, method=None):
	"""after_insert: fold a late punch into attendance that was already marked."""
	if not getattr(doc, "employee", None) or not getattr(doc, "time", None):
		return
	if frappe.flags.get("skip_attendance_checkin_sync"):
		return
	sync_attendance_hours_from_checkins(doc.employee, getdate(doc.time))
