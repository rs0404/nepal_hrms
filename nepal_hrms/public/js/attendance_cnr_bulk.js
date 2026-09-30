// Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.provide("nepal_hrms.attendance_cnr_bulk");

nepal_hrms.attendance_cnr_bulk.FIELD_LABELS = {
	status: __("Status"),
	half_day_status: __("Half Day Status"),
	leave_type: __("Leave Type"),
	late_entry: __("Late Entry"),
	early_exit: __("Early Exit"),
	custom_late_mins: __("Late Mins"),
	custom_early_mins: __("Early Mins"),
	custom_cnr_unexcused_late: __("Unexcused Late"),
	custom_cnr_unexcused_early: __("Unexcused Early"),
	custom_cnr_late_in_pool: __("Late In Pool"),
	custom_cnr_early_in_pool: __("Early In Pool"),
	custom_cnr_month_late_pool_count: __("Month Late Pool"),
	custom_cnr_month_early_pool_count: __("Month Early Pool"),
};

nepal_hrms.attendance_cnr_bulk.TRACKED_FIELDS = Object.keys(
	nepal_hrms.attendance_cnr_bulk.FIELD_LABELS
);

nepal_hrms.attendance_cnr_bulk.TEXT_FIELDS = ["status", "half_day_status", "leave_type"];

nepal_hrms.attendance_cnr_bulk.REASON_LABELS = {
	holiday: __("Holiday"),
	weekly_off: __("Weekly Off"),
	sandwich_leave: __("Sandwich → On Leave"),
	sandwich_absent: __("Sandwich → Absent"),
	leave_on_holiday: __("Leave on holiday"),
	worked_holiday: __("Worked on holiday (Comp Off via request)"),
	working_day: __("Working day (was holiday)"),
	working_day_absent: __("Working day absent (was holiday)"),
	cnr: __("Late / early"),
};

nepal_hrms.attendance_cnr_bulk._display_val = function (field, value) {
	if (nepal_hrms.attendance_cnr_bulk.TEXT_FIELDS.includes(field)) {
		return value == null || value === "" ? "—" : String(value);
	}
	if (value == null || value === "") {
		return "0";
	}
	return String(cint(value));
};

nepal_hrms.attendance_cnr_bulk._diff_rows = function (before, after) {
	before = before || {};
	after = after || {};
	const rows = [];
	nepal_hrms.attendance_cnr_bulk.TRACKED_FIELDS.forEach((field) => {
		const bv = before[field];
		const av = after[field];
		let changed = false;
		if (nepal_hrms.attendance_cnr_bulk.TEXT_FIELDS.includes(field)) {
			changed = (bv || null) !== (av || null);
		} else {
			changed = cint(bv) !== cint(av);
		}
		if (!changed) return;
		rows.push({
			field,
			label: nepal_hrms.attendance_cnr_bulk.FIELD_LABELS[field] || field,
			before: nepal_hrms.attendance_cnr_bulk._display_val(field, bv),
			after: nepal_hrms.attendance_cnr_bulk._display_val(field, av),
		});
	});
	return rows;
};

nepal_hrms.attendance_cnr_bulk._diff_table_html = function (row, { compact = false } = {}) {
	let diffs = nepal_hrms.attendance_cnr_bulk._diff_rows(row.before, row.after);
	if (!diffs.length && (row.changes || []).length) {
		// Fallback: parse "Label: before → after" strings from API
		diffs = (row.changes || [])
			.map((text) => {
				const m = String(text).match(/^(.+?):\s*(.*?)\s*→\s*(.*)$/);
				if (!m) return null;
				return { label: m[1], before: m[2] || "—", after: m[3] || "—" };
			})
			.filter(Boolean);
	}
	if (!diffs.length) {
		return `<div class="text-muted">${frappe.utils.escape_html(row.summary || __("No field changes"))}</div>`;
	}

	const pad = compact ? "4px 6px" : "6px 8px";
	const body = diffs
		.map(
			(d) => `<tr>
				<td style="padding:${pad};vertical-align:top;color:var(--text-muted);white-space:nowrap;">
					${frappe.utils.escape_html(d.label)}
				</td>
				<td style="padding:${pad};vertical-align:top;">
					<span style="display:inline-block;padding:1px 6px;border-radius:4px;background:#fff3cd;border:1px solid #ffe69c;">
						${frappe.utils.escape_html(d.before)}
					</span>
				</td>
				<td style="padding:${pad};vertical-align:top;text-align:center;color:var(--text-muted);">→</td>
				<td style="padding:${pad};vertical-align:top;">
					<span style="display:inline-block;padding:1px 6px;border-radius:4px;background:#d1e7dd;border:1px solid #a3cfbb;">
						${frappe.utils.escape_html(d.after)}
					</span>
				</td>
			</tr>`
		)
		.join("");

	return `<table class="table" style="margin:0;font-size:12px;width:100%;">
		<thead>
			<tr style="background:var(--bg-color);">
				<th style="padding:${pad};width:34%;">${__("Field")}</th>
				<th style="padding:${pad};width:28%;">${__("Now (before)")}</th>
				<th style="padding:${pad};width:8%;"></th>
				<th style="padding:${pad};width:30%;">${__("After recalculate")}</th>
			</tr>
		</thead>
		<tbody>${body}</tbody>
	</table>`;
};

