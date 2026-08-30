// Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Nepal HRMS Settings", {
	run_payroll_setup(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint({
				title: __("Unsaved Changes"),
				message: __("Save the settings first — setup reads the account mapping and overtime multiplier from the saved document."),
				indicator: "orange",
			});
			return;
		}

		frappe.confirm(
			__("Create the Nepal salary components, four salary structures and the income tax slab?<br><br>Existing records are updated in place, never duplicated. Salary structures already on this site are left untouched."),
			() => {
				frappe.call({
					method: "nepal_hrms.custom_code.payroll.setup.setup_nepal_payroll",
					freeze: true,
					freeze_message: __("Setting up Nepal payroll…"),
					callback: (r) => {
						if (!r.message) return;
						frm.events.show_setup_result(frm, r.message);
					},
				});
			}
		);
	},

	run_scheduled_payroll_now(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint({
				title: __("Unsaved Changes"),
				message: __("Save the settings first — the run reads the scheduled rows from the saved document."),
				indicator: "orange",
			});
			return;
		}

		const action = frm.doc.scheduled_payroll_action || "Create Payroll Entry Only";
		const submits = action === "Create, and Submit Salary Slips";
		const warning = submits
			? `<p style="color:var(--text-danger)"><b>${__(
					"This will submit salary slips and post the accrual journal entry."
			  )}</b></p>`
			: "";

		frappe.confirm(
			`${warning}<p>${__("Run the scheduled payroll now for the period that just ended?")}</p>
			 <p>${__("Mode")}: <b>${frappe.utils.escape_html(action)}</b></p>`,
			() => {
				frappe.call({
					method: "nepal_hrms.custom_code.payroll.scheduled_payroll.run_now",
					freeze: true,
					freeze_message: __("Running payroll…"),
					callback: (r) => {
						const results = r.message || [];
						if (!results.length) {
							frappe.msgprint(__("Nothing to do — no enabled rows, or entries already exist for this period."));
							return;
						}
						const rows = results
							.map(
								(i) =>
									`<tr><td>${frappe.utils.escape_html(i.row)}</td>
									 <td>${frappe.utils.escape_html(i.status)}</td>
									 <td>${frappe.utils.escape_html(i.detail)}</td></tr>`
							)
							.join("");
						frappe.msgprint({
							title: __("Scheduled Payroll"),
							wide: true,
							message: `<table class="table table-bordered"><thead><tr>
								<th>${__("Run")}</th><th>${__("Status")}</th><th>${__("Detail")}</th>
								</tr></thead><tbody>${rows}</tbody></table>`,
						});
					},
				});
			}
		);
	},

	show_setup_result(frm, log) {
		const rows = (list, cols) =>
			list.map((i) => `<tr>${cols.map((c) => `<td>${frappe.utils.escape_html(String(i[c] ?? ""))}</td>`).join("")}</tr>`).join("");

		let html = `<p>${__("Salary components created or updated")}: <b>${log.components}</b></p>`;

		if (!log.account_rows) {
			html += `<p style="color:var(--text-muted)">${__(
				"No rows in the Component Account Mapping table, so no accounts were assigned. Add them and re-run to avoid setting each component's account by hand."
			)}</p>`;
		}

		html += `<h5>${__("Salary Structures")}</h5>
			<table class="table table-bordered"><thead><tr>
			<th>${__("Structure")}</th><th>${__("Result")}</th></tr></thead>
			<tbody>${rows(log.structures, ["name", "action"])}</tbody></table>`;

		html += `<h5>${__("Income Tax Slab")}</h5>
			<table class="table table-bordered"><thead><tr>
			<th>${__("Slab")}</th><th>${__("Result")}</th><th>${__("Source")}</th></tr></thead>
			<tbody>${rows(log.tax_slabs, ["name", "action", "source"])}</tbody></table>`;

		frappe.msgprint({ title: __("Nepal Payroll Setup"), message: html, wide: true });
	},
});
