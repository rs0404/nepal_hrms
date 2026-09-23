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

let nh_help_dismiss_bound = false;

function nh_help_html(text) {
	if (!text) return "";
	return String(__(text)).replace(/\n/g, "<br>");
}

function nh_hide_popovers() {
	$(".nh-field-help").popover("hide");
}

function nh_is_help_target(target) {
	return $(target).closest(".nh-field-help, .popover.nh-help-popover").length > 0;
}

function nh_ensure_dismiss_on_outside() {
	if (nh_help_dismiss_bound) return;
	nh_help_dismiss_bound = true;

	document.addEventListener(
		"pointerdown",
		(e) => {
			if (!nh_is_help_target(e.target)) nh_hide_popovers();
		},
		true
	);
	document.addEventListener(
		"keydown",
		(e) => {
			if (e.key === "Escape") nh_hide_popovers();
		},
		true
	);
}

function nh_bind_help_button($anchor, content) {
	if (!$anchor.length || !content) return;
	if ($anchor.find(".nh-field-help").length) return;

	nh_ensure_dismiss_on_outside();

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

	nh_ensure_dismiss_on_outside();
}

function nh_has_raven() {
	const flag = frappe.boot.nepal_hrms && frappe.boot.nepal_hrms.has_raven;
	if (flag === true || flag === 1) return true;
	if (flag === false || flag === 0) return false;
	return null;
}

function nh_toggle_notifications_tab(frm, show) {
	const df = frm.get_docfield("notification_tab");
	if (df) df.hidden = show ? 0 : 1;

	frm.set_df_property("notification_tab", "hidden", show ? 0 : 1);

	const field = frm.get_field("notification_tab");
	const tab = field && field.tab;
	if (!tab) return;

	tab.df.hidden = show ? 0 : 1;
	if (show) {
		tab.toggle(true);
	} else {
		tab.refresh();
	}
}

function nh_bind_input_link(input, doctype, filters, on_select) {
	if (!input || input._nh_link || typeof Awesomplete === "undefined") return;

	input._nh_link = true;
	input.setAttribute("autocomplete", "off");

	const awesomplete = new Awesomplete(input, {
		minChars: 0,
		maxItems: 20,
		autoFirst: true,
		filter() {
			return true;
		},
	});

	const fetch_options = (term) => {
		frappe.call({
			method: "frappe.desk.search.search_link",
			args: {
				doctype,
				txt: term || "",
				filters: filters || {},
			},
			callback(r) {
				awesomplete.list = (r.message || []).map((row) => row.value);
			},
		});
	};

	$(input).on("focus.nh_link input.nh_link", function () {
		fetch_options(this.value);
	});

	// Awesomplete writes the pick straight onto input.value. Frappe's control
	// only learns of a new value from a native change event, so without this the
	// model never saw the selection: the field looked filled, saved nothing, and
	// came back empty on reload. Typing the name in full always worked, because
	// blurring the field does fire change -- which is why this only bit on click.
	$(input).on("awesomplete-selectcomplete.nh_link", function () {
		input.dispatchEvent(new Event("change", { bubbles: true }));
		if (typeof on_select === "function") on_select(input.value);
	});
}

function nh_bind_data_link(frm, fieldname, doctype, filters) {
	try {
		const field = frm.get_field(fieldname);
		if (!field || !field.$input) return;
		nh_bind_input_link(field.$input.get(0), doctype, filters, (value) => {
			// Belt and braces: the change event above covers the standard control,
			// this covers any control that reads the model rather than the input.
			if (frm.doc[fieldname] !== value) frm.set_value(fieldname, value);
		});
	} catch (error) {
		console.warn("Nepal HRMS Raven picker", error);
	}
}

function nh_bind_event_channel_pickers(frm) {
	const grid = frm.fields_dict.raven_notifications && frm.fields_dict.raven_notifications.grid;
	if (!grid || !grid.wrapper) return;

	grid.wrapper.off("focus.nh_row_channel").on("focus.nh_row_channel", 'input[data-fieldname="channel"]', function () {
		nh_bind_input_link(this, "Raven Channel", { is_direct_message: 0 });
	});
}