nepal_hrms.attendance_cnr_bulk._checkins_html = function (row) {
	const checkins = row.checkins || [];
	if (checkins.length) {
		const lines = checkins
			.map((c) => {
				const typ = frappe.utils.escape_html(c.log_type || "—");
				const t = frappe.utils.escape_html(c.time_display || "—");
				return `<div style="font-variant-numeric:tabular-nums;"><span style="display:inline-block;min-width:28px;font-weight:600;">${typ}</span> ${t}</div>`;
			})
			.join("");
		return `<div class="text-muted" style="font-size:11px;margin-top:6px;line-height:1.45;">${lines}</div>`;
	}
	const blank = (v) => !v || v === "—" || v === "-";
	const inn = row.in_time_display;
	const out = row.out_time_display;
	if (!blank(inn) || !blank(out)) {
		return `<div class="text-muted" style="font-size:11px;margin-top:6px;">
			${__("In")}: ${frappe.utils.escape_html(blank(inn) ? "—" : inn)}
			· ${__("Out")}: ${frappe.utils.escape_html(blank(out) ? "—" : out)}
		</div>`;
	}
	return `<div class="text-muted" style="font-size:11px;margin-top:6px;">${__("No check-ins")}</div>`;
};

nepal_hrms.attendance_cnr_bulk._app_status_style = function (status) {
	const s = (status || "").toLowerCase();
	if (s === "approved") {
		return "background:#d1e7dd;border:1px solid #a3cfbb;color:#0f5132;";
	}
	if (s === "rejected" || s === "cancelled") {
		return "background:#f8d7da;border:1px solid #f1aeb5;color:#842029;";
	}
	// Draft / Open / other = not approved yet
	return "background:#fff3cd;border:1px solid #ffe69c;color:#664d03;";
};

nepal_hrms.attendance_cnr_bulk._applications_html = function (row) {
	const apps = row.applications || [];
	if (!apps.length) {
		return `<div class="text-muted" style="font-size:11px;margin-top:4px;">${__("No applications")}</div>`;
	}
	const lines = apps
		.map((a) => {
			const label = frappe.utils.escape_html(a.short || a.doctype || "App");
			const status = frappe.utils.escape_html(a.status || "Draft");
			const work = a.type_of_work
				? ` <span class="text-muted">(${frappe.utils.escape_html(a.type_of_work)})</span>`
				: "";
			const routeDoctype = (a.doctype || "")
				.toLowerCase()
				.replace(/ /g, "-");
			const href = a.doctype && a.name
				? `/app/${routeDoctype}/${encodeURIComponent(a.name)}`
				: null;
			const nameLink = href
				? `<a href="${href}" target="_blank" style="margin-left:4px;">${frappe.utils.escape_html(a.name)}</a>`
				: "";
			const badge = `<span style="display:inline-block;padding:0 6px;border-radius:4px;font-size:10px;${nepal_hrms.attendance_cnr_bulk._app_status_style(
				a.status
			)}">${status}</span>`;
			return `<div style="margin-top:2px;"><span style="font-weight:600;min-width:32px;display:inline-block;">${label}</span> ${badge}${work}${nameLink}</div>`;
		})
		.join("");
	return `<div style="font-size:11px;margin-top:6px;line-height:1.5;">${lines}</div>`;
};

