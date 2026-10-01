app_name = "nepal_hrms"
app_title = "Nepal HRMS"
app_publisher = "Yarsa Labs Pvt. Ltd."
app_description = "Nepali HR and Payroll (Bikram Sambat) for Frappe HR"
app_email = "support@yarsalabs.com"
app_license = "GNU General Public License (v3)"
app_logo_url = "/assets/nepal_hrms/icon/app-icon.svg"
# /bshrms always redirects to the configured PWA route, so it never goes stale.
app_home = "/bshrms"
# Org-qualified on purpose. A bare name that is not yet in the bench's apps.txt
# sends frappe's installer to GitHub to guess the repo, and an app that lives in
# neither the frappe nor the erpnext org 404s with InvalidRemoteException instead
# of the "please install X first" message it meant to show. The repo segment must
# spell the module name, because install_app matches it against installed_apps.
required_apps = ["frappe/hrms", "yarsa/nepal_compliance"]

# The PWA's route is a setting, so it is served by a page renderer that reads
# it per request instead of a route rule fixed here. See nepal_hrms/pwa_route.py.
page_renderer = ["nepal_hrms.pwa_route.PWAPage"]

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
	"/assets/nepal_hrms/css/attendance_bar.css?v=20260919c",
]

app_include_js = [
	"/assets/nepal_hrms/js/date_approval_hint.js",
	"/assets/nepal_hrms/js/employee_benefit_claim.js",
	"/assets/nepal_hrms/js/attendance_cnr_bulk.js",
	"/assets/nepal_hrms/js/attendance_policy_escape_list.js",
	"/assets/nepal_hrms/js/icon_patch.js",
	"/assets/nepal_hrms/js/salary_slip_attendance_sync.js",
]

boot_session = "nepal_hrms.boot.get_boot_info"

# nepal_compliance registers the same Salary Slip after_insert and daily BS task.
# Merged hooks fire both, so neutralise its copies per worker process.
before_request = ["nepal_hrms.compat.nepal_compliance.apply"]
before_job = ["nepal_hrms.compat.nepal_compliance.apply"]

doctype_js = {
	"Salary Slip": "public/js/salary_slip_nepali.js",
	"Payroll Entry": "public/js/payroll_entry_nepali.js",
	"Attendance": "public/js/attendance_cnr.js",
	"Attendance Request": "public/js/attendance_request.js",
	"Leave Application": "public/js/leave_application.js",
	"Late Entry Application": "public/js/cnr_application.js",
	"Early Exit Application": "public/js/cnr_application.js",
	"Out of Office Application": "public/js/cnr_application.js",
	"Salary Structure Assignment": "public/js/salary_structure_assignment.js",
	"Salary Structure": "public/js/salary_structure.js",
	"Additional Salary": "public/js/additional_salary.js",
}

doctype_list_js = {
	"Salary Component": "public/js/custom_button.js",
	"Salary Slip": "public/js/salary_slip_list.js",
	"Leave Allocation": "public/js/leave_allocation.js",
	"Attendance": "public/js/attendance_list_cnr.js",
	"Attendance Policy Escape": "public/js/attendance_policy_escape_list.js",
	"Late Entry Application": "public/js/cnr_application_list.js",
	"Early Exit Application": "public/js/cnr_application_list.js",
	"Out of Office Application": "public/js/cnr_application_list.js",
}

after_install = "nepal_hrms.install.install"
# Custom fields must be re-synced on every migrate: create_custom_fields() was
# previously reachable only from after_install, so any field added later never
# appeared on existing sites (it just silently failed the has_field guards).
after_migrate = [
	"nepal_hrms.custom_field.create_custom_fields",
	"nepal_hrms.notifications.raven_sync.seed_notification_rows_on_migrate",
]
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
	"Leave Application": "nepal_hrms.overrides.leave_application.CustomLeaveApplication",
}

