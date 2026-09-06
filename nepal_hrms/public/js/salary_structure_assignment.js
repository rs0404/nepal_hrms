// Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Salary Structure Assignment", {
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
			() => {
				nepal_hrms.form_help.attach(frm, {
					form_class: "nh-ssa-form",
					fieldnames: [
						"custom_nepal_salary_section",
						"custom_basic_salary",
						"custom_dearness_allowance",
						"custom_grade_amount",
						"custom_basic_remuneration",
						"custom_total_allowances",
						"custom_total_fixed_remuneration",
						"custom_allowance_section",
						"custom_allowances",
						"custom_leave_encashment_formula",
					],
				});
			}
		);
	},
});