nepal_hrms.attendance_cnr_bulk._date_meta_html = function (row) {
	let reasonHtml = "";
	if (row.reason) {
		const label =
			nepal_hrms.attendance_cnr_bulk.REASON_LABELS[row.reason] || row.reason;
		reasonHtml = `<div style="font-size:11px;margin-top:4px;color:var(--text-color);">
			<span style="display:inline-block;padding:1px 6px;border-radius:4px;background:var(--bg-color);border:1px solid var(--border-color);">
				${frappe.utils.escape_html(label)}
			</span>
		</div>`;
	}
	return (
		reasonHtml +
		nepal_hrms.attendance_cnr_bulk._checkins_html(row) +
		nepal_hrms.attendance_cnr_bulk._applications_html(row)
	);
};

nepal_hrms.attendance_cnr_bulk._stale_banner_html = function (preview) {
	if (!preview || !preview.stale_period) return "";
	return `<div style="margin-bottom:10px;padding:10px 12px;border-radius:8px;background:#fff3cd;border:1px solid #ffe69c;color:#664d03;">
		<b>${__("Warning")}:</b>
		${__(
			"You are recalculating attendance older than 2 months. Please confirm this is intentional."
		)}
	</div>`;
};

nepal_hrms.attendance_cnr_bulk._warn_stale_period = function (preview) {
	if (!preview || !preview.stale_period) return;
	frappe.msgprint({
		title: __("Older than 2 months"),
		indicator: "orange",
		message: __(
			"The selected period starts more than 2 months ago. Recalculating old attendance can affect historical records and payroll. Proceed carefully."
		),
	});
};

nepal_hrms.attendance_cnr_bulk._date_cell = function (row) {
	const bs = row.attendance_date_bs_pretty || row.attendance_date_bs || "";
	const ad = row.attendance_date
		? frappe.datetime.str_to_user(row.attendance_date)
		: "";
	return `<td style="padding:8px;white-space:nowrap;vertical-align:top;width:200px;">
		<a href="/app/attendance/${encodeURIComponent(row.name)}" target="_blank" style="font-weight:600;">
			${frappe.utils.escape_html(bs)}
		</a>
		<div class="text-muted" style="font-size:11px;margin-top:2px;">${frappe.utils.escape_html(ad)}</div>
		${nepal_hrms.attendance_cnr_bulk._date_meta_html(row)}
	</td>`;
};

nepal_hrms.attendance_cnr_bulk._changes_cell = function (row) {
	return `<td style="padding:4px 8px;vertical-align:top;">
		${nepal_hrms.attendance_cnr_bulk._diff_table_html(row, { compact: true })}
	</td>`;
};

nepal_hrms.attendance_cnr_bulk._who_label = function (preview) {
	if (preview.employee_count > 1) {
		return __("{0} employees", [preview.employee_count]);
	}
	return preview.employee_name || preview.employee || __("selected employees");
};

nepal_hrms.attendance_cnr_bulk._period_label = function (preview) {
	const from_bs = preview.from_date_bs_pretty || frappe.datetime.str_to_user(preview.from_date);
	const to_bs = preview.to_date_bs_pretty || frappe.datetime.str_to_user(preview.to_date);
	return `${from_bs} → ${to_bs}`;
};

nepal_hrms.attendance_cnr_bulk._build_preview_args = function (values) {
	const mode = values.selection_mode || "employees";
	const args = {
		selection_mode: mode,
		from_date: values.from_date,
		to_date: values.to_date,
	};
	if (mode === "department") {
		args.department = values.department;
	} else if (mode === "employees") {
		let employees = values.employees || [];
		if (typeof employees === "string") {
			employees = employees
				.split(",")
				.map((s) => s.trim())
				.filter(Boolean);
		}
		if ((!employees || !employees.length) && values.employee) {
			employees = [values.employee];
		}
		args.employees = employees;
	}
	return args;
};

nepal_hrms.attendance_cnr_bulk._toggle_selection_fields = function (dialog) {
	const mode = dialog.get_value("selection_mode") || "employees";
	dialog.set_df_property("employees", "hidden", mode !== "employees" ? 1 : 0);
	dialog.set_df_property("employees", "reqd", mode === "employees" ? 1 : 0);
	dialog.set_df_property("department", "hidden", mode !== "department" ? 1 : 0);
	dialog.set_df_property("department", "reqd", mode === "department" ? 1 : 0);

	const hint = dialog.fields_dict.selection_hint;
	if (!hint) return;
	let msg = "";
	if (mode === "all_active") {
		msg = __("All Active employees will be included (max 200).");
	} else if (mode === "department") {
		msg = __("All Active employees in the selected department will be included.");
	} else {
		msg = __("Pick one or more employees to recalculate.");
	}
	hint.$wrapper.html(`<div class="text-muted" style="margin-top:-6px;margin-bottom:8px;">${msg}</div>`);
};

