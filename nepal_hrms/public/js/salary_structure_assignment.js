// Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Salary Structure Assignment", {
	onload(frm) {
		frappe.require([
			"/assets/nepal_hrms/css/nepal_hrms_settings.css",
			"/assets/nepal_hrms/js/form_help.js",
		]);
		suggest_leave_encashment_formula(frm);
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
		suggest_leave_encashment_formula(frm);
	},
});

function suggest_leave_encashment_formula(frm) {
	// Settings only suggest: never overwrite a value the user (or a prior save) already set.
	if (frm.doc.custom_leave_encashment_formula) return;
	if (frm._nh_encashment_formula_suggested) return;
	frm._nh_encashment_formula_suggested = true;

	frappe.db.get_single_value("Nepal HRMS Settings", "default_leave_encashment_formula").then((formula) => {
		if (!formula || frm.doc.custom_leave_encashment_formula) return;
		frm.set_value("custom_leave_encashment_formula", formula);
	});
}