doc_events = {
	"Salary Slip": {
		"after_insert": "nepal_hrms.patches.payroll_entry.execute",
	},
	"Employee Checkin": {
		"validate": "nepal_hrms.api.ooo_attendance.validate_ooo_checkin",
		"after_insert": [
			"nepal_hrms.custom_code.application_hooks.sync_cnr_application_from_checkin",
			"nepal_hrms.overrides.attendance_override.sync_existing_attendance_on_checkin",
		],
	},
	"Attendance": {
		"validate": "nepal_hrms.custom_code.attendance_hooks.validate_attendance",
		"on_submit": "nepal_hrms.notifications.pwa.notify_attendance",
		"before_submit": [
			"nepal_hrms.custom_code.attendance_hooks.before_submit_attendance",
			"nepal_hrms.api.ooo_attendance.check_ooo_hold",
		],
		"on_update": "nepal_hrms.custom_code.attendance_hooks.on_update_attendance",
		"after_insert": "nepal_hrms.custom_code.attendance_hooks.after_insert_attendance",
	},
	"Late Entry Application": {
		"validate": "nepal_hrms.custom_code.application_hooks.validate_late_early_application",
		"after_insert": "nepal_hrms.notifications.pwa.notify_application_created",
		"before_submit": "nepal_hrms.custom_code.application_hooks.before_submit_cnr_application",
		"on_submit": [
			"nepal_hrms.custom_code.application_hooks.on_submit_late_early_application",
			"nepal_hrms.notifications.pwa.notify_application_decided",
		],
		"on_cancel": "nepal_hrms.custom_code.application_hooks.on_cancel_late_early_application",
	},
	"Early Exit Application": {
		"validate": "nepal_hrms.custom_code.application_hooks.validate_late_early_application",
		"after_insert": "nepal_hrms.notifications.pwa.notify_application_created",
		"before_submit": "nepal_hrms.custom_code.application_hooks.before_submit_cnr_application",
		"on_submit": [
			"nepal_hrms.custom_code.application_hooks.on_submit_late_early_application",
			"nepal_hrms.notifications.pwa.notify_application_decided",
		],
		"on_cancel": "nepal_hrms.custom_code.application_hooks.on_cancel_late_early_application",
	},
	"Out of Office Application": {
		"validate": "nepal_hrms.custom_code.application_hooks.validate_ooo_application",
		"after_insert": "nepal_hrms.notifications.pwa.notify_application_created",
		"before_submit": "nepal_hrms.custom_code.application_hooks.before_submit_cnr_application",
		"on_submit": [
			"nepal_hrms.custom_code.application_hooks.on_submit_ooo_application",
			"nepal_hrms.notifications.pwa.notify_application_decided",
		],
		"on_cancel": "nepal_hrms.custom_code.application_hooks.on_cancel_ooo_application",
	},
	"Salary Structure Assignment": {
		"validate": [
			# breakdown first: the encashment formula may reference basic_remuneration
			"nepal_hrms.custom_code.payroll.salary_breakdown.sync_salary_breakdown",
			"nepal_hrms.custom_code.salary_structure_assignment.validate_leave_encashment",
		]
	},
	"Additional Salary": {
		"validate": "nepal_hrms.custom_code.payroll.component_variant.validate_component_variant",
	},
	# Approval follows the org chart (custom_code/approval_authority.py). Leave
	# Application's check lives in its class override, ahead of Frappe HR's.
	"Shift Request": {
		"validate": "nepal_hrms.custom_code.approval_hooks.validate_shift_request_approval",
		"before_submit": "nepal_hrms.custom_code.approval_hooks.before_submit_shift_request",
	},
	"Compensatory Leave Request": {
		"before_submit": "nepal_hrms.custom_code.approval_hooks.before_submit_compensatory_leave_request",
	},
	"Leave Application": {
		"validate": [
			"nepal_hrms.custom_code.leave_application_hooks.validate_leave_application_reason",
			"nepal_hrms.custom_code.leave_application_hooks.validate_half_day_session",
			"nepal_hrms.custom_code.leave_application_hooks.validate_sandwich_leave_application",
			"nepal_hrms.custom_code.leave_application_hooks.validate_leave_balance_including_drafts",
			"nepal_hrms.custom_code.leave_application_hooks.validate_leave_application_deadline",
		],
		# Runs after HRMS has written the half-day Attendance: settle the worked
		# half now, or check-ins punched before the approval are never re-read.
		"on_submit": "nepal_hrms.custom_code.half_day.on_leave_application_change",
		"on_update_after_submit": "nepal_hrms.custom_code.half_day.on_leave_application_change",
	},
}

override_whitelisted_methods = {
	"hrms.hr.doctype.employee_checkin.employee_checkin.mark_attendance_and_link_log":
		"nepal_hrms.overrides.attendance_override.custom_mark_attendance_and_link_log",
	"hrms.api.get_attendance_requests":
		"nepal_hrms.overrides.hrms_api.get_attendance_requests",
	"hrms.api.get_leave_applications":
		"nepal_hrms.overrides.hrms_api.get_leave_applications",
}

scheduler_events = {
	"daily": [
		"nepal_hrms.custom_code.leave_allocation.scheduled_tasks.run_daily_bs_tasks",
		"nepal_hrms.api.ooo_attendance.cleanup_old_path_logs",
		"nepal_hrms.custom_code.payroll.scheduled_payroll.run_scheduled_payroll",
	]
}

override_doctype_dashboards = {
	"Attendance": "nepal_hrms.overrides.attendance_dashboard.get_data",
	"Employee": "nepal_hrms.overrides.employee_dashboard.get_data",
}