nepal_hrms.attendance_cnr_bulk._bind_date_presets = function (dialog, presets) {
	const wrap = dialog.fields_dict.date_presets.$wrapper;
	const monthLabel = (presets.bs_month && presets.bs_month.label) || __("This Month");
	wrap.html(`
		<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:4px;">
			<button type="button" class="btn btn-default btn-xs cnr-preset-today">${__("Today")}</button>
			<button type="button" class="btn btn-default btn-xs cnr-preset-month">${__(
				"This Month"
			)} <span class="text-muted">(${frappe.utils.escape_html(monthLabel)})</span></button>
		</div>
		<div class="text-muted" style="font-size:11px;margin-bottom:8px;">
			${__(
				"This Month uses the current Nepali (BS) month — 1st day to last day."
			)}
		</div>
	`);

	wrap.find(".cnr-preset-today").on("click", () => {
		const t = presets.today;
		if (!t) return;
		dialog.set_value("from_date", t.ad);
		dialog.set_value("to_date", t.ad);
		frappe.show_alert({
			message: __("Set to today ({0})", [t.bs_pretty || t.bs || t.ad]),
			indicator: "blue",
		});
	});

	wrap.find(".cnr-preset-month").on("click", () => {
		const m = presets.bs_month;
		if (!m) return;
		dialog.set_value("from_date", m.from_date);
		dialog.set_value("to_date", m.to_date);
		frappe.show_alert({
			message: __("Set to {0} ({1} → {2})", [
				m.label,
				m.from_date_bs_pretty || m.from_date_bs,
				m.to_date_bs_pretty || m.to_date_bs,
			]),
			indicator: "blue",
		});
	});
};

nepal_hrms.attendance_cnr_bulk.open_dialog = function (defaults) {
	defaults = defaults || {};

	let defaultEmployees = defaults.employees || [];
	if ((!defaultEmployees || !defaultEmployees.length) && defaults.employee) {
		defaultEmployees = [defaults.employee];
	}
	if (typeof defaultEmployees === "string") {
		defaultEmployees = [defaultEmployees];
	}

	const d = new frappe.ui.Dialog({
		title: __("Recheck Attendance for Period"),
		size: "large",
		fields: [
			{
				fieldname: "recheck_intro",
				fieldtype: "HTML",
				options: `<p class="text-muted small" style="margin-bottom:4px;">${__(
					"Re-applies late entry, early exit, holiday, sandwich and half-day leave rules to the chosen days. Shows every change before saving."
				)}</p>`,
			},
			{
				fieldname: "selection_mode",
				label: __("Select Employees"),
				fieldtype: "Select",
				options: "employees\nall_active\ndepartment",
				default: defaults.selection_mode || "employees",
				reqd: 1,
				onchange() {
					nepal_hrms.attendance_cnr_bulk._toggle_selection_fields(d);
				},
			},
			{
				fieldname: "selection_hint",
				fieldtype: "HTML",
			},
			{
				fieldname: "employees",
				label: __("Employees"),
				fieldtype: "MultiSelectList",
				options: "Employee",
				get_data(txt) {
					return frappe.db.get_link_options("Employee", txt, {
						status: "Active",
					});
				},
				default: defaultEmployees,
			},
			{
				fieldname: "department",
				label: __("Department"),
				fieldtype: "Link",
				options: "Department",
				default: defaults.department || "",
			},
			{
				fieldname: "date_presets",
				fieldtype: "HTML",
			},
			{
				fieldname: "from_date",
				label: __("From Date"),
				fieldtype: "Date",
				reqd: 1,
				default: defaults.from_date || frappe.datetime.month_start(),
			},
			{
				fieldname: "to_date",
				label: __("To Date"),
				fieldtype: "Date",
				reqd: 1,
				default: defaults.to_date || frappe.datetime.month_end(),
			},
			{
				fieldname: "preview_html",
				fieldtype: "HTML",
			},
		],
		primary_action_label: __("Preview Changes"),
		primary_action(values) {
			nepal_hrms.attendance_cnr_bulk.run_preview(d, values);
		},
	});

	d.show();

	// Friendly Select labels (values remain mode keys)
	const $sel = d.fields_dict.selection_mode.$input;
	$sel.empty();
	[
		{ value: "employees", label: __("Selected Employees") },
		{ value: "all_active", label: __("All Active Employees") },
		{ value: "department", label: __("By Department") },
	].forEach((opt) => {
		$sel.append(`<option value="${frappe.utils.escape_html(opt.value)}">${opt.label}</option>`);
	});
	$sel.val(defaults.selection_mode || "employees").trigger("change");

	nepal_hrms.attendance_cnr_bulk._toggle_selection_fields(d);

	if (defaultEmployees.length && d.fields_dict.employees) {
		const ctrl = d.fields_dict.employees;
		frappe.db
			.get_list("Employee", {
				filters: { name: ["in", defaultEmployees] },
				fields: ["name", "employee_name"],
				limit: defaultEmployees.length,
			})
			.then((rows) => {
				ctrl._options = (rows || []).map((row) => ({
					value: row.name,
					label: row.employee_name || row.name,
					description: row.name,
				}));
				if (ctrl.set_value) {
					ctrl.set_value(defaultEmployees);
				}
			});
	}

	frappe.call({
		method: "nepal_hrms.api.attendance_recalc.get_bs_date_presets",
		callback(r) {
			if (!r.message) return;
			nepal_hrms.attendance_cnr_bulk._bind_date_presets(d, r.message);
			// If no explicit from/to defaults, prefer current BS month
			if (!defaults.from_date && !defaults.to_date && r.message.bs_month) {
				d.set_value("from_date", r.message.bs_month.from_date);
				d.set_value("to_date", r.message.bs_month.to_date);
			}
		},
	});

	return d;
};

