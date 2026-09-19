"""Clear late/early unexcused flags on days a half-day leave later covered.

custom_cnr_unexcused_late / _early are written when Attendance is saved. A
leave approved *after* that stamps leave_type onto the row, and the policy
hook then skips its whole penalty block (`not doc.leave_type`), so the flag
from before the approval is never recomputed. The row is left claiming an
unexcused delay on a day payroll treats as excused -- Monthly Attendance
Sheet BS read that flag and showed "E! — no application" against an approved
leave.

Only the flags are cleared. Status and the occurrence-pool fields are left
alone: those were settled when the mark was assigned, and restating them here
would reopen decisions the pool logic already made.
"""

import frappe
from frappe.utils import cint, getdate


def execute():
	if not frappe.db.has_column("Attendance", "custom_cnr_unexcused_late"):
		return

	from nepal_hrms.custom_code.attendance_policy import (
		classify_delay,
		get_approved_application,
		get_hr_settings,
	)

	settings = get_hr_settings()
	grace = cint(getattr(settings, "late_early_grace_mins", None) or 15)
	max_delay = cint(getattr(settings, "late_early_max_delay_mins", None) or 60)

	fields = [
		"name",
		"employee",
		"attendance_date",
		"custom_late_mins",
		"custom_early_mins",
		"custom_cnr_unexcused_late",
		"custom_cnr_unexcused_early",
	]
	rows = {}
	for flag in ("custom_cnr_unexcused_late", "custom_cnr_unexcused_early"):
		for row in frappe.get_all(
			"Attendance",
			filters={"docstatus": ["<", 2], flag: 1},
			fields=fields,
		):
			rows[row.name] = row

	cleared = 0
	for row in rows.values():
		updates = {}
		for field, mins_field, doctype in (
			("custom_cnr_unexcused_late", "custom_late_mins", "Late Entry Application"),
			("custom_cnr_unexcused_early", "custom_early_mins", "Early Exit Application"),
		):
			if not cint(row.get(field)):
				continue
			if classify_delay(cint(row.get(mins_field)), grace, max_delay) != "major":
				continue
			if not _has_half_day_leave_on(row.employee, row.attendance_date):
				continue
			# An Office Work slip already excused it through another path; leave
			# the flag alone there so this patch owns one reason only.
			app = get_approved_application(doctype, row.employee, row.attendance_date)
			if app and (app.type_of_work or "") == "Office Work":
				continue
			updates[field] = 0

		if updates:
			frappe.db.set_value("Attendance", row.name, updates, update_modified=False)
			cleared += 1

	if cleared:
		frappe.db.commit()
		print(f"Cleared stale unexcused late/early flags on {cleared} Attendance rows")


def _has_half_day_leave_on(employee, attendance_date):
	"""Same test as attendance_policy._has_half_day_leave."""
	return bool(
		frappe.db.exists(
			"Leave Application",
			{
				"employee": employee,
				"docstatus": 1,
				"status": "Approved",
				"from_date": ["<=", getdate(attendance_date)],
				"to_date": [">=", getdate(attendance_date)],
				"half_day": 1,
				"half_day_date": getdate(attendance_date),
			},
		)
	)
