frappe.ui.form.on("Salary Slip", {
	onload(frm) {
		frappe.require([
			"/assets/nepal_hrms/css/nepal_hrms_settings.css",
			"/assets/nepal_hrms/js/form_help.js",
		]);
	},

	refresh(frm) {
		frappe.require(
			[
				"/assets/nepal_hrms/css/nepal_hrms_settings.css",
				"/assets/nepal_hrms/js/form_help.js",
			],
			() => attach_salary_slip_help(frm)
		);
	},

	employee: function (frm) {
        if (!frm.doc.employee) return;

        frappe.call({
            method: "nepal_hrms.utils.get_suggested_payroll_dates",
            args: { employee: frm.doc.employee },
            callback: function (r) {
                if (r.message && r.message.start_date && r.message.end_date) {
                    frm.set_value("start_date", r.message.start_date);
                    frm.set_value("end_date", r.message.end_date);
                    frappe.show_alert({
                        message: __('Auto-populated dates based on Nepali calendar'),
                        indicator: 'green'
                    });
                }
            }
        });
    },

    start_date: function (frm) {
        if (frm.doc.start_date) {
            frappe.call({
                method: "nepal_hrms.utils.get_suggested_payroll_dates",
                args: { start_date: frm.doc.start_date },
                callback: function (r) {
                    if (r.message && r.message.is_first_day && r.message.end_date) {
                        frm.set_value("end_date", r.message.end_date);
                        frappe.show_alert({
                            message: __('End date auto-filled for the payroll period'),
                            indicator: 'green'
                        });
                    }
                    validate_payroll_days(frm);
                }
            });
        } else {
            validate_payroll_days(frm);
        }
    },

    end_date: function (frm) {
        validate_payroll_days(frm);
    }
});

function validate_payroll_days(frm) {
    if (frm.doc.start_date && frm.doc.end_date) {
        let diff = frappe.datetime.get_day_diff(frm.doc.end_date, frm.doc.start_date) + 1;
        if (diff > 32) {
            frappe.msgprint({
                title: __('Warning'),
                indicator: 'orange',
                message: __('The selected period is {0} days, which is greater than 32 days. Please verify the dates. You may have selected 2 months period.', [diff])
            });
        }
    }
}

const SALARY_SLIP_HELP_FIELDS = [
	"custom_daily_divisor_used",
	"custom_overtime_hours",
	"custom_paid_leave_days",
	"custom_late_entry_half_days",
	"custom_late_entry_full_days",
	"custom_early_exit_half_days",
	"custom_early_exit_full_days",
	"custom_out_of_office_half_days",
	"custom_unapproved_absent_days",
	"custom_late_deduction_rate",
	"custom_lwp_deduction_rate",
	"custom_unapproved_absent_rate",
	"custom_is_continuous_lwp_gross",
	"custom_is_period_leave_gross",
	"custom_late_deduction_amount",
	"custom_lwp_deduction_amount",
	"custom_unapproved_absent_deduction_amount",
	"custom_leave_late_deduction_total",
	"custom_annual_tax_projection_section",
	"custom_projected_annual_tds",
	"custom_tds_paid_till_date",
	"custom_remaining_payroll_periods",
	"custom_current_period_tds",
	"custom_assessable_employment_income",
	"custom_one_third_assessable_income",
	"custom_total_retirement_contribution",
	"custom_annual_retirement_limit",
	"custom_allowed_retirement_deduction",
	"custom_annual_taxable_deductions",
];

function attach_salary_slip_help(frm) {
	if (!nepal_hrms?.form_help?.attach) return;
	nepal_hrms.form_help.attach(frm, {
		form_class: "nh-salary-slip-form",
		fieldnames: SALARY_SLIP_HELP_FIELDS,
		include_sections: true,
		hide_all_descriptions: false,
	});
}
