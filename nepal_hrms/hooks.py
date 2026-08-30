app_name = "nepal_hrms"
app_title = "Nepal HRMS"
app_publisher = "Yarsa Labs Pvt. Ltd."
app_description = "Nepali HR and Payroll (Bikram Sambat) for Frappe HR"
app_email = "support@yarsalabs.com"
app_license = "GNU General Public License (v3)"
app_logo_url = "/assets/nepal_hrms/icon/app-icon.svg"
app_home = "/bshrms"
required_apps = ["hrms", "nepal_compliance"]

website_route_rules = [
	{"from_route": "/bshrms/<path:app_path>", "to_route": "bshrms"},
]

add_to_apps_screen = [
	{
		"name": "bshrms",
		"logo": "/assets/nepal_hrms/icon/app-icon.svg",
		"title": "BS HRMS",
		"route": "/bshrms",
		"has_permission": "nepal_hrms.utils.check_app_permission",
	}
]

app_include_css = [
	"/assets/nepal_hrms/css/attendance_bar.css",
]

app_include_js = [
	"/assets/nepal_hrms/js/employee_benefit_claim.js",
	"/assets/nepal_hrms/js/attendance_cnr_bulk.js",
	"/assets/nepal_hrms/js/attendance_policy_escape_list.js",
]

boot_session = "nepal_hrms.boot.get_boot_info"

doctype_js = {
	"Salary Slip": "public/js/salary_slip_nepali.js",
	"Payroll Entry": "public/js/payroll_entry_nepali.js",
	"Attendance": "public/js/attendance_cnr.js",
	"Late Entry Application": "public/js/cnr_application.js",
	"Early Exit Application": "public/js/cnr_application.js",
	"Out of Office Application": "public/js/cnr_application.js",
}

doctype_list_js = {
	"Salary Component": "public/js/custom_button.js",
	"Leave Allocation": "public/js/leave_allocation.js",
	"Attendance": "public/js/attendance_list_cnr.js",
	"Attendance Policy Escape": "public/js/attendance_policy_escape_list.js",
}

after_install = "nepal_hrms.install.install"
# Custom fields must be re-synced on every migrate: create_custom_fields() was
# previously reachable only from after_install, so any field added later never
# appeared on existing sites (it just silently failed the has_field guards).
after_migrate = ["nepal_hrms.custom_field.create_custom_fields"]
after_sync = [
	"nepal_hrms.custom_code.payroll.salary_structure.create_salary_structures",
	"nepal_hrms.custom_code.leave_type.leave_type.setup_default_leave_types",
	"nepal_hrms.setup_roles.setup_roles",
]

before_uninstall = "nepal_hrms.uninstall.cleanup_salary_structures"

override_doctype_class = {
	"Salary Structure": "nepal_hrms.overrides.salary_structure.CustomSalaryStructure",
	"Employee Benefit Claim": "nepal_hrms.overrides.employee_benefit_claim.CustomEmployeeBenefitClaim",
	"Salary Slip": "nepal_hrms.overrides.salary_slip.CustomSalarySlip",
	"Payroll Entry": "nepal_hrms.overrides.salary_slip.CustomPayrollEntry",
	"Leave Policy Assignment": "nepal_hrms.custom_code.leave_allocation.monthly_leave_bs.LeavePolicyAssignment",
	"Employee Checkin": "nepal_hrms.overrides.employee_checkin.CustomEmployeeCheckin",
	"Shift Type": "nepal_hrms.overrides.shift_type.NepalShiftType",
	"Attendance Request": "nepal_hrms.overrides.attendance_request.CustomAttendanceRequest",
}

doc_events = {
	"Salary Slip": {
		"after_insert": "nepal_hrms.patches.payroll_entry.execute",
	},
	"Employee Checkin": {
		"validate": "nepal_hrms.api.ooo_attendance.validate_ooo_checkin",
	},
	"Attendance": {
		"validate": "nepal_hrms.custom_code.attendance_hooks.validate_attendance",
		"before_submit": [
			"nepal_hrms.custom_code.attendance_hooks.before_submit_attendance",
			"nepal_hrms.api.ooo_attendance.check_ooo_hold",
		],
		"on_update": "nepal_hrms.custom_code.attendance_hooks.on_update_attendance",
		"after_insert": "nepal_hrms.custom_code.attendance_hooks.after_insert_attendance",
	},
	"Salary Structure Assignment": {
		"validate": [
			# breakdown first: the encashment formula may reference basic_remuneration
			"nepal_hrms.custom_code.payroll.salary_breakdown.sync_salary_breakdown",
			"nepal_hrms.custom_code.salary_structure_assignment.validate_leave_encashment",
		]
	},
	"Leave Application": {
		"validate": "nepal_hrms.custom_code.leave_application_hooks.validate_sandwich_leave_application"
	},
}

override_whitelisted_methods = {
	"hrms.hr.doctype.employee_checkin.employee_checkin.mark_attendance_and_link_log":
		"nepal_hrms.overrides.attendance_override.custom_mark_attendance_and_link_log",
	"hrms.api.get_attendance_requests":
		"nepal_hrms.overrides.hrms_api.get_attendance_requests",
}

scheduler_events = {
	"daily": [
		"nepal_hrms.custom_code.leave_allocation.scheduled_tasks.run_daily_bs_tasks",
		"nepal_hrms.api.ooo_attendance.cleanup_old_path_logs",
	]
}

override_doctype_dashboards = {
	"Attendance": "nepal_hrms.overrides.attendance_dashboard.get_data",
	"Employee": "nepal_hrms.overrides.employee_dashboard.get_data",
}
