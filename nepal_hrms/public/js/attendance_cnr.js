// Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Attendance', {
	refresh(frm) {
		if (frm.is_new()) return;

		// Keep HRMS link fields visible (Attendance Request / Leave Application)
		;['attendance_request', 'leave_application'].forEach((fn) => {
			if (frm.fields_dict[fn]) {
				frm.set_df_property(fn, 'hidden', 0);
				frm.set_df_property(fn, 'read_only', 1);
			}
		});

		frm.add_custom_button(__('Recalculate Late/Early'), () => {
			frappe.call({
				method: 'nepal_hrms.custom_code.attendance_policy.recalculate_attendance_late_early',
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __('Recalculating...'),
				callback(r) {
					if (r.message && r.message.ok) {
						frappe.show_alert({
							message: __('Late/early minutes and C&R status updated'),
							indicator: 'green',
						});
						frm.reload_doc();
					}
				},
			});
		});

		show_related_application_links(frm);
	},
});

function show_related_application_links(frm) {
	frappe.call({
		method: 'nepal_hrms.api.attendance_calendar.get_attendance_related_applications',
		args: {
			employee: frm.doc.employee,
			attendance_date: frm.doc.attendance_date,
			attendance: frm.doc.name,
		},
		freeze: false,
		callback(r) {
			const data = r.message || {};
			const links = data.links || [];
			if (!links.length) {
				frm.dashboard.clear_headline();
				return;
			}
			const parts = links.map((row) => {
				const route = frappe.utils.get_form_link(row.doctype, row.name, true);
				const status = row.status ? ` (${row.status})` : '';
				return `<a href="${route}">${frappe.utils.escape_html(row.label || row.name)}${frappe.utils.escape_html(status)}</a>`;
			});
			frm.dashboard.set_headline(
				__('Related Applications') + ': ' + parts.join(' · ')
			);
		},
	});
}
