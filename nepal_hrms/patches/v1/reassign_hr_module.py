import frappe

HR_SETTINGS_FIELDS = [
	"use_nepali_date_in_attendance",
	"show_working_hours_in_attendance",
	"enable_late_early_penalty",
	"late_early_grace_mins",
	"late_early_max_delay_mins",
	"initial_grace_occurrences",
	"subsequent_grace_step_occurrences",
	"combine_late_and_early_pool",
	"enable_late_full_day_escalation",
	"late_full_day_after_occurrences",
	"enable_late_early_application_deadline",
	"late_early_application_max_days",
	"enable_leave_sandwich_rule",
	"block_sandwich_leave_application",
	"max_paid_out_of_office_hours",
	"enable_continuous_lwp_gross_deduction",
	"continuous_lwp_threshold_days",
]

HR_DOCTYPES = [
	"Late Entry Application",
	"Early Exit Application",
	"Out of Office Application",
	"Attendance Policy Escape",
	"Employee Path Log",
	"Nepal HRMS Settings",
]

HR_CUSTOM_FIELD_DOCTYPES = [
	"Employee",
	"Expense Claim",
	"Salary Component",
	"Salary Slip",
	"Employee Checkin",
	"Attendance",
	"HR Settings",
	"Leave Allocation",
	"Leave Type",
	"Leave Application",
	"Payroll Entry",
	"Income Tax Slab",
	"Payroll Period",
	"Salary Structure",
	"Salary Structure Assignment",
	"Bulk Salary Structure Assignment",
	"Salary Withholding",
	"Additional Salary",
	"Employee Incentive",
	"Retention Bonus",
	"Employee Tax Exemption Declaration",
	"Employee Tax Exemption Proof Submission",
	"Employee Benefit Application",
	"Employee Benefit Claim",
	"Compensatory Leave Request",
	"Attendance Request",
	"Employee Advance",
	"Job Offer",
	"Employee Referral",
	"Shift Assignment",
	"Shift Request",
	"Shift Assignment Tool",
	"Employee Attendance Tool",
	"Upload Attendance",
	"Leave Period",
	"Leave Policy Assignment",
	"Leave Control Panel",
	"Leave Encashment",
]


def execute():
	_reassign_doctypes()
	_reassign_custom_fields()
	_reassign_report_and_page()
	_copy_hr_settings()
	from nepal_hrms.custom_field import create_custom_fields

	create_custom_fields()


def _reassign_doctypes():
	for name in HR_DOCTYPES:
		if frappe.db.exists("DocType", name):
			frappe.db.set_value("DocType", name, "module", "Nepal HRMS", update_modified=False)


def _reassign_custom_fields():
	frappe.db.sql(
		"""
		UPDATE `tabCustom Field`
		SET module = 'Nepal HRMS'
		WHERE dt IN ({placeholders})
		""".format(placeholders=", ".join(["%s"] * len(HR_CUSTOM_FIELD_DOCTYPES))),
		tuple(HR_CUSTOM_FIELD_DOCTYPES),
	)


def _reassign_report_and_page():
	if frappe.db.exists("Report", "Monthly Attendance Sheet BS"):
		frappe.db.set_value(
			"Report", "Monthly Attendance Sheet BS", "module", "Nepal HRMS", update_modified=False
		)
	for page_name in ("live_attendance_boar-1", "live_attendance_board", "live_attendance_boar"):
		if frappe.db.exists("Page", page_name):
			frappe.db.set_value("Page", page_name, "module", "Nepal HRMS", update_modified=False)


def _copy_hr_settings():
	if not frappe.db.exists("DocType", "Nepal Compliance Settings"):
		return
	if not frappe.db.exists("DocType", "Nepal HRMS Settings"):
		return

	source = frappe.db.get_singles_dict("Nepal Compliance Settings") or {}
	target = frappe.get_single("Nepal HRMS Settings")
	changed = False
	for fieldname in HR_SETTINGS_FIELDS:
		if fieldname in source and source.get(fieldname) is not None:
			target.set(fieldname, source.get(fieldname))
			changed = True
	if changed:
		target.save(ignore_permissions=True)