function nh_seed_notification_rows(frm) {
	if (!frm.fields_dict.raven_notifications) return;

	frappe.call({
		method: "nepal_hrms.notifications.raven_sync.get_notification_event_catalog",
		callback(r) {
			const catalog = r.message || [];
			if (!catalog.length) return;

			const existing = new Set(
				(frm.doc.raven_notifications || []).map((row) => row.event_key).filter(Boolean)
			);
			let added = false;
			catalog.forEach((event) => {
				if (existing.has(event.key)) return;
				const row = frm.add_child("raven_notifications");
				row.event_key = event.key;
				row.event_label = event.label;
				row.enabled = 0;
				row.send_to_channel = 0;
				row.send_to_employee = 0;
				row.send_to_reports_to = 0;
				row.send_to_approver = 0;
				added = true;
			});
			if (added) {
				frm.refresh_field("raven_notifications");
			}

			(frm.doc.raven_notifications || []).forEach((row) => {
				if (row.event_key && !row.event_label) {
					const match = catalog.find((event) => event.key === row.event_key);
					if (match) {
						frappe.model.set_value(row.doctype, row.name, "event_label", match.label);
					}
				}
			});
		},
	});
}

function nh_apply_notifications_tab(frm, show) {
	nh_toggle_notifications_tab(frm, show);
	if (!show) return;

	nh_seed_notification_rows(frm);
	nh_bind_data_link(frm, "raven_bot", "Raven Bot");
	nh_bind_data_link(frm, "raven_channel", "Raven Channel", { is_direct_message: 0 });
	nh_bind_data_link(frm, "raven_workspace", "Raven Workspace");
	nh_bind_event_channel_pickers(frm);
}

function nh_setup_notifications_tab(frm) {
	const known = nh_has_raven();
	if (known === true) {
		nh_apply_notifications_tab(frm, true);
		return;
	}
	if (known === false) {
		nh_apply_notifications_tab(frm, false);
		return;
	}

	frappe.call({
		method: "nepal_hrms.notifications.raven_sync.get_notification_event_catalog",
		callback(r) {
			nh_apply_notifications_tab(frm, Boolean(r.message && r.message.length));
		},
		error() {
			nh_apply_notifications_tab(frm, false);
		},
	});
}

function nh_set_employee_id_field_options(frm) {
	const update_options = () => {
		if (!frm.fields_dict.salary_slip_employee_id_field) return;

		const current = frm.doc.salary_slip_employee_id_field || "name";
		const supported_types = new Set(["Data", "Link", "Dynamic Link", "Int"]);
		const options = ["name"];

		for (const field of frappe.get_meta("Employee").fields || []) {
			if (field.fieldname && supported_types.has(field.fieldtype)) {
				options.push(field.fieldname);
			}
		}
		if (!options.includes(current)) options.push(current);

		frm.set_df_property(
			"salary_slip_employee_id_field",
			"options",
			[...new Set(options)].join("\n")
		);
	};

	frappe.model.with_doctype("Employee", update_options).catch((error) => {
		console.warn("Unable to load Employee ID source fields", error);
	});
}

frappe.ui.form.on("Nepal HRMS Settings", {
	onload(frm) {
		frappe.require(NH_SETTINGS_CSS);
	},

	refresh(frm) {
		frappe.require(NH_SETTINGS_CSS, () => nh_attach_settings_help(frm));
		try {
			nh_setup_notifications_tab(frm);
		} catch (error) {
			console.warn("Nepal HRMS notifications tab", error);
		}
	},

	onload_post_render(frm) {
		nh_set_employee_id_field_options(frm);
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

		frm.set_query("salary_slip_additional_earning_components", () => ({
			filters: { type: "Earning", disabled: 0 },
		}));
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
