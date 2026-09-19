import json

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
		"Salary Detail": [
			{"fieldname": "custom_fixed_amount", "label": "Fixed Amount", "fieldtype": "Currency", "options": "currency", "insert_after": "abbr", "read_only": 1, "allow_on_submit": 1, "in_list_view": 1, "columns": 2, "depends_on": "", "description": "Contractual amount before attendance deductions. Amount is the salary actually earned for the period."},
		],
		"Salary Slip": [
			{"fieldname": "nepali_start_date", "label": "Nepali Start Date", "fieldtype": "Data", "insert_after": "start_date", "allow_on_submit": 1},
			{"fieldname": "nepali_end_date", "label": "Nepali End Date", "fieldtype": "Data", "insert_after": "end_date", "allow_on_submit": 1},
			{"fieldname": "custom_ssf_base", "label": "SSF / PF Base", "fieldtype": "Currency", "options": "currency", "insert_after": "totals", "read_only": 1, "allow_on_submit": 1, "description": "Monthly contribution base for SSF, PF, gratuity, festival pay and overtime, taken from the Salary Structure Assignment. Basic Salary plus Grade by default; Dearness Allowance and Grade are toggles in Nepal HRMS Settings. Contractual, not prorated by payment days."},
			{"fieldname": "custom_fixed_gross_pay", "label": "Fixed Gross", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_ssf_base", "read_only": 1, "allow_on_submit": 1, "description": "Gross salary before attendance deductions. Standard Gross Pay is the earned gross after attendance deductions."},
			{"fieldname": "taxable_salary", "label": "Taxable Salary", "fieldtype": "Currency", "insert_after": "total_deduction", "hidden": 1, "allow_on_submit": 1},
			{"fieldname": "custom_annual_tax_projection_section", "label": "Annual Tax and Retirement Projection", "fieldtype": "Section Break", "insert_after": "base_total_deduction", "description": "Current-period TDS = (Projected Annual TDS - TDS Already Paid) / Remaining Payroll Periods. Retirement deductions are limited by Nepal's statutory cap."},
			{"fieldname": "custom_projected_annual_tds", "label": "Projected Annual TDS", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_annual_tax_projection_section", "read_only": 1, "allow_on_submit": 1, "description": "Estimated income tax for the full fiscal year after projected earnings and allowed deductions."},
			{"fieldname": "custom_tds_paid_till_date", "label": "TDS Already Paid", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_projected_annual_tds", "read_only": 1, "allow_on_submit": 1, "description": "TDS deducted on earlier submitted Salary Slips in this fiscal year, including any opening balance."},
			{"fieldname": "custom_remaining_payroll_periods", "label": "Remaining Payroll Periods", "fieldtype": "Float", "insert_after": "custom_tds_paid_till_date", "read_only": 1, "allow_on_submit": 1, "description": "Payroll periods still remaining in the fiscal year, including this Salary Slip."},
			{"fieldname": "custom_current_period_tds", "label": "Current Period TDS", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_remaining_payroll_periods", "read_only": 1, "allow_on_submit": 1, "description": "TDS allocated to this Salary Slip after spreading the unpaid annual tax over the remaining periods."},
			{"fieldname": "custom_annual_tax_projection_col", "label": "", "fieldtype": "Column Break", "insert_after": "custom_current_period_tds"},
			{"fieldname": "custom_assessable_employment_income", "label": "Annual Assessable Employment Income", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_annual_tax_projection_col", "read_only": 1, "allow_on_submit": 1, "description": "Projected taxable employment earnings before retirement deductions."},
			{"fieldname": "custom_one_third_assessable_income", "label": "One-Third of Assessable Income", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_assessable_employment_income", "read_only": 1, "allow_on_submit": 1, "description": "One-third of annual assessable employment income; one of the statutory retirement-deduction limits."},
			{"fieldname": "custom_total_retirement_contribution", "label": "Projected Retirement Contributions", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_one_third_assessable_income", "read_only": 1, "allow_on_submit": 1, "description": "Projected annual SSF, PF, gratuity and CIT contributions before applying the statutory cap."},
			{"fieldname": "custom_annual_retirement_limit", "label": "Annual Retirement Ceiling", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_total_retirement_contribution", "read_only": 1, "allow_on_submit": 1, "description": "Maximum statutory retirement deduction, currently NPR 500,000."},
			{"fieldname": "custom_allowed_retirement_deduction", "label": "Allowed Retirement Deduction", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_annual_retirement_limit", "read_only": 1, "allow_on_submit": 1, "description": "Lowest of projected contributions, one-third of assessable income and the annual retirement ceiling."},
			{"fieldname": "custom_annual_taxable_deductions", "label": "Annual Taxable Deductions", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_allowed_retirement_deduction", "read_only": 1, "allow_on_submit": 1, "description": "Total annual deductions applied before income tax is calculated, including the capped retirement deduction."},
			{"fieldname": "custom_cit_contribution_reference", "label": "CIT Contribution Election", "fieldtype": "Link", "options": "Employee CIT Contribution", "insert_after": "custom_annual_taxable_deductions", "read_only": 1, "allow_on_submit": 1, "no_copy": 1},
			{"fieldname": "custom_cit_contribution_amount", "label": "Monthly CIT Contribution", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_cit_contribution_reference", "read_only": 1, "allow_on_submit": 1},
			{"fieldname": "custom_tax_breakup_html", "label": "Detailed Tax Calculation", "fieldtype": "HTML", "insert_after": "income_tax_calculation_breakup_section", "hidden": 1},
			{"fieldname": "custom_tax_calculation_data", "label": "Tax Calculation Data", "fieldtype": "Long Text", "insert_after": "custom_tax_breakup_html", "hidden": 1, "allow_on_submit": 1},
			# Divisor snapshot: written on first calculation so a later Nepal Payroll
			# Period Override cannot restate pay that has already been computed.
			{"fieldname": "custom_daily_divisor_used", "label": "Daily Rate Divisor Used", "fieldtype": "Float", "insert_after": "total_working_days", "read_only": 1, "description": "Days this slip was divided by for per-day deductions. Frozen at first calculation."},
			{"fieldname": "custom_daily_divisor_basis", "label": "Daily Rate Basis Used", "fieldtype": "Data", "insert_after": "custom_daily_divisor_used", "read_only": 1},
			{
				"fieldname": "custom_absent_days_manual",
				"label": "Manual Absent Days Override",
				"fieldtype": "Check",
				"insert_after": "absent_days",
				"hidden": 1,
				"default": "0",
				"allow_on_submit": 1,
				"description": "When set, Absent Days on this slip are kept on save instead of being replaced from attendance.",
			},
			{"fieldname": "custom_overtime_hours", "label": "Overtime Hours", "fieldtype": "Int", "insert_after": "leave_without_pay", "description": "Hours paid as overtime this period. Formula: hours × (basic remuneration / 30 / 8) × the multiplier in Nepal HRMS Settings."},
			{"fieldname": "custom_attendance_breakdown_section", "label": "", "fieldtype": "Section Break", "insert_after": "payment_days_calculation_help"},
			{"fieldname": "custom_attendance_counts_heading", "label": "Attendance Deduction Breakdown", "fieldtype": "Heading", "insert_after": "custom_attendance_breakdown_section"},
			{"fieldname": "custom_paid_leave_days", "label": "Paid Leave Days", "fieldtype": "Float", "insert_after": "custom_attendance_counts_heading", "read_only": 1, "allow_on_submit": 1, "description": "Approved paid leave (non-LWP) in this payroll period"},
			{"fieldname": "custom_late_entry_half_days", "label": "Late Entry Half Days", "fieldtype": "Float", "insert_after": "custom_paid_leave_days", "read_only": 1, "allow_on_submit": 1, "description": "Major late arrivals only (beyond max delay). Pool ½P / 1P are written on Attendance and counted in Penalty Days, not here."},
			{"fieldname": "custom_late_entry_full_days", "label": "Late Entry Full Days", "fieldtype": "Float", "insert_after": "custom_late_entry_half_days", "read_only": 1, "allow_on_submit": 1, "description": "Unused. Pool 1P is reported in Penalty Days, not as a separate late full-day count."},
			{"fieldname": "custom_early_exit_half_days", "label": "Early Exit Half Days", "fieldtype": "Float", "insert_after": "custom_late_entry_full_days", "read_only": 1, "allow_on_submit": 1, "description": "Major early exits only (beyond max delay). Pool ½P / 1P are written on Attendance and counted in Penalty Days, not here."},
			{"fieldname": "custom_early_exit_full_days", "label": "Early Exit Full Days", "fieldtype": "Float", "insert_after": "custom_early_exit_half_days", "read_only": 1, "allow_on_submit": 1, "description": "Unused. Pool 1P is reported in Penalty Days, not as a separate early-exit full-day count."},
			{"fieldname": "custom_out_of_office_half_days", "label": "Out of Office Half Days", "fieldtype": "Float", "insert_after": "custom_early_exit_full_days", "read_only": 1, "allow_on_submit": 1, "description": "Half-day penalties for personal out-of-office time above the allowed limit."},
			{"fieldname": "custom_unapproved_absent_days", "label": "Unapproved Absent Days", "fieldtype": "Float", "insert_after": "custom_out_of_office_half_days", "read_only": 1, "allow_on_submit": 1, "description": "Genuine unapproved absences. Pool ½P / 1P days are reported separately in Penalty Days and are not counted here."},
			{"fieldname": "custom_penalty_days", "label": "Penalty Days", "fieldtype": "Float", "insert_after": "custom_unapproved_absent_days", "read_only": 1, "allow_on_submit": 1, "description": "Late / early occurrence-pool penalties written on Attendance: ½P counts 0.5 and 1P counts 1.0. Deducted on the Penalty Deduction Base in Nepal HRMS Settings."},
			{"fieldname": "custom_attendance_counts_col", "label": "", "fieldtype": "Column Break", "insert_after": "custom_penalty_days"},
			{"fieldname": "custom_deduction_rates_section", "label": "Deduction Rates", "fieldtype": "Heading", "insert_after": "custom_attendance_counts_col"},
			{"fieldname": "custom_late_deduction_rate", "label": "Late/Early/OOO Half-Day Rate", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_deduction_rates_section", "read_only": 1, "allow_on_submit": 1, "description": "Half of the configured Half-Day Deduction Base daily rate."},
			{"fieldname": "custom_lwp_deduction_rate", "label": "LWP Daily Rate", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_late_deduction_rate", "read_only": 1, "allow_on_submit": 1, "description": "Configured LWP Deduction Base daily rate, or Gross when a continuous-LWP or period-leave threshold applies."},
			{"fieldname": "custom_unapproved_absent_rate", "label": "Unapproved Absence Daily Rate", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_lwp_deduction_rate", "read_only": 1, "allow_on_submit": 1, "description": "Daily rate from the configured Unapproved Absence Deduction Base."},
			{"fieldname": "custom_penalty_deduction_rate", "label": "Penalty Daily Rate", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_unapproved_absent_rate", "read_only": 1, "allow_on_submit": 1, "description": "Daily rate from the configured Penalty Deduction Base. Falls back to the Half-Day Deduction Base when that setting is blank."},
			{"fieldname": "custom_is_continuous_lwp_gross", "label": "Continuous LWP Uses Gross Rate", "fieldtype": "Check", "insert_after": "custom_penalty_deduction_rate", "read_only": 1, "allow_on_submit": 1, "description": "Checked when a single LWP application met the continuous threshold, so LWP is deducted from Gross."},
			{"fieldname": "custom_is_period_leave_gross", "label": "Period Leave Uses Gross LWP Rate", "fieldtype": "Check", "insert_after": "custom_is_continuous_lwp_gross", "read_only": 1, "allow_on_submit": 1, "description": "Set when LWP + absent days in this period exceeded the Period Leave Threshold, so LWP is deducted from Gross."},
			{"fieldname": "custom_deduction_amounts_section", "label": "", "fieldtype": "Column Break", "insert_after": "custom_is_period_leave_gross"},
			{"fieldname": "custom_deduction_amounts_heading", "label": "Actual Deduction Amounts", "fieldtype": "Heading", "insert_after": "custom_deduction_amounts_section"},
			{"fieldname": "custom_late_deduction_amount", "label": "Late/Early/OOO Deduction Amount", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_deduction_amounts_heading", "read_only": 1, "allow_on_submit": 1, "description": "Half-day late, early-exit and out-of-office penalties multiplied by the half-day rate."},
			{"fieldname": "custom_lwp_deduction_amount", "label": "LWP Deduction Amount", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_late_deduction_amount", "read_only": 1, "allow_on_submit": 1, "description": "LWP days multiplied by the LWP daily rate."},
			{"fieldname": "custom_unapproved_absent_deduction_amount", "label": "Unapproved Absence Deduction Amount", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_lwp_deduction_amount", "read_only": 1, "allow_on_submit": 1, "description": "Unapproved absent days multiplied by the unapproved absence daily rate."},
			{"fieldname": "custom_penalty_deduction_amount", "label": "Penalty Deduction Amount", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_unapproved_absent_deduction_amount", "read_only": 1, "allow_on_submit": 1, "description": "Penalty days multiplied by the penalty daily rate."},
			{"fieldname": "custom_leave_late_deduction_total", "label": "Total Attendance Deduction", "fieldtype": "Currency", "options": "currency", "insert_after": "custom_penalty_deduction_amount", "read_only": 1, "allow_on_submit": 1, "description": "Late/early/OOO, LWP, unapproved absence and penalty deductions combined"},
			{"fieldname": "custom_attendance_breakdown_html", "label": "Attendance Deduction Explanation", "fieldtype": "HTML", "insert_after": "custom_leave_late_deduction_total"},
			{"fieldname": "custom_attendance_breakdown_data", "label": "Attendance Deduction Data", "fieldtype": "Long Text", "insert_after": "custom_attendance_breakdown_html", "hidden": 1, "allow_on_submit": 1},
		],
		"Employee Checkin": [
			{"fieldname": "custom_attendance_type", "label": "Attendance Type", "fieldtype": "Select", "options": "Normal\nOOO Work", "default": "Normal", "insert_after": "log_type", "in_list_view": 1, "allow_on_submit": 1},
			{"fieldname": "custom_reason", "label": "OOO Reason", "fieldtype": "Small Text", "insert_after": "custom_attendance_type", "depends_on": "eval:doc.custom_attendance_type == 'OOO Work'", "allow_on_submit": 1},
			{"fieldname": "custom_ooo_application", "label": "Out of Office Application", "fieldtype": "Link", "options": "Out of Office Application", "insert_after": "custom_reason", "read_only": 1, "allow_on_submit": 1},
			{"fieldname": "custom_is_approved", "label": "Is Approved", "fieldtype": "Check", "insert_after": "custom_ooo_application", "default": 0, "permlevel": 1, "allow_on_submit": 1, "description": "Set by Leave Approver to approve OOO Work check-ins"},
			{"fieldname": "custom_ooo_rejected", "label": "OOO Rejected", "fieldtype": "Check", "insert_after": "custom_is_approved", "default": 0, "permlevel": 1, "allow_on_submit": 1, "description": "Set by Leave Approver when OOO Work check-ins are rejected"},
			{"fieldname": "custom_ooo_rejection_reason", "label": "OOO Rejection Reason", "fieldtype": "Small Text", "insert_after": "custom_ooo_rejected", "depends_on": "eval:doc.custom_ooo_rejected", "permlevel": 1, "allow_on_submit": 1},
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
			{"fieldname": "custom_cnr_pool_penalty", "label": "Occurrence Pool Penalty", "fieldtype": "Select", "options": "\nhalf\nfull", "insert_after": "custom_cnr_month_early_pool_count", "allow_on_submit": 1, "read_only": 1, "description": "half = ½P (Half Day / other half absent). full = 1P (Absent). Both count as unapproved absence on payroll."},
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
			{"fieldname": "custom_attendance_sheet_acronym", "label": "Attendance Sheet Acronym", "fieldtype": "Data", "insert_after": "leave_type_name", "length": 3, "description": "Up to 3 letters on Monthly Attendance Sheet BS (e.g. LWP, SL, AHL). Leave blank for automatic initials."},
			{"fieldname": "custom_attendance_sheet_leave_group", "label": "Attendance Sheet Leave Group", "fieldtype": "Select", "options": "Annual/Home\nSick\nOther Paid", "insert_after": "custom_attendance_sheet_acronym", "description": "Groups paid leave totals on Monthly Attendance Sheet BS. Leave Without Pay types are always grouped as LWP, regardless of this value."},
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
			# Stock Payroll Entry filters by branch/department/designation only. Wages
			# and Salary structures post to different expense accounts, so a run is
			# normally per-structure.
			{"fieldname": "custom_salary_structure", "label": "Salary Structure", "fieldtype": "Link", "options": "Salary Structure", "insert_after": "designation", "description": "Restrict this run to employees assigned to one salary structure. Leave blank for every structure in the company."},
			{"fieldname": "custom_created_by_scheduler", "label": "Created by Scheduler", "fieldtype": "Check", "insert_after": "status", "read_only": 1, "default": 0, "allow_on_submit": 1},
		],
		"Income Tax Slab": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "effective_from", "allow_on_submit": 1},
		],
		"Payroll Period": [
			{"fieldname": "nepali_start_date", "label": "Start Date BS", "fieldtype": "Data", "insert_after": "start_date", "allow_on_submit": 1},
			{"fieldname": "nepali_end_date", "label": "End Date BS", "fieldtype": "Data", "insert_after": "end_date", "allow_on_submit": 1},
		],
		"Salary Structure": [
			{"fieldname": "custom_leave_encashment_formula", "label": "Leave Encashment Formula", "fieldtype": "Small Text", "insert_after": "leave_encashment_amount_per_day", "description": "Per-day Leave Encashment amount. Suggested from Nepal HRMS Settings when empty; change freely here.\n\nExamples: custom_basic_remuneration / 30, basic_remuneration / 30, base / 30.\n\nAlso available: custom_basic_salary, custom_dearness_allowance, custom_grade_amount, custom_total_fixed_remuneration, nsa_<abbr>, and structure component abbrs.", "allow_on_submit": 1},
		],
		"Salary Structure Assignment": [
			{"fieldname": "nepali_date", "label": "Nepali Date", "fieldtype": "Data", "insert_after": "from_date", "allow_on_submit": 1},
			{"fieldname": "custom_leave_encashment_formula", "label": "Leave Encashment Formula", "fieldtype": "Small Text", "insert_after": "leave_encashment_amount_per_day", "description": "Per-day Leave Encashment amount. Suggested from Nepal HRMS Settings when empty; change freely here.\n\nExamples: custom_basic_remuneration / 30, basic_remuneration / 30, base / 30.\n\nAlso available: custom_basic_salary, custom_dearness_allowance, custom_grade_amount, custom_total_fixed_remuneration, nsa_<abbr>, and structure component abbrs.", "allow_on_submit": 1},
			# Nepal salary breakdown. Deliberately NOT allow_on_submit: pay changes must go
			# through amend so there is an audit trail.
			{"fieldname": "custom_nepal_salary_section", "label": "Nepal Salary Breakdown", "fieldtype": "Section Break", "insert_after": "payroll_payable_account", "description": "Base is kept in sync with this breakdown automatically. Fill Basic, Dearness Allowance, Grade and Other Allowances; Base is updated from the total."},
			{"fieldname": "custom_basic_salary", "label": "Basic Salary", "fieldtype": "Currency", "insert_after": "custom_nepal_salary_section", "options": "currency", "description": "\u0906\u0927\u093e\u0930\u092d\u0942\u0924 \u0924\u0932\u092c. Base for SSF/PF, gratuity, festival allowance, overtime and leave encashment."},
			{"fieldname": "custom_dearness_allowance", "label": "Dearness Allowance", "fieldtype": "Currency", "insert_after": "custom_basic_salary", "options": "currency", "description": "\u092e\u0939\u0901\u0917\u0940 \u092d\u0924\u094d\u0924\u093e. Counts toward the statutory minimum wage. Excluded from the SSF/PF base unless enabled in Nepal HRMS Settings."},
			{"fieldname": "custom_grade_amount", "label": "Grade Amount", "fieldtype": "Currency", "insert_after": "custom_dearness_allowance", "options": "currency", "description": "\u0917\u094d\u0930\u0947\u0921. Annual increment. Included in the SSF/PF base by default."},
			{"fieldname": "custom_nepal_salary_cb", "label": "", "fieldtype": "Column Break", "insert_after": "custom_grade_amount"},
			{"fieldname": "custom_basic_remuneration", "label": "Basic Remuneration", "fieldtype": "Currency", "insert_after": "custom_nepal_salary_cb", "options": "currency", "read_only": 1, "description": "Contribution base for SSF / PF / Gratuity, per Nepal HRMS Settings."},
			{"fieldname": "custom_total_allowances", "label": "Total Other Allowances", "fieldtype": "Currency", "insert_after": "custom_basic_remuneration", "options": "currency", "read_only": 1, "description": "Sum of the Other Allowances table below. Included in Base / Total Fixed Remuneration."},
			{"fieldname": "custom_total_fixed_remuneration", "label": "Total Fixed Remuneration", "fieldtype": "Currency", "insert_after": "custom_total_allowances", "options": "currency", "read_only": 1, "description": "Basic + Dearness Allowance + Grade + Other Allowances. Written back to Base."},
			{"fieldname": "custom_allowance_section", "label": "Other Allowances", "fieldtype": "Section Break", "insert_after": "custom_total_fixed_remuneration", "description": "Other Allowances are entered here on the Assignment — not only on Salary Structure → Earnings.\n\nNepal Payroll structures (name starts with Nepal Payroll -):\nThese rows are added to the Salary Slip automatically. You do not need them under Structure → Earnings.\n\nExample: Assignment has Transport Allowance = 3,000. The slip will show Transport Allowance = 3,000 even though it is missing from the structure Earnings table.\n\nStructures you create yourself:\nThe same component must also be under Structure → Earnings, and its formula must be nsa_<abbr> (e.g. nsa_transport if Abbr is transport). Only then does the slip take the amount from this table.\n\nExample: Component Transport Allowance, Abbr transport, formula nsa_transport. Assignment row amount 3,000 → slip pays 3,000. If the structure uses a fixed amount instead of that formula, the slip uses the structure amount and ignores this table.\n\nIf the component is only here and not on a custom structure's Earnings, it raises Base but is not paid."},
			{"fieldname": "custom_allowances", "label": "Allowances", "fieldtype": "Table", "options": "Nepal Salary Allowance", "insert_after": "custom_allowance_section", "description": "Add rows such as communication, transport, fuel, housing, medical, position, or remote area.\n\nEach component needs an Abbr — that becomes the formula key nsa_<abbr>. Example: Abbr transport → formula nsa_transport.\n\nNepal Payroll structures: amounts here are paid on the slip automatically.\n\nYour own structures: add the same component under Earnings with formula nsa_<abbr>, or the amount will not be paid from this table."},
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
		"Late Entry Application": [
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
		"Early Exit Application": [
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
		"Out of Office Application": [
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
			existing_name = frappe.db.get_value(
				"Custom Field",
				{"dt": doctype_name, "fieldname": field["fieldname"]},
			)
			if not existing_name:
				custom_field = frappe.get_doc({
					"doctype": "Custom Field",
					"dt": doctype_name,
					"module": "Nepal HRMS",
					**field,
				})
				custom_field.save()
				created_fields.append({"dt": doctype_name, "fieldname": field["fieldname"]})
			else:
				updatable_keys = {
					"label",
					"fieldtype",
					"options",
					"insert_after",
					"description",
					"read_only",
					"hidden",
					"allow_on_submit",
					"collapsible",
					"depends_on",
					"mandatory_depends_on",
					"default",
					"permlevel",
					"in_list_view",
					"in_standard_filter",
					"columns",
				}
				updates = {
					key: value
					for key, value in field.items()
					if key in updatable_keys
				}
				updates["module"] = "Nepal HRMS"
				frappe.db.set_value(
					"Custom Field",
					existing_name,
					updates,
					update_modified=False,
				)

	_place_salary_slip_ssf_base_above_fixed_gross()
	_place_salary_slip_lwp_and_overtime_under_absent_days()
	_ensure_salary_slip_absent_days_editable()
	return created_fields


def _move_fields_after(order, fields_to_move, after):
	"""Return a copy of order with fields_to_move placed immediately after `after`."""
	order = list(order)
	if after not in order:
		return order
	moving = [fn for fn in fields_to_move if fn in order]
	for fn in moving:
		order.remove(fn)
	idx = order.index(after) + 1
	for offset, fn in enumerate(moving):
		order.insert(idx + offset, fn)
	return order


def _place_salary_slip_ssf_base_above_fixed_gross():
	"""Put SSF / PF Base immediately above Fixed Gross in the Totals section.

	An existing field_order Property Setter already pins custom_fixed_gross_pay,
	so a new custom field's insert_after alone would not lift it above.
	"""
	ps_name = frappe.db.get_value(
		"Property Setter",
		{
			"doc_type": "Salary Slip",
			"property": "field_order",
			"doctype_or_field": "DocType",
		},
		"name",
	)
	if not ps_name:
		# No pinned order yet: insert_after on the two fields is enough.
		return

	order = json.loads(frappe.db.get_value("Property Setter", ps_name, "value") or "[]")
	if "custom_ssf_base" not in order:
		order = order + ["custom_ssf_base"]

	new_order = _move_fields_after(
		order,
		("custom_ssf_base", "custom_fixed_gross_pay"),
		"totals",
	)
	if new_order == order:
		return

	frappe.db.set_value(
		"Property Setter", ps_name, "value", json.dumps(new_order), update_modified=False
	)
	frappe.clear_cache(doctype="Salary Slip")


def _place_salary_slip_lwp_and_overtime_under_absent_days():
	"""Put Leave Without Pay and Overtime Hours in the right column under Absent Days."""
	ps_name = frappe.db.get_value(
		"Property Setter",
		{
			"doc_type": "Salary Slip",
			"property": "field_order",
			"doctype_or_field": "DocType",
		},
		"name",
	)
	if ps_name:
		order = json.loads(frappe.db.get_value("Property Setter", ps_name, "value") or "[]")
	else:
		order = [df.fieldname for df in frappe.get_meta("Salary Slip").fields]

	new_order = _move_fields_after(
		order,
		("leave_without_pay", "custom_overtime_hours"),
		"absent_days",
	)
	if new_order == order:
		return

	value = json.dumps(new_order)
	if ps_name:
		frappe.db.set_value("Property Setter", ps_name, "value", value, update_modified=False)
	else:
		frappe.get_doc(
			{
				"doctype": "Property Setter",
				"doctype_or_field": "DocType",
				"doc_type": "Salary Slip",
				"property": "field_order",
				"property_type": "Small Text",
				"value": value,
				"is_system_generated": 1,
				"module": "Nepal HRMS",
			}
		).insert(ignore_permissions=True)

	frappe.clear_cache(doctype="Salary Slip")


def _ensure_salary_slip_absent_days_editable():
	"""Allow payroll users to override absent days like Leave Without Pay."""
	if frappe.db.exists(
		"Property Setter",
		{
			"doc_type": "Salary Slip",
			"fieldname": "absent_days",
			"property": "read_only",
		},
	):
		return
	frappe.make_property_setter(
		{
			"doctype": "Salary Slip",
			"fieldname": "absent_days",
			"property": "read_only",
			"value": "0",
			"property_type": "Check",
		},
		is_system_generated=1,
	)
	frappe.clear_cache(doctype="Salary Slip")
