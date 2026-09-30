frappe.ui.form.on("Attendance", {
	setup(frm) {
		frm.make_methods = frm.make_methods || {};
		frm.make_methods["Leave Application"] = () => create_linked_application(frm, "Leave Application");
		frm.make_methods["Attendance Request"] = () =>
			create_linked_application(frm, "Attendance Request");
	},
	refresh(frm) {
		ensure_attendance_connections(frm);

		if (frm.is_new()) return;

		// Keep HRMS link fields visible (Attendance Request / Leave Application)
		["attendance_request", "leave_application"].forEach((fn) => {
			if (frm.fields_dict[fn]) {
				frm.set_df_property(fn, "hidden", 0);
				frm.set_df_property(fn, "read_only", 1);
			}
		});

		frm.add_custom_button(__("Recalculate Late/Early"), () => {
			frappe.call({
				method: "nepal_hrms.custom_code.attendance_policy.recalculate_attendance_late_early",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Recalculating..."),
				callback(r) {
					if (r.message && r.message.ok) {
						frappe.show_alert({
							message: __("Late/early minutes and attendance status rechecked"),
							indicator: "green",
						});
						frm.reload_doc();
					}
				},
			});
		});

		show_related_application_links(frm);
	},
});

function create_linked_application(frm, doctype) {
	const values = {
		employee: frm.doc.employee,
		company: frm.doc.company,
	};
	if (doctype === "Leave Application") {
		values.from_date = frm.doc.attendance_date;
		values.to_date = frm.doc.attendance_date;
	} else if (doctype === "Attendance Request") {
		values.from_date = frm.doc.attendance_date;
		values.to_date = frm.doc.attendance_date;
	}
	frappe.new_doc(doctype, values);
}

function ensure_attendance_connections(frm) {
	if (!frm.dashboard) return;

	if (!frm.dashboard.data) {
		frm.dashboard.init_data();
	}
	const data = frm.dashboard.data;
	data.method = "nepal_hrms.overrides.attendance_dashboard.get_open_count";
	data.internal_links = data.internal_links || {};
	delete data.internal_links["Leave Application"];
	delete data.internal_links["Attendance Request"];

	data.internal_and_external_links = data.internal_and_external_links || {};
	data.internal_and_external_links["Leave Application"] = "leave_application";
	data.internal_and_external_links["Attendance Request"] = "attendance_request";

	const wanted = [
		"Employee Checkin",
		"Leave Application",
		"Attendance Request",
		"Late Entry Application",
		"Early Exit Application",
		"Out of Office Application",
	];

	if (!data.transactions || !data.transactions.length) {
		data.transactions = [{ label: "", items: [] }];
	}

	const group = data.transactions[0];
	const items = list(group.items || []);
	wanted.forEach((dt) => {
		if (!items.includes(dt) && frappe.model.can_read(dt)) {
			items.push(dt);
		}
	});
	group.items = wanted.filter((dt) => items.includes(dt));

	const needs_rerender =
		!frm.dashboard.data_rendered ||
		!frm.dashboard.transactions_area ||
		!frm.dashboard.transactions_area.find(
			'.document-link[data-doctype="Leave Application"]'
		).length ||
		!frm.dashboard.transactions_area.find(
			'.document-link[data-doctype="Attendance Request"]'
		).length ||
		!frm.dashboard.transactions_area.find(
			'.document-link[data-doctype="Leave Application"] .btn-new'
		).length ||
		!frm.dashboard.transactions_area.find(
			'.document-link[data-doctype="Attendance Request"] .btn-new'
		).length;

	if (needs_rerender && frm.dashboard.transactions_area) {
		frm.dashboard._fetched_counts = false;
		frm.dashboard.transactions_area.empty();
		frm.dashboard.data_rendered = false;
		frm.dashboard.render_links();
		frm.dashboard.after_refresh();
	}
}

function list(arr) {
	return Array.isArray(arr) ? arr.slice() : [];
}

function show_related_application_links(frm) {
	frappe.call({
		method: "nepal_hrms.api.attendance_calendar.get_attendance_related_applications",
		args: {
			employee: frm.doc.employee,
			attendance_date: frm.doc.attendance_date,
			attendance: frm.doc.name,
		},
		freeze: false,
		callback(r) {
			const data = r.message || {};
			const links = data.links || [];

			const leaveLinks = links.filter((row) => row.doctype === "Leave Application");
			const requestLinks = links.filter((row) => row.doctype === "Attendance Request");
			const otherLinks = links.filter(
				(row) =>
					row.doctype !== "Leave Application" &&
					row.doctype !== "Attendance Request"
			);

			set_attendance_link_field(frm, "leave_application", leaveLinks, __("Leave Application"));
			set_attendance_link_field(
				frm,
				"attendance_request",
				requestLinks,
				__("Attendance Request")
			);

			const headlineParts = [];
			leaveLinks.forEach((row) => headlineParts.push(format_related_link(row)));
			requestLinks.forEach((row) => headlineParts.push(format_related_link(row)));
			otherLinks.forEach((row) => headlineParts.push(format_related_link(row)));

			if (!headlineParts.length) {
				frm.dashboard.clear_headline();
				return;
			}
			frm.dashboard.set_headline(
				__("Related Applications") + ": " + headlineParts.join(" · ")
			);
		},
	});
}

function format_related_link(row) {
	const route = frappe.utils.get_form_link(row.doctype, row.name, true);
	const status = row.status ? ` (${row.status})` : "";
	const label = row.label || row.name;
	// The headline is one line of links joined by separators, so the reason goes
	// in the tooltip rather than inline where it would swamp the row.
	const reasonParts = [];
	if (row.reason) reasonParts.push(row.reason);
	if (row.status === "Rejected" && row.rejection_reason) {
		reasonParts.push(`${__("Rejected")}: ${row.rejection_reason}`);
	}
	const title = reasonParts.length
		? ` title="${frappe.utils.escape_html(reasonParts.join(" — "))}"`
		: "";
	return `<a href="${route}"${title}>${frappe.utils.escape_html(__(row.doctype))}: ${frappe.utils.escape_html(label)}${frappe.utils.escape_html(status)}</a>`;
}

function set_attendance_link_field(frm, fieldname, rows, emptyLabel) {
	if (!frm.fields_dict[fieldname]) return;

	frm.set_df_property(fieldname, "hidden", 0);
	frm.set_df_property(fieldname, "read_only", 1);

	if (!rows.length) {
		frm.set_df_property(
			fieldname,
			"description",
			__("No linked {0} for this date", [emptyLabel])
		);
		return;
	}

	const html = rows
		.map((row) => {
			const route = frappe.utils.get_form_link(row.doctype, row.name, true);
			const status = row.status ? ` · ${frappe.utils.escape_html(row.status)}` : "";
			return `<a href="${route}" target="_blank">${frappe.utils.escape_html(row.name)}</a>${status}`;
		})
		.join("<br>");
	frm.set_df_property(fieldname, "description", html);
}
