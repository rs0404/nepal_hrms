// Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
// For license information, please see license.txt

// Hide the wrong variant from the salary component picker. Stock only filters
// on company and disabled, so a salaried employee's one-off overtime can be
// raised against the Wages component and post to the wrong expense account.
//
// Components with no variant suffix (TDS, CIT, Insurance, the SSF and PF
// contributions) post to liability accounts and stay available to everyone,
// so the filter excludes the opposite variant rather than requiring a match.

frappe.ui.form.on("Additional Salary", {
	onload(frm) {
		frm.trigger("nepal_fetch_variant");
	},

	employee(frm) {
		frm.trigger("nepal_fetch_variant");
	},

	payroll_date(frm) {
		frm.trigger("nepal_fetch_variant");
	},

	from_date(frm) {
		frm.trigger("nepal_fetch_variant");
	},

	// Stock re-sets its own component query on company change, so re-apply ours after it.
	company(frm) {
		frm.trigger("nepal_apply_component_filter");
	},

	nepal_fetch_variant(frm) {
		if (!frm.doc.employee) {
			frm.nepal_variant = null;
			frm.trigger("nepal_apply_component_filter");
			return;
		}

		frappe.call({
			method: "nepal_hrms.custom_code.payroll.component_variant.get_employee_variant",
			args: {
				employee: frm.doc.employee,
				on_date: frm.doc.payroll_date || frm.doc.from_date,
			},
			callback(r) {
				frm.nepal_variant = r.message || null;
				frm.trigger("nepal_apply_component_filter");
			},
		});
	},

	nepal_apply_component_filter(frm) {
		frm.set_query("salary_component", function () {
			const filters = { disabled: 0 };
			if (frm.doc.company) filters.company = frm.doc.company;
			if (frm.nepal_variant) {
				const opposite = frm.nepal_variant === "Salary" ? "Wages" : "Salary";
				filters.name = ["not like", `% - ${opposite}`];
			}
			return { filters: filters };
		});
	},
});