nepal_hrms.attendance_cnr_bulk._render_preview_table = function (preview) {
	const multi = (preview.employee_count || 1) > 1 || (preview.by_employee || []).length > 1;
	const sections = [];

	const renderRows = (changes) =>
		(changes || [])
			.map(
				(c) =>
					`<tr>${nepal_hrms.attendance_cnr_bulk._date_cell(
						c
					)}${nepal_hrms.attendance_cnr_bulk._changes_cell(c)}</tr>`
			)
			.join("");

	if (multi && preview.by_employee && preview.by_employee.length) {
		preview.by_employee.forEach((emp) => {
			if (!emp.change_count) return;
			sections.push(`
				<div style="margin:12px 0 6px;font-weight:600;">
					${frappe.utils.escape_html(emp.employee_name || emp.employee)}
					<span class="text-muted" style="font-weight:400;"> · ${__(
						"{0} change(s)",
						[emp.change_count]
					)}</span>
				</div>
				<div style="max-height:220px;overflow:auto;border:1px solid var(--border-color);border-radius:8px;margin-bottom:8px;">
					<table class="table" style="margin:0;font-size:12px;">
						<thead>
							<tr style="background:var(--bg-color);">
								<th style="padding:8px;width:150px;">${__("Nepali Date")}</th>
								<th style="padding:8px;">${__("Changes (Now → After)")}</th>
							</tr>
						</thead>
						<tbody>${renderRows(emp.changes)}</tbody>
					</table>
				</div>
			`);
		});
	} else {
		sections.push(`
			<div style="max-height:320px;overflow:auto;border:1px solid var(--border-color);border-radius:8px;">
				<table class="table" style="margin:0;font-size:12px;">
					<thead>
						<tr style="background:var(--bg-color);">
							<th style="padding:8px;width:150px;">${__("Nepali Date")}</th>
							<th style="padding:8px;">${__("Changes (Now → After)")}</th>
						</tr>
					</thead>
					<tbody>${renderRows(preview.changes)}</tbody>
				</table>
			</div>
		`);
	}

	return `
		${nepal_hrms.attendance_cnr_bulk._stale_banner_html(preview)}
		<div style="margin-bottom:10px;padding:10px 12px;border-radius:8px;background:var(--bg-light-gray);">
			<div style="font-weight:600;margin-bottom:4px;">
				${__("{0} record(s) will change", [preview.change_count])}
			</div>
			<div class="text-muted" style="font-size:12px;">
				${frappe.utils.escape_html(nepal_hrms.attendance_cnr_bulk._who_label(preview))}
				· ${frappe.utils.escape_html(nepal_hrms.attendance_cnr_bulk._period_label(preview))}
			</div>
			<div class="text-muted" style="font-size:11px;margin-top:4px;">
				${__("{0} unchanged · {1} protected/skipped · nothing is saved until you confirm", [
					preview.unchanged_count,
					preview.skipped_protected_count,
				])}
			</div>
		</div>
		${sections.join("")}
	`;
};

