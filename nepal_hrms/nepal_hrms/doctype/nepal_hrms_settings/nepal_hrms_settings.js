// Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
// For license information, please see license.txt

(() => {
const NH_SETTINGS_CSS = "/assets/nepal_hrms/css/nepal_hrms_settings.css";
const NH_SKIP_HELP_TYPES = new Set([
	"Tab Break",
	"Section Break",
	"Column Break",
	"HTML",
	"Heading",
	"Fold",
]);

let nh_help_doc_bound = false;

function nh_help_html(text) {
	if (!text) return "";
	return String(__(text)).replace(/\n/g, "<br>");
}

function nh_hide_popovers() {
	$(".nh-field-help").popover("hide");
}

function nh_bind_help_button($anchor, content) {
	if (!$anchor.length || !content) return;
	if ($anchor.find(".nh-field-help").length) return;

	const $btn = $(`<button type="button" class="btn-reset nh-field-help" aria-label="${__(
		"Help"
	)}">${frappe.utils.icon("help", "sm")}</button>`);
	$anchor.append($btn);

	$btn.popover({
		trigger: "manual",
		placement: "auto",
		html: true,
		sanitize: false,
		container: "body",
		template: `<div class="popover nh-help-popover" role="tooltip">
			<div class="arrow"></div>
			<div class="popover-body"></div>
		</div>`,
		content: () => `<div class="nh-help-body">${content}</div>`,
	});

	$btn.on("click", (e) => {
		e.preventDefault();
		e.stopPropagation();
		const open = $btn.attr("aria-describedby");
		nh_hide_popovers();
		if (!open) $btn.popover("show");
	});
}

function nh_help_anchor_for_field(field) {
	if (field.df.fieldtype === "Button") {
		const $button = field.$wrapper.find("button").first();
		if (!$button.length) return $();
		let $help = field.$wrapper.find(".nh-button-help");
		if (!$help.length) {
			$help = $('<span class="help nh-button-help"></span>');
			$button.after($help);
		}
		return $help;
	}

	if (field.df.fieldtype === "Check") {
		const $label = field.$wrapper.find(".checkbox label");
		let $help = field.$wrapper.find(".nh-check-help");
		if (!$help.length) {
			$help = field.$wrapper.find("span.help").first();
			if ($help.parent().is("label")) {
				$help.addClass("nh-check-help").insertAfter($label);
			} else {
				$help = $('<span class="help nh-check-help"></span>').insertAfter($label);
			}
		}
		return $help;
	}

	return field.$wrapper.find("span.help").first();
}

function nh_attach_settings_help(frm) {
	frm.$wrapper.addClass("nh-settings-form");

	Object.values(frm.fields_dict || {}).forEach((field) => {
		if (!field?.df || !field.$wrapper) return;
		if (NH_SKIP_HELP_TYPES.has(field.df.fieldtype)) return;
		const content = nh_help_html(field.df.description);
		if (!content) return;
		nh_bind_help_button(nh_help_anchor_for_field(field), content);
	});

	(frm.layout.sections || []).forEach((section) => {
		const content = nh_help_html(section.df?.description);
		if (!content || !section.head?.length) return;
		if (section.head.find(".nh-field-help").length) return;

		const $help = $('<span class="help nh-section-help"></span>');
		const $indicator = section.head.find(".collapse-indicator");
		if ($indicator.length) {
			$indicator.before($help);
		} else {
			section.head.append($help);
		}
		nh_bind_help_button($help, content);
		$help.on("click", (e) => e.stopPropagation());
	});

	frm.$wrapper
		.off("shown.bs.tab.nh-help")
		.on("shown.bs.tab.nh-help", ".form-tabs a", nh_hide_popovers);

	if (!nh_help_doc_bound) {
		nh_help_doc_bound = true;
		$(document).on("click.nh-settings-help", (e) => {
			if (!$(e.target).closest(".nh-field-help, .popover.nh-help-popover").length) {
				nh_hide_popovers();
			}
		});
	}
}

frappe.ui.form.on("Nepal HRMS Settings", {
	onload(frm) {
		frappe.require(NH_SETTINGS_CSS);
	},

	refresh(frm) {
		frappe.require(NH_SETTINGS_CSS, () => nh_attach_settings_help(frm));
	},

	setup(frm) {
		// Accounts are posted against a specific company, so a row's account list is
		// only meaningful once that row names one. Group accounts can't take entries.
		frm.set_query("account", "payroll_accounts", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			const filters = { is_group: 0 };
			if (row.company) filters.company = row.company;
			return { filters: filters };
		});

		// Scheduled runs: same per-row company scoping, plus the account-shape filters
		// stock Payroll Entry applies, so a scheduled row can only hold values a manual
		// entry would have accepted.
		const scheduled_row_query = (extra) => (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			const filters = Object.assign({ is_group: 0 }, extra);
			if (row.company) filters.company = row.company;
			return { filters: filters };
		};

		frm.set_query("cost_center", "scheduled_payroll_runs", scheduled_row_query());
		frm.set_query(
			"payroll_payable_account",
			"scheduled_payroll_runs",
			scheduled_row_query({ root_type: "Liability" })
		);
		frm.set_query(
			"payment_account",
			"scheduled_payroll_runs",
			scheduled_row_query({ account_type: ["in", ["Bank", "Cash"]] })
		);

		frm.set_query("salary_structure", "scheduled_payroll_runs", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			const filters = { docstatus: 1, is_active: "Yes" };
			if (row.company) filters.company = row.company;
			return { filters: filters };
		});
	},

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


frappe.ui.form.on("Nepal Payroll Account", {
	company(frm, cdt, cdn) {
		// The account that was picked belongs to the previous company. Drop it rather
		// than leave a cross-company mapping that only fails later, during setup.
		const row = locals[cdt][cdn];
		if (row.account) frappe.model.set_value(cdt, cdn, "account", null);
	},
});

frappe.ui.form.on("Nepal Scheduled Payroll", {
	company(frm, cdt, cdn) {
		// Every other link on the row is company-scoped, so none of them survive a
		// company change. Clearing beats carrying a stale cross-company reference into
		// an unattended payroll run.
		const row = locals[cdt][cdn];
		for (const field of [
			"salary_structure",
			"cost_center",
			"payroll_payable_account",
			"payment_account",
		]) {
			if (row[field]) frappe.model.set_value(cdt, cdn, field, null);
		}
	},
});
})();
