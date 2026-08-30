# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Override for mark_attendance_and_link_log from HRMS.
When unapproved OOO Work check-ins are present:
  - Attendance is Draft (or held) with custom_ooo_hold=1
  - Working hours exclude unapproved OOO until Leave Approver approves
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, time_diff_in_hours

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
	compute_late_early_minutes,
	get_approved_application,
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


def _status_from_hours(working_hours, shift_name=None):
	"""Map hours to Present/Half Day/Absent using shift thresholds when available."""
	hours = flt(working_hours)
	absent_th = half_th = 0
	if shift_name:
		absent_th, half_th = frappe.db.get_value(
			"Shift Type",
			shift_name,
			["working_hours_threshold_for_absent", "working_hours_threshold_for_half_day"],
		) or (0, 0)
		absent_th = flt(absent_th)
		half_th = flt(half_th)
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
