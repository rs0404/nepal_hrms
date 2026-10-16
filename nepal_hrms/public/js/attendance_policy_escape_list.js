// Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings["Attendance Policy Escape"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Bulk Assign…"), () => {
			nepal_hrms.attendance_policy_escape.open_bulk_dialog();
		});
	},
};

frappe.provide("nepal_hrms.attendance_policy_escape");

nepal_hrms.attendance_policy_escape.open_bulk_dialog = function () {
	const d = new frappe.ui.Dialog({
		title: __("Bulk Assign Attendance Policy Escape"),
		size: "large",
		fields: [
			{
				fieldname: "department",
				label: __("Filter by Department"),
				fieldtype: "Link",
				options: "Department",
				description: __("Optional — narrows the employee list only"),
				onchange() {
					const emp = d.fields_dict.employees;
					if (emp && emp.set_value) {
						emp.set_value([]);
					}
				},
			},
			{
				fieldname: "employees",
				label: __("Employees"),
				fieldtype: "MultiSelectList",
				reqd: 1,
				get_data(txt) {
					const filters = { status: "Active" };
					const dept = d.get_value("department");
					if (dept) {
						filters.department = dept;
					}
					return frappe.db.get_link_options("Employee", txt, filters);
				},
			},
			{
				fieldname: "from_date",
				label: __("From Date"),
				fieldtype: "Date",
			},
			{
				fieldname: "to_date",
				label: __("To Date"),
				fieldtype: "Date",
			},
			{
				fieldname: "section_flags",
				fieldtype: "Section Break",
				label: __("Escape Rules"),
			},
			{
				fieldname: "escape_sandwich",
				label: __("Escape Sandwich Rule"),
				fieldtype: "Check",
				default: 0,
			},
			{
				fieldname: "escape_late_early",
				label: __("Escape Late Entry / Early Exit"),
				fieldtype: "Check",
				default: 0,
			},
			{
				fieldname: "escape_continuous_lwp_gross",
				label: __("Escape Consecutive LWP Gross"),
				fieldtype: "Check",
				default: 0,
			},
			{
				fieldname: "col_flags",
				fieldtype: "Column Break",
			},
			{
				fieldname: "escape_absent_gross",
				label: __("Escape Absent Gross"),
				fieldtype: "Check",
				default: 0,
			},
			{
				fieldname: "escape_applications",
				label: __("Escape Late / Early / OOO Applications"),
				fieldtype: "Check",
				default: 0,
			},
			{
				fieldname: "escape_attendance_deduction",
				label: __("Escape Attendance-Based Deduction"),
				fieldtype: "Check",
				default: 0,
				description: __("Only LWP leave deducts; attendance does not affect pay"),
			},
			{
				fieldname: "escape_ssf_earned_scaling",
				label: __("SSF Amount Independent of Leave"),
				fieldtype: "Check",
				default: 0,
				description: __("SSF stays on the fixed amount; leave and absence do not reduce it"),
			},
			{
				fieldname: "allow_self_approval",
				label: __("Allow Self-Approval"),
				fieldtype: "Check",
				default: 0,
				description: __("They may approve their own applications and requests"),
			},
			{
				fieldname: "allow_approve_all",
				label: __("Allow Approving Everyone"),
				fieldtype: "Check",
				default: 0,
				description: __("They may approve anyone's applications and requests. System Manager only."),
				hidden: !frappe.user.has_role("System Manager"),
			},
			{
				fieldname: "section_reason",
				fieldtype: "Section Break",
			},
			{
				fieldname: "reason",
				label: __("Reason"),
				fieldtype: "Small Text",
			},
		],
		primary_action_label: __("Create Escapes"),
		primary_action(values) {
			let employees = values.employees || [];
			if (typeof employees === "string") {
				employees = employees
					.split(",")
					.map((s) => s.trim())
					.filter(Boolean);
			}
			if (!employees.length) {
				frappe.msgprint(__("Select at least one employee"));
				return;
			}
			const flags = [
				values.escape_sandwich,
				values.escape_late_early,
				values.escape_continuous_lwp_gross,
				values.escape_absent_gross,
				values.escape_applications,
				values.escape_attendance_deduction,
				values.escape_ssf_earned_scaling,
				values.allow_self_approval,
				values.allow_approve_all,
			];
			if (!flags.some((v) => cint(v))) {
				frappe.msgprint(__("Select at least one escape rule"));
				return;
			}

			frappe.call({
				method: "nepal_hrms.api.policy_escape.bulk_assign_attendance_policy_escapes",
				args: {
					employees: employees,
					from_date: values.from_date || null,
					to_date: values.to_date || null,
					escape_sandwich: cint(values.escape_sandwich),
					escape_late_early: cint(values.escape_late_early),
					escape_continuous_lwp_gross: cint(values.escape_continuous_lwp_gross),
					escape_absent_gross: cint(values.escape_absent_gross),
					escape_applications: cint(values.escape_applications),
					escape_attendance_deduction: cint(values.escape_attendance_deduction),
					escape_ssf_earned_scaling: cint(values.escape_ssf_earned_scaling),
					allow_self_approval: cint(values.allow_self_approval),
					allow_approve_all: cint(values.allow_approve_all),
					reason: values.reason || "",
					is_active: 1,
				},
				freeze: true,
				freeze_message: __("Creating escapes…"),
				callback(r) {
					if (!r.message) return;
					const res = r.message;
					d.hide();
					frappe.msgprint({
						title: __("Bulk Assign Complete"),
						indicator: res.created_count ? "green" : "orange",
						message: __(
							"Created {0} escape(s). Skipped {1}.",
							[res.created_count, res.skipped_count]
						),
					});
					if (cur_list && cur_list.doctype === "Attendance Policy Escape") {
						cur_list.refresh();
					}
				},
			});
		},
	});

	d.show();
};