nepal_hrms.attendance_cnr_bulk.run_preview = function (dialog, values) {
	const args = nepal_hrms.attendance_cnr_bulk._build_preview_args(values);
	if (args.selection_mode === "employees" && (!args.employees || !args.employees.length)) {
		frappe.msgprint(__("Select at least one employee"));
		return;
	}
	if (args.selection_mode === "department" && !args.department) {
		frappe.msgprint(__("Select a department"));
		return;
	}

	frappe.call({
		method: "nepal_hrms.api.attendance_recalc.preview_recalculate_attendance_period",
		args: args,
		freeze: true,
		freeze_message: __("Checking attendance..."),
		callback(r) {
			if (!r.message) return;
			const preview = r.message;
			const wrap = dialog.fields_dict.preview_html.$wrapper;
			wrap.empty();

			nepal_hrms.attendance_cnr_bulk._warn_stale_period(preview);

			if (!preview.change_count) {
				frappe.msgprint({
					title: __("No Changes"),
					indicator: "blue",
					message: __(
						"Nothing to change for {0} ({1}). ({2} already correct, {3} skipped)",
						[
							nepal_hrms.attendance_cnr_bulk._who_label(preview),
							nepal_hrms.attendance_cnr_bulk._period_label(preview),
							preview.unchanged_count,
							preview.skipped_protected_count,
						]
					),
				});
				return;
			}

			wrap.html(nepal_hrms.attendance_cnr_bulk._render_preview_table(preview));
			nepal_hrms.attendance_cnr_bulk.confirm_apply(dialog, args, preview);
		},
	});
};

nepal_hrms.attendance_cnr_bulk.confirm_apply = function (dialog, args, preview) {
	const sample = (preview.changes || []).slice(0, 12);
	const more =
		preview.change_count > sample.length
			? `<div class="text-muted" style="margin-top:8px;">${__(
					"…and {0} more (same detail is in the preview table above)",
					[preview.change_count - sample.length]
			  )}</div>`
			: "";

	const lines = sample
		.map((c) => {
			const who =
				preview.employee_count > 1
					? `<div class="text-muted" style="font-size:11px;margin-bottom:2px;">${frappe.utils.escape_html(
							c.employee_name || c.employee || ""
					  )}</div>`
					: "";
			const date = frappe.utils.escape_html(
				c.attendance_date_bs_pretty || c.attendance_date_bs || c.attendance_date
			);
			return `<div style="margin:10px 0;padding:8px;border:1px solid var(--border-color);border-radius:8px;">
				${who}
				<div style="font-weight:600;">${date}</div>
				${nepal_hrms.attendance_cnr_bulk._date_meta_html(c)}
				<div style="margin-top:8px;">
					${nepal_hrms.attendance_cnr_bulk._diff_table_html(c, { compact: true })}
				</div>
			</div>`;
		})
		.join("");

	frappe.confirm(
		`<div style="max-height:460px;overflow:auto;">
			${nepal_hrms.attendance_cnr_bulk._stale_banner_html(preview)}
			<p style="font-size:14px;margin-bottom:8px;"><b>${__("Recheck these days?")}</b></p>
			<p>${__(
				"This will update {0} Attendance record(s) for {1} ({2}) and add timeline comments. This cannot be undone automatically.",
				[
					preview.change_count,
					frappe.utils.escape_html(nepal_hrms.attendance_cnr_bulk._who_label(preview)),
					frappe.utils.escape_html(nepal_hrms.attendance_cnr_bulk._period_label(preview)),
				]
			)}</p>
			<p class="text-muted" style="font-size:12px;margin-bottom:8px;">
				${__("Yellow = current value (Now). Green = value after recalculate.")}
			</p>
			<hr>
			${lines}
			${more}
		</div>`,
		() => {
			frappe.call({
				method: "nepal_hrms.api.attendance_recalc.apply_recalculate_attendance_period",
				args: args,
				freeze: true,
				freeze_message: __("Updating attendance..."),
				callback(r) {
					if (!r.message || !r.message.ok) return;
					const res = r.message;
					dialog.hide();
					frappe.show_alert({
						message: __(
							"Updated {0} Attendance record(s). {1} unchanged, {2} skipped.",
							[res.updated, res.unchanged, res.skipped]
						),
						indicator: "green",
					});
					if (cur_list && cur_list.doctype === "Attendance") {
						cur_list.refresh();
					}
					if (
						frappe.query_report &&
						frappe.query_report.report_name === "Monthly Attendance Sheet BS"
					) {
						frappe.query_report.refresh();
					}
				},
			});
		}
	);
};
