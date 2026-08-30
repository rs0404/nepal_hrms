import frappe
from frappe import _


def create_custom_fields():
	custom_fields = {
		"Employee": [
			{"fieldname": "revised_salary", "label": "Revised Salary", "fieldtype": "Currency", "insert_after": "payroll_cost_center", "reqd": 0, "allow_on_submit": 1},
		],
		"Expense Claim": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "posting_date", "allow_on_submit": 1},
		],
		"Salary Component": [
			{"fieldname": "include_in_taxable_salary", "label": "Include In Taxable Salary", "fieldtype": "Check", "insert_after": "is_income_tax_component", "allow_on_submit": 1, "description": "Check this if this component is to be included in taxable salary calculation of Nepal HRMS."},
		],
		"Salary Slip": [
			{"fieldname": "nepali_start_date", "label": "Nepali Start Date", "fieldtype": "Data", "insert_after": "start_date", "allow_on_submit": 1},
			{"fieldname": "nepali_end_date", "label": "Nepali End Date", "fieldtype": "Data", "insert_after": "end_date", "allow_on_submit": 1},
			{"fieldname": "taxable_salary", "label": "Taxable Salary", "fieldtype": "Currency", "insert_after": "total_deduction", "allow_on_submit": 1},
			{"fieldname": "custom_tax_breakup_html", "label": "Detailed Tax Calculation", "fieldtype": "HTML", "insert_after": "income_tax_calculation_breakup_section"},
			{"fieldname": "custom_tax_calculation_data", "label": "Tax Calculation Data", "fieldtype": "Long Text", "insert_after": "custom_tax_breakup_html", "hidden": 1, "allow_on_submit": 1},
		],
		"Employee Checkin": [
			{"fieldname": "custom_attendance_type", "label": "Attendance Type", "fieldtype": "Select", "options": "Normal\nOOO Work", "default": "Normal", "insert_after": "log_type", "in_list_view": 1, "allow_on_submit": 1},
			{"fieldname": "custom_reason", "label": "OOO Reason", "fieldtype": "Small Text", "insert_after": "custom_attendance_type", "depends_on": "eval:doc.custom_attendance_type == 'OOO Work'", "allow_on_submit": 1},
			{"fieldname": "custom_is_approved", "label": "Is Approved", "fieldtype": "Check", "insert_after": "custom_reason", "default": 0, "allow_on_submit": 1, "description": "Set by Leave Approver to approve OOO Work check-ins"},
			{"fieldname": "custom_ooo_rejected", "label": "OOO Rejected", "fieldtype": "Check", "insert_after": "custom_is_approved", "default": 0, "allow_on_submit": 1, "description": "Set by Leave Approver when OOO Work check-ins are rejected"},
			{"fieldname": "custom_ooo_rejection_reason", "label": "OOO Rejection Reason", "fieldtype": "Small Text", "insert_after": "custom_ooo_rejected", "depends_on": "eval:doc.custom_ooo_rejected", "allow_on_submit": 1},
		],
		"Attendance": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "attendance_date", "allow_on_submit": 1},
			{"fieldname": "custom_ooo_hold", "label": "OOO Hold", "fieldtype": "Check", "insert_after": "modify_half_day_status", "default": 0, "allow_on_submit": 1, "description": "Attendance is on hold pending OOO Work approval by Leave Approver"},
			{"fieldname": "custom_has_ooo_logs", "label": "Has OOO Logs", "fieldtype": "Check", "insert_after": "custom_ooo_hold", "default": 0, "allow_on_submit": 1, "read_only": 1},
			{"fieldname": "custom_late_mins", "label": "Late Minutes", "fieldtype": "Int", "insert_after": "late_entry", "default": 0, "allow_on_submit": 1, "read_only": 1, "description": "Minutes after shift start (before grace is applied for payroll)"},
			{"fieldname": "custom_early_mins", "label": "Early Exit Minutes", "fieldtype": "Int", "insert_after": "early_exit", "default": 0, "allow_on_submit": 1, "read_only": 1, "description": "Minutes before shift end (before grace is applied for payroll)"},
			{"fieldname": "custom_cnr_unexcused_late", "label": "Unexcused Late — Half Day", "fieldtype": "Check", "insert_after": "custom_late_mins", "default": 0, "allow_on_submit": 1, "read_only": 1, "description": "Set for major (beyond max delay) late with no covering leave / Office Work excuse"},
			{"fieldname": "custom_cnr_unexcused_early", "label": "Unexcused Early Exit — Half Day", "fieldtype": "Check", "insert_after": "custom_early_mins", "default": 0, "allow_on_submit": 1, "read_only": 1, "description": "Set for major (beyond max delay) early exit with no covering leave / Office Work excuse"},
			{"fieldname": "custom_cnr_late_in_pool", "label": "In Late Occurrence Pool", "fieldtype": "Check", "insert_after": "custom_cnr_unexcused_late", "default": 0, "allow_on_submit": 1, "read_only": 1, "description": "Grace→max late with no approved Late Entry Application; counts toward monthly half-day / full-day pool"},
			{"fieldname": "custom_cnr_early_in_pool", "label": "In Early Occurrence Pool", "fieldtype": "Check", "insert_after": "custom_cnr_unexcused_early", "default": 0, "allow_on_submit": 1, "read_only": 1, "description": "Grace→max early exit with no approved Early Exit Application; counts toward monthly pool"},
			{"fieldname": "custom_cnr_month_late_pool_count", "label": "Month Late Pool Count", "fieldtype": "Int", "insert_after": "custom_cnr_late_in_pool", "default": 0, "allow_on_submit": 1, "read_only": 1, "description": "Calendar-month count of attendance days in the late occurrence pool for this employee (as of this date)"},
			{"fieldname": "custom_cnr_month_early_pool_count", "label": "Month Early Pool Count", "fieldtype": "Int", "insert_after": "custom_cnr_early_in_pool", "default": 0, "allow_on_submit": 1, "read_only": 1, "description": "Calendar-month count of attendance days in the early occurrence pool for this employee (as of this date)"},
			{"fieldname": "custom_ooo_hours", "label": "OOO Hours", "fieldtype": "Float", "insert_after": "custom_has_ooo_logs", "default": 0, "allow_on_submit": 1, "read_only": 1, "description": "Approved Out of Office / OOO Work hours for the day"},
		],
		"HR Settings": [
			{"fieldname": "custom_ooo_section", "label": "OOO Work Settings", "fieldtype": "Section Break", "insert_after": "allow_geolocation_tracking"},
			{"fieldname": "custom_gps_tracking_interval", "label": "GPS Tracking Interval (seconds)", "fieldtype": "Int", "insert_after": "custom_ooo_section", "default": 300, "description": "Interval in seconds for GPS position logging during OOO Work sessions"},
			{"fieldname": "custom_ooo_column_break", "label": "", "fieldtype": "Column Break", "insert_after": "custom_gps_tracking_interval"},
			{"fieldname": "custom_path_log_retention_days", "label": "Path Log Retention (days)", "fieldtype": "Int", "insert_after": "custom_ooo_column_break", "default": 0, "description": "Number of days to retain Employee Path Logs. Set to 0 for Always Retain."},
		],
		"Leave Allocation": [
			{"fieldname": "from_nepali_date_leave_allocation", "label": "From Date BS", "fieldtype": "Data", "insert_after": "from_date", "allow_on_submit": 1},
			{"fieldname": "to_nepali_date_leave_allocation", "label": "To Date BS", "fieldtype": "Data", "insert_after": "to_date", "allow_on_submit": 1},
		],
		"Leave Type": [
			{"fieldname": "allocate_leave_on_start_of_bs_month", "label": "Allocate Leave on Start of BS Month", "fieldtype": "Check", "insert_after": "max_continuous_days_allowed", "description": "Make sure Is Earned Leave is unchecked if you check it.", "allow_on_submit": 1},
			{"fieldname": "bs_monthly_allocation_amount", "label": "BS Monthly Allocation Amount", "fieldtype": "Float", "insert_after": "allocate_leave_on_start_of_bs_month", "depends_on": "eval:doc.allocate_leave_on_start_of_bs_month == 1", "mandatory_depends_on": "eval:doc.allocate_leave_on_start_of_bs_month == 1", "description": "Amount of leave to be allocated at the start of each BS month eg: 0.5 for half day, 1.0 for full day.", "allow_on_submit": 1},
		],
		"Leave Application": [
			{"fieldname": "from_nepali_date_leave_application", "label": "From Date BS", "fieldtype": "Data", "insert_after": "from_date", "allow_on_submit": 1},
			{"fieldname": "to_nepali_date_leave_application", "label": "To Date BS", "fieldtype": "Data", "insert_after": "to_date", "allow_on_submit": 1},
		],
		"Payroll Entry": [
			{"fieldname": "nepali_start_date", "label": "Start Date BS", "fieldtype": "Data", "insert_after": "start_date", "allow_on_submit": 1},
			{"fieldname": "nepali_end_date", "label": "End Date BS", "fieldtype": "Data", "insert_after": "end_date", "allow_on_submit": 1},
		],
		"Income Tax Slab": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "effective_from", "allow_on_submit": 1},
		],
		"Payroll Period": [
			{"fieldname": "nepali_start_date", "label": "Start Date BS", "fieldtype": "Data", "insert_after": "start_date", "allow_on_submit": 1},
			{"fieldname": "nepali_end_date", "label": "End Date BS", "fieldtype": "Data", "insert_after": "end_date", "allow_on_submit": 1},
		],
		"Salary Structure": [
			{"fieldname": "custom_leave_encashment_formula", "label": "Leave Encashment Formula", "fieldtype": "Small Text", "insert_after": "leave_encashment_amount_per_day", "description": "Formula for Leave Encashment Per Day (e.g., base * 0.6 / 30). Use 'base' for base salary.", "allow_on_submit": 1},
		],
		"Salary Structure Assignment": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "from_date", "allow_on_submit": 1},
			{"fieldname": "custom_leave_encashment_formula", "label": "Leave Encashment Formula", "fieldtype": "Small Text", "insert_after": "leave_encashment_amount_per_day", "description": "Formula for Leave Encashment Per Day (e.g., basic_remuneration / 30). Use 'base' for total fixed remuneration.", "allow_on_submit": 1},
			# Nepal salary breakdown. Deliberately NOT allow_on_submit: pay changes must go
			# through amend so there is an audit trail.
			{"fieldname": "custom_nepal_salary_section", "label": "Nepal Salary Breakdown", "fieldtype": "Section Break", "insert_after": "payroll_payable_account", "description": "Base is kept in sync with this breakdown automatically. Fill either side."},
			{"fieldname": "custom_basic_salary", "label": "Basic Salary", "fieldtype": "Currency", "insert_after": "custom_nepal_salary_section", "options": "currency", "description": "\u0906\u0927\u093e\u0930\u092d\u0942\u0924 \u0924\u0932\u092c. Base for SSF/PF, gratuity, festival allowance, overtime and leave encashment."},
			{"fieldname": "custom_dearness_allowance", "label": "Dearness Allowance", "fieldtype": "Currency", "insert_after": "custom_basic_salary", "options": "currency", "description": "\u092e\u0939\u0901\u0917\u0940 \u092d\u0924\u094d\u0924\u093e. Counts toward the statutory minimum wage. Excluded from the SSF/PF base unless enabled in Nepal HRMS Settings."},
			{"fieldname": "custom_grade_amount", "label": "Grade", "fieldtype": "Currency", "insert_after": "custom_dearness_allowance", "options": "currency", "description": "\u0917\u094d\u0930\u0947\u0921. Annual increment. Included in the SSF/PF base by default."},
			{"fieldname": "custom_nepal_salary_cb", "label": "", "fieldtype": "Column Break", "insert_after": "custom_grade_amount"},
			{"fieldname": "custom_basic_remuneration", "label": "Basic Remuneration", "fieldtype": "Currency", "insert_after": "custom_nepal_salary_cb", "options": "currency", "read_only": 1, "description": "Contribution base for SSF / PF / Gratuity, per Nepal HRMS Settings."},
			{"fieldname": "custom_total_allowances", "label": "Total Other Allowances", "fieldtype": "Currency", "insert_after": "custom_basic_remuneration", "options": "currency", "read_only": 1},
			{"fieldname": "custom_total_fixed_remuneration", "label": "Total Fixed Remuneration", "fieldtype": "Currency", "insert_after": "custom_total_allowances", "options": "currency", "read_only": 1, "description": "Basic + Dearness Allowance + Grade + Other Allowances. Written back to Base."},
			{"fieldname": "custom_allowance_section", "label": "Other Allowances", "fieldtype": "Section Break", "insert_after": "custom_total_fixed_remuneration"},
			{"fieldname": "custom_allowances", "label": "Allowances", "fieldtype": "Table", "options": "Nepal Salary Allowance", "insert_after": "custom_allowance_section", "description": "Communication, transport, fuel, housing, medical, position, remote area, etc. Each row's Abbr is usable in Salary Component formulas."},
		],
		"Bulk Salary Structure Assignment": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "payroll_payable_account", "allow_on_submit": 1},
		],
		"Salary Withholding": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "posting_date", "allow_on_submit": 1},
		],
		"Additional Salary": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "payroll_date", "allow_on_submit": 1},
		],
		"Employee Incentive": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "payroll_date", "allow_on_submit": 1},
		],
		"Retention Bonus": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "bonus_payment_date", "allow_on_submit": 1},
		],
		"Employee Tax Exemption Declaration": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "payroll_period", "allow_on_submit": 1},
		],
		"Employee Tax Exemption Proof Submission": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "payroll_period", "allow_on_submit": 1},
		],
		"Employee Benefit Application": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "payroll_period", "allow_on_submit": 1},
		],
		"Employee Benefit Claim": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "payroll_period", "allow_on_submit": 1},
			{"fieldname": "claim_festival_allowance", "label": "Claim as Festival Allowance", "fieldtype": "Check", "insert_after": "company", "description": "Amount Eligible for and to Claim will be auto set as per Employee Revised/Gross Salary. It is claimed once a year"},
		],
		"Compensatory Leave Request": [
			{"fieldname": "work_from_date_bs", "label": "Work From Date BS", "fieldtype": "Data", "insert_after": "work_from_date", "allow_on_submit": 1},
			{"fieldname": "work_end_date_bs", "label": "Work End Date BS", "fieldtype": "Data", "insert_after": "work_end_date", "allow_on_submit": 1},
		],
		"Attendance Request": [
			{"fieldname": "from_date_bs", "label": "From Date BS", "fieldtype": "Data", "insert_after": "from_date", "allow_on_submit": 1},
			{"fieldname": "to_date_bs", "label": "To Date BS", "fieldtype": "Data", "insert_after": "to_date", "allow_on_submit": 1},
			{
				"fieldname": "status",
				"label": "Status",
				"fieldtype": "Select",
				"options": "Open\nApproved\nRejected",
				"default": "Open",
				"insert_after": "explanation",
				"in_list_view": 1,
				"in_standard_filter": 1,
				"allow_on_submit": 1,
			},
			{
				"fieldname": "custom_rejection_reason",
				"label": "Rejection Reason",
				"fieldtype": "Small Text",
				"insert_after": "status",
				"depends_on": "eval:doc.status=='Rejected'",
				"mandatory_depends_on": "eval:doc.status=='Rejected'",
				"allow_on_submit": 1,
			},
		],
		"Employee Advance": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "posting_date", "allow_on_submit": 1},
		],
		"Job Offer": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "offer_date", "allow_on_submit": 1},
		],
		"Employee Referral": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "date", "allow_on_submit": 1},
		],
		"Shift Assignment": [
			{"fieldname": "start_date_bs", "label": "Start Date BS", "fieldtype": "Data", "insert_after": "start_date", "allow_on_submit": 1},
			{"fieldname": "end_date_bs", "label": "End Date BS", "fieldtype": "Data", "insert_after": "end_date", "allow_on_submit": 1},
		],
		"Shift Request": [
			{"fieldname": "from_date_bs", "label": "From Date BS", "fieldtype": "Data", "insert_after": "from_date", "allow_on_submit": 1},
			{"fieldname": "to_date_bs", "label": "To Date BS", "fieldtype": "Data", "insert_after": "to_date", "allow_on_submit": 1},
		],
		"Shift Assignment Tool": [
			{"fieldname": "start_date_bs", "label": "Start Date BS", "fieldtype": "Data", "insert_after": "start_date", "allow_on_submit": 1},
			{"fieldname": "end_date_bs", "label": "End Date BS", "fieldtype": "Data", "insert_after": "end_date", "allow_on_submit": 1},
		],
		"Employee Attendance Tool": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "date", "allow_on_submit": 1},
		],
		"Upload Attendance": [
			{"fieldname": "att_fr_date_bs", "label": "Attendance From Date BS", "fieldtype": "Data", "insert_after": "att_fr_date", "allow_on_submit": 1},
			{"fieldname": "column_break", "label": "", "fieldtype": "Column Break", "insert_after": "att_fr_date_bs"},
			{"fieldname": "att_to_date_bs", "label": "Attendance To Date BS", "fieldtype": "Data", "insert_after": "att_to_date", "allow_on_submit": 1},
		],
		"Leave Period": [
			{"fieldname": "from_date_bs", "label": "From Date BS", "fieldtype": "Data", "insert_after": "from_date", "allow_on_submit": 1},
			{"fieldname": "to_date_bs", "label": "To Date BS", "fieldtype": "Data", "insert_after": "to_date", "allow_on_submit": 1},
		],
		"Leave Policy Assignment": [
			{"fieldname": "effective_from_bs", "label": "Effective From BS", "fieldtype": "Data", "insert_after": "effective_from", "allow_on_submit": 1},
			{"fieldname": "effective_to_bs", "label": "Effective To BS", "fieldtype": "Data", "insert_after": "effective_to", "allow_on_submit": 1},
		],
		"Leave Control Panel": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "leave_policy", "allow_on_submit": 1},
		],
		"Leave Encashment": [
			{"fieldname": "encashment_date_bs", "label": "Encashment Date BS", "fieldtype": "Data", "insert_after": "encashment_date", "allow_on_submit": 1},
		],
	}

	created_fields = []

	for doctype_name, fields in custom_fields.items():
		for field in fields:
			if not frappe.db.exists("Custom Field", {"dt": doctype_name, "fieldname": field["fieldname"]}):
				custom_field = frappe.get_doc({
					"doctype": "Custom Field",
					"dt": doctype_name,
					"module": "Nepal HRMS",
					**field,
				})
				custom_field.save()
				created_fields.append({"dt": doctype_name, "fieldname": field["fieldname"]})
			else:
				frappe.db.set_value(
					"Custom Field",
					{"dt": doctype_name, "fieldname": field["fieldname"]},
					"module",
					"Nepal HRMS",
					update_modified=False,
				)

	return created_fields
