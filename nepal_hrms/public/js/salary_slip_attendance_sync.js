// Payroll Settings "Leave" mode makes HRMS ignore Attendance, so a draft slip can
// sit on stale absence figures. These buttons re-pull them on demand.

frappe.provide("nepal_hrms.salary_slip_sync");

nepal_hrms.salary_slip_sync = {
	call(slips, dry_run) {
		return frappe.call({
			method: "nepal_hrms.api.salary_slip_sync.sync_with_attendance",
			args: { slips: JSON.stringify(slips), dry_run: dry_run ? 1 : 0 },
			freeze: true,
			freeze_message: dry_run
				? __("Checking against Attendance…")
				: __("Syncing with Attendance…"),
		});
	},

	fmt(n) {
		return format_number(n, null, 2);
	},

	preview_html(res) {
		const rows = (res.results || []).filter((r) => r.changed);
		if (!rows.length) {
			return `<p>${__("All selected slips already match Attendance.")}</p>`;
		}
		// Same vocabulary as the Monthly Attendance Sheet BS: late / early penalties
		// on their own line, "Absent" meaning only genuine unapproved absence. The
		// raw absent_days HRMS keeps internally lumps the two together.
		// Only a figure that moves is drawn as before → after and coloured, so the
		// eye lands on what the sync changes; an unchanged one is shown once, muted.
		// Compared as displayed, so float noise below 2 decimals never lights up.
		const cell = (r, field) => {
			const before = this.fmt(r.before[field]);
			const after = this.fmt(r.after[field]);
			if (before === after) {
				return `<td class="text-right text-muted">${after}</td>`;
			}
			return `<td class="text-right" style="background:var(--yellow-highlight-color, #fff5cc);">
				<span class="text-muted">${before}</span> &rarr;
				<b style="color:var(--orange-600, #c2410c);">${after}</b>
			</td>`;
		};
		const body = rows
			.map(
				(r) => `<tr>
					<td>${frappe.utils.escape_html(r.employee_name || r.employee)}</td>
					${cell(r, "custom_penalty_days")}
					${cell(r, "custom_unapproved_absent_days")}
					${cell(r, "leave_without_pay")}
					${cell(r, "custom_paid_leave_days")}
					${cell(r, "net_pay")}
				</tr>`
			)
			.join("");
		return `<table class="table table-bordered table-sm">
			<thead><tr>
				<th>${__("Employee")}</th>
				<th class="text-right">${__("Penalty Days")}</th>
				<th class="text-right">${__("Absent Days")}</th>
				<th class="text-right">${__("LWP")}</th>
				<th class="text-right">${__("Paid Leaves")}</th>
				<th class="text-right">${__("Net Pay")}</th>
			</tr></thead><tbody>${body}</tbody></table>
			<p class="text-muted small">${__(
				"Penalty Days are late / early ½P and 1P written on Attendance. Absent Days are genuine unapproved absences only. Same split as the Monthly Attendance Sheet BS."
			)}</p>`;
	},

	skipped_html(res) {
		const rows = res.skipped || [];
		if (!rows.length) return "";
		const items = rows
			.map((s) => `<li>${frappe.utils.escape_html(s.name)} — ${frappe.utils.escape_html(s.reason)}</li>`)
			.join("");
		return `<p class="text-muted">${__("Skipped")}:</p><ul class="text-muted">${items}</ul>`;
	},

	// Dry-run first so the payroll officer sees the money move before it moves.
	run(slips, on_done) {
		this.call(slips, 1).then((r) => {
			const res = r.message;
			if (!res) return;
			const changed = (res.results || []).filter((x) => x.changed);
			if (!changed.length) {
				frappe.msgprint({
					title: __("Already in sync"),
					message: this.preview_html(res) + this.skipped_html(res),
					indicator: "green",
				});
				return;
			}
			const d = new frappe.ui.Dialog({
				title: __("Sync {0} Salary Slip(s) with Attendance", [changed.length]),
				size: "large",
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "preview",
						options: this.preview_html(res) + this.skipped_html(res),
					},
				],
				primary_action_label: __("Apply"),
				primary_action: () => {
					d.hide();
					this.call(slips, 0).then((r2) => {
						const out = r2.message || {};
						frappe.show_alert({
							message: __("{0} slip(s) synced with Attendance", [out.synced || 0]),
							indicator: "green",
						});
						if (on_done) on_done(out);
					});
				},
			});
			d.show();
		});
	},
};

frappe.ui.form.on("Salary Slip", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 0) return;
		frm.add_custom_button(
			__("Sync with Attendance"),
			() =>
				nepal_hrms.salary_slip_sync.run([frm.doc.name], () =>
					frm.reload_doc()
				),
			__("Tools")
		);
	},
});
