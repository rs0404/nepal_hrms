function sheetBsEnsureCompactFilters() {
	if (document.getElementById("sheet-bs-compact-filters")) return;
	const style = document.createElement("style");
	style.id = "sheet-bs-compact-filters";
	// Scope to this report only; do not set flex on .form-group (breaks Frappe filter grid).
	style.textContent = `
		body.sheet-bs-report-page .standard-filter-section {
			padding-top: 4px !important;
			padding-bottom: 4px !important;
		}
		body.sheet-bs-report-page .standard-filter-section .form-group {
			margin-bottom: 4px !important;
		}
		body.sheet-bs-report-page .form-group[data-fieldname="custom_start_day"] .control-input-wrapper,
		body.sheet-bs-report-page .form-group[data-fieldname="custom_end_day"] .control-input-wrapper {
			max-width: 5.5rem;
		}
		body.sheet-bs-report-page .form-group[data-fieldname="custom_start_day"] input,
		body.sheet-bs-report-page .form-group[data-fieldname="custom_end_day"] input {
			max-width: 5.5rem;
		}
		body.sheet-bs-report-page .form-group[data-fieldname="start_month_type"] .control-input-wrapper,
		body.sheet-bs-report-page .form-group[data-fieldname="end_month_type"] .control-input-wrapper {
			max-width: 11rem;
		}
	`;
	document.head.appendChild(style);
}

function sheetBsMarkReportPage() {
	document.body.classList.add("sheet-bs-report-page");
}

function sheetBsTimeBarLegendHtml(leaveLegendRows) {
	const timeBar = `
		<div class="attendance-bar-legend-section">
			<div class="attendance-bar-legend-title">${__("Time bar")}</div>
			<div class="attendance-bar-legend-grid">
				<span class="legend-item"><span class="legend-swatch" style="background:#22c55e;"></span>${__("Office")}</span>
				<span class="legend-item"><span class="legend-swatch" style="background:#3b82f6;"></span>${__("OOO Work")}</span>
				<span class="legend-item"><span class="legend-swatch" style="background:#0d9488;"></span>${__("WFH")}</span>
				<span class="legend-item"><span class="legend-swatch" style="background:#a855f7;"></span>${__("Half Day")}</span>
				<span class="legend-item"><span class="legend-swatch" style="background:#f97316;"></span>${__("Extra")}</span>
				<span class="legend-item"><span class="legend-swatch" style="background:#ef4444;"></span>${__("Gap")}</span>
				<span class="legend-item"><span class="legend-swatch" style="background:#94a3b8;"></span>${__("Holiday / WO")}</span>
			</div>
		</div>`;
	const badges = `
		<div class="attendance-bar-legend-section">
			<div class="attendance-bar-legend-title">${__("Late / Early badges")}</div>
			<div class="attendance-bar-legend-grid">
				<span class="legend-item"><span style="background:#fbbf24;color:#78350f;font-weight:700;font-size:10px;padding:1px 6px;border-radius:999px;">Lg</span> ${__("Late within grace")}</span>
				<span class="legend-item"><span style="background:#ef4444;color:#fff;font-weight:700;font-size:10px;padding:1px 6px;border-radius:999px;">L!</span> ${__("Late — no application")}</span>
				<span class="legend-item"><span style="background:#16a34a;color:#fff;font-weight:700;font-size:10px;padding:1px 6px;border-radius:999px;">L✓</span> ${__("Late — approved")}</span>
				<span class="legend-item"><span style="background:#fbbf24;color:#78350f;font-weight:700;font-size:10px;padding:1px 6px;border-radius:999px;">Eg</span> ${__("Early within grace")}</span>
				<span class="legend-item"><span style="background:#ef4444;color:#fff;font-weight:700;font-size:10px;padding:1px 6px;border-radius:999px;">E!</span> ${__("Early — no application")}</span>
				<span class="legend-item"><span style="background:#16a34a;color:#fff;font-weight:700;font-size:10px;padding:1px 6px;border-radius:999px;">E✓</span> ${__("Early — approved")}</span>
				<span class="legend-item"><span style="background:#3b82f6;color:#fff;font-weight:700;font-size:10px;padding:1px 6px;border-radius:999px;">O</span> ${__("OOO application")}</span>
			</div>
		</div>`;
	const leaveRows = (leaveLegendRows || [])
		.map(
			(row) =>
				`<div class="leave-acronym-list-row">
					<span class="leave-acronym-pill">${frappe.utils.escape_html(row.acronym)}</span>
					<span class="leave-acronym-list-label">${frappe.utils.escape_html(row.leave_type)}</span>
				</div>`
		)
		.join("");
	const leaves = `
		<div class="attendance-bar-legend-section">
			<div class="attendance-bar-legend-title">${__("Leave types (pill acronyms)")}</div>
			<div class="attendance-bar-legend-list leave-acronym-list">${leaveRows || `<div class="text-muted">${__("No leave types")}</div>`}</div>
		</div>`;
	return `<div class="attendance-bar-legend attendance-bar-legend-panel">${timeBar}${badges}${leaves}</div>`;
}

function sheetBsOpenLegendDialog() {
	frappe.call({
		method: "nepal_hrms.custom_code.leave_type_acronym.get_attendance_sheet_leave_legend",
		callback(r) {
			const d = new frappe.ui.Dialog({
				title: __("Time Bar & Leave Legend"),
				size: "large",
				fields: [{ fieldname: "legend_html", fieldtype: "HTML" }],
			});
			d.fields_dict.legend_html.$wrapper.html(sheetBsTimeBarLegendHtml(r.message || []));
			d.show();
		},
	});
}

frappe.query_reports["Monthly Attendance Sheet BS"] = {
	"onload": function (report) {
		sheetBsEnsureCompactFilters();
		sheetBsMarkReportPage();
		setTimeout(sheetBsMarkReportPage, 400);
		// Recreate datatable on each refresh so inlineFilters: false and HTML formatters re-run.
		const refreshReport = report.refresh.bind(report);
		report.refresh = function (have_filters_changed) {
			if (report.datatable && typeof report.datatable.destroy === "function") {
				try {
					report.datatable.destroy();
				} catch (e) {
					console.warn("Monthly Attendance Sheet BS: datatable destroy", e);
				}
				report.datatable = null;
			}
			return refreshReport(have_filters_changed);
		};
		report.page.add_inner_button(__("Time Bar Legend"), () => sheetBsOpenLegendDialog());

		frappe.call({
			method: "nepal_hrms.api.attendance.get_calendar_data",
			callback: function (r) {
				if (r.message && r.message.current_bs_year) {
					frappe.query_report.set_filter_value("bs_year", String(r.message.current_bs_year));
					frappe.query_report.set_filter_value("bs_month", String(r.message.current_bs_month));

					let year = r.message.current_bs_year;
					let month = r.message.current_bs_month;
					let last_day = 30;
					if ([1, 2, 3, 4, 5, 6].includes(month)) last_day = 31;

					let from_date = `${year}-${String(month).padStart(2, '0')}-01`;
					let to_date = `${year}-${String(month).padStart(2, '0')}-${last_day}`;

					frappe.query_report.set_filter_value("from_bs_date", from_date);
					frappe.query_report.set_filter_value("to_bs_date", to_date);
				}
			}
		});

		report.page.add_inner_button(__("Recalculate C&R…"), () => {
			const filters = {
				filter_based_on: frappe.query_report.get_filter_value("filter_based_on"),
				bs_year: frappe.query_report.get_filter_value("bs_year"),
				bs_month: frappe.query_report.get_filter_value("bs_month"),
				use_custom_period: frappe.query_report.get_filter_value("use_custom_period"),
				custom_start_day: frappe.query_report.get_filter_value("custom_start_day"),
				start_month_type: frappe.query_report.get_filter_value("start_month_type"),
				custom_end_day: frappe.query_report.get_filter_value("custom_end_day"),
				end_month_type: frappe.query_report.get_filter_value("end_month_type"),
				from_bs_date: frappe.query_report.get_filter_value("from_bs_date"),
				to_bs_date: frappe.query_report.get_filter_value("to_bs_date"),
				employee: frappe.query_report.get_filter_value("employee"),
			};
			frappe.call({
				method: "nepal_hrms.api.attendance_recalc.resolve_monthly_sheet_bs_period",
				args: { filters: filters },
				freeze: true,
				callback(r) {
					const defaults = r.message || {};
					if (!defaults.employee) {
						defaults.employee = filters.employee || "";
					}
					if (!defaults.employees || !defaults.employees.length) {
						defaults.employees = defaults.employee ? [defaults.employee] : [];
					}
					nepal_hrms.attendance_cnr_bulk.open_dialog(defaults);
				},
			});
		});

		report.page.add_inner_button(__("Download Spreadsheet…"), () => {
			const d = new frappe.ui.Dialog({
				title: __("Download Attendance Sheet"),
				fields: [
					{
						fieldname: "export_mode",
						label: __("Data Format"),
						fieldtype: "Select",
						options: [
							{
								value: "daily",
								label: __(
									"Daily columns — Status, Check In, Check Out, Worked Hrs (no JSON)"
								),
							},
							{
								value: "full",
								label: __(
									"Full data — daily columns plus logs, late/early mins, leave & apps"
								),
							},
						],
						default: "daily",
						reqd: 1,
					},
					{
						fieldname: "file_format",
						label: __("File Type"),
						fieldtype: "Select",
						options: "Excel\nCSV",
						default: "Excel",
						reqd: 1,
					},
				],
				primary_action_label: __("Download"),
				primary_action(values) {
					const filters = report.get_filter_values(true);
					open_url_post(frappe.request.url, {
						cmd: "nepal_hrms.nepal_hrms.report.monthly_attendance_sheet_bs.download_attendance_sheet_bs.download_monthly_attendance_sheet_bs",
						filters: JSON.stringify(filters),
						export_mode: values.export_mode,
						file_format: values.file_format,
					});
					d.hide();
				},
			});
			d.show();
		});
	},
	filters: [
		{
			fieldname: "filter_based_on",
			label: __("Filter Based On"),
			fieldtype: "Select",
			options: ["BS Month", "BS Date Range"],
			default: "BS Month",
			reqd: 1,
			on_change: function () {
				let val = frappe.query_report.get_filter_value("filter_based_on");
				frappe.query_report.toggle_filter_display("bs_year", val !== "BS Month");
				frappe.query_report.toggle_filter_display("bs_month", val !== "BS Month");
				frappe.query_report.toggle_filter_display("use_custom_period", val !== "BS Month");
				frappe.query_report.toggle_filter_display("from_bs_date", val !== "BS Date Range");
				frappe.query_report.toggle_filter_display("to_bs_date", val !== "BS Date Range");

				let show_custom = val === "BS Month" && frappe.query_report.get_filter_value("use_custom_period");
				frappe.query_report.toggle_filter_display("custom_start_day", !show_custom);
				frappe.query_report.toggle_filter_display("start_month_type", !show_custom);
				frappe.query_report.toggle_filter_display("custom_end_day", !show_custom);
				frappe.query_report.toggle_filter_display("end_month_type", !show_custom);
			}
		},
		{
			fieldname: "bs_year",
			label: __("BS Year"),
			fieldtype: "Select",
			options: Array.from({ length: 100 }, (_, i) => (2000 + i).toString()),
			default: "2081",
		},
		{
			fieldname: "bs_month",
			label: __("BS Month"),
			fieldtype: "Select",
			options: [
				{ value: "1", label: __("Baisakh") },
				{ value: "2", label: __("Jestha") },
				{ value: "3", label: __("Ashad") },
				{ value: "4", label: __("Shrawan") },
				{ value: "5", label: __("Bhadra") },
				{ value: "6", label: __("Ashwin") },
				{ value: "7", label: __("Kartik") },
				{ value: "8", label: __("Mangsir") },
				{ value: "9", label: __("Poush") },
				{ value: "10", label: __("Magh") },
				{ value: "11", label: __("Falgun") },
				{ value: "12", label: __("Chaitra") },
			],
			default: "1",
		},
		{
			fieldname: "use_custom_period",
			label: __("Use Custom Calculation Period"),
			fieldtype: "Check",
			default: 0,
			on_change: function () {
				let val = frappe.query_report.get_filter_value("filter_based_on");
				let custom = frappe.query_report.get_filter_value("use_custom_period");
				let show = val === "BS Month" && custom;
				frappe.query_report.toggle_filter_display("custom_start_day", !show);
				frappe.query_report.toggle_filter_display("start_month_type", !show);
				frappe.query_report.toggle_filter_display("custom_end_day", !show);
				frappe.query_report.toggle_filter_display("end_month_type", !show);
			}
		},
		{ fieldname: "custom_start_day", label: __("Start Day"), fieldtype: "Int", default: 29, hidden: 1 },
		{ fieldname: "start_month_type", label: __("Start Month"), fieldtype: "Select", options: ["Previous Month", "Current Month"], default: "Previous Month", hidden: 1 },
		{ fieldname: "custom_end_day", label: __("End Day"), fieldtype: "Int", default: 28, hidden: 1 },
		{ fieldname: "end_month_type", label: __("End Month"), fieldtype: "Select", options: ["Current Month", "Next Month"], default: "Current Month", hidden: 1 },
		{ fieldname: "from_bs_date", label: __("From BS Date"), fieldtype: "Data", description: __("Format: YYYY-MM-DD"), hidden: 1 },
		{ fieldname: "to_bs_date", label: __("To BS Date"), fieldtype: "Data", description: __("Format: YYYY-MM-DD"), hidden: 1 },
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
			get_query: () => {
				var company = frappe.query_report.get_filter_value("company");
				return { filters: { company: company } };
			},
		},
		{ fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department" },
		{ fieldname: "shift", label: __("Shift Type"), fieldtype: "Link", options: "Shift Type" },
		{ fieldname: "show_details", label: __("Show Daily Details"), fieldtype: "Check", default: 0 },
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company") || "",
			reqd: 1,
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		const colId = column.fieldname || column.id;
		const rowData = data && typeof data === "object" && !Array.isArray(data) ? data : row;

		if (colId && colId.startsWith("day_") && !colId.endsWith("_in") && !colId.endsWith("_out") && !colId.endsWith("_wh") && !colId.endsWith("_checks")) {
			let cellData = {};
			const rawJson = (rowData && rowData[colId]) ?? value;
			try {
				cellData = typeof rawJson === "string" ? JSON.parse(rawJson) : rawJson || {};
			} catch (e) {
				console.warn("Monthly Attendance Sheet BS: invalid cell JSON", colId, e);
				return `<div class="attendance-cell-container" title="Cell data error">
					<div class="attendance-bar attendance-bar-placeholder"></div>
					<div class="cnr-pill-row">${getPillHTML("NONE", "", "0", false, false, null, {}, false, "")}</div>
				</div>`;
			}

			try {
				let {
					status, wh, checks, target, leave_type, leave_acronym, half_day, late_entry, early_exit,
					bar_data, attendance_doc, late_entry_app, early_exit_app, ooo_app,
					late_mins, early_mins, late_kind, early_kind,
				} = cellData;

				let logDetails = checks ? `\nLogs: ${checks.split(",").join(" -> ")}` : "";
				let leaveDetails = leave_type ? `\nLeave: ${leave_type}${half_day ? " (Half Day)" : ""}` : "";

				let extraDetails = "";
				const lateMinsVal = late_mins || (bar_data && bar_data.late_mins) || 0;
				const earlyMinsVal = early_mins || (bar_data && bar_data.early_mins) || 0;
				if (lateMinsVal > 0) extraDetails += `\nLate: ${formatMins(lateMinsVal)} (${lateKindLabel(late_kind)})`;
				if (earlyMinsVal > 0) extraDetails += `\nEarly: ${formatMins(earlyMinsVal)} (${lateKindLabel(early_kind)})`;
				if (bar_data) {
					if (bar_data.ooo_mins > 0) extraDetails += `\nOOO Work: ${formatMins(bar_data.ooo_mins)}`;
					if (bar_data.extra_mins > 0) extraDetails += `\nExtra Work: ${formatMins(bar_data.extra_mins)}`;
				}
				if (late_entry_app) extraDetails += `\nLate Entry App: ${late_entry_app}`;
				if (early_exit_app) extraDetails += `\nEarly Exit App: ${early_exit_app}`;
				if (ooo_app) extraDetails += `\nOOO App: ${ooo_app}`;

				const isHalfDay = isHalfDayCell(status, half_day, target);
				const halfDayLabel = status === "HD/A" ? "Half Day (Absent half)" : status === "HD/P" ? "Half Day (Present half)" : "Half Day";
				const hoverTitle = isHalfDay
					? `${halfDayLabel} · Target: ${target} hr${leaveDetails}${extraDetails}${logDetails}`
					: `Target: ${target} hr${leaveDetails}${extraDetails}${logDetails}`;
				let hoverAttr = ` title="${frappe.utils.escape_html(hoverTitle)}" `;
				const cellClass = isHalfDay ? "attendance-cell-container attendance-cell--half-day" : "attendance-cell-container";

				let barHTML = "";
				if (bar_data) {
					try {
						barHTML = renderTimeBar(bar_data, status, wh, checks, target, leave_type, half_day, late_entry, early_exit);
					} catch (barErr) { console.error(barErr); }
				}

				let appLinks = { late_entry_app, early_exit_app, ooo_app, late_kind, early_kind, late_mins: lateMinsVal, early_mins: earlyMinsVal };
				let lateBadge = cnrKindBadge("L", appLinks.late_kind, appLinks.late_entry_app, "late-entry-application", appLinks.late_mins);
				let earlyBadge = cnrKindBadge("E", appLinks.early_kind, appLinks.early_exit_app, "early-exit-application", appLinks.early_mins);
				let oooBadge = appLinks.ooo_app
					? cnrDocLink(
						"out-of-office-application",
						appLinks.ooo_app,
						`<span style="background:#3b82f6;color:#fff;font-weight:700;font-size:9px;padding:1px 5px;border-radius:999px;line-height:1;margin:0;">O</span>`,
						appLinks.ooo_app
					)
					: "";
				let pillHTML = getPillHTML(status, wh, target, late_entry, early_exit, attendance_doc, appLinks, half_day, leave_acronym);
				let badgeRow = (lateBadge || earlyBadge || oooBadge)
					? `<div class="cnr-badge-row">
						<div class="cnr-badge-slot cnr-badge-left">${lateBadge || ""}</div>
						<div class="cnr-badge-slot cnr-badge-mid">${oooBadge || ""}</div>
						<div class="cnr-badge-slot cnr-badge-right">${earlyBadge || ""}</div>
					</div>`
					: "";

				return `<div ${hoverAttr} class="${cellClass}">
					${barHTML || `<div class="attendance-bar attendance-bar-placeholder"></div>`}
					<div class="cnr-pill-row">${pillHTML}</div>
					${badgeRow}
				</div>`;
			} catch (fmtErr) {
				console.error("Monthly Attendance Sheet BS formatter", fmtErr);
				const st = (cellData && cellData.status) || "NONE";
				return `<div class="attendance-cell-container" title="${frappe.utils.escape_html(String(fmtErr.message || fmtErr))}">
					<div class="attendance-bar attendance-bar-placeholder"></div>
					<div class="cnr-pill-row">${getPillHTML(st, cellData && cellData.wh, cellData && cellData.target, false, false, cellData && cellData.attendance_doc, {}, cellData && cellData.half_day, cellData && cellData.leave_acronym)}</div>
				</div>`;
			}
		}

		value = default_formatter(value, row, column, data);

		const appCountCols = {
			total_late_entry_apps: "Late Entry Application",
			total_early_exit_apps: "Early Exit Application",
			total_ooo_apps: "Out of Office Application",
		};
		if (appCountCols[column.fieldname] && data) {
			const count = cint(data[column.fieldname]);
			const link = count
				? cnrAppListLink(appCountCols[column.fieldname], data.employee, data.period_start, data.period_end, count)
				: `<span style="text-align:center; display:block; width:100%;">${count || 0}</span>`;
			return `<div style="height: 68px; display: flex; align-items: center; justify-content: center;">${link}</div>`;
		}

		if (["total_present", "total_absent", "total_holiday", "total_leave", "payable_days", "total_late_entry", "total_early_exit", "total_grace_late", "total_unexcused_late"].includes(column.fieldname)) {
			value = `<div style="text-align:center; font-weight:bold;">${value}</div>`;
		}

		return `<div style="height: 68px; display: flex; align-items: center;">${value}</div>`;
	},
	"get_datatable_options": function (options) {
		(options.columns || []).forEach((col) => {
			const colId = col.fieldname || col.id;
			if (colId && /^day_\d{4}_\d{2}_\d{2}$/.test(colId)) {
				col.width = col.width || 88;
				col.minWidth = col.minWidth || 88;
			}
			if (is_sheet_bs_frozen_column(col)) {
				col.sticky = true;
			}
		});
		return Object.assign(options, {
			rowHeight: 72,
			cellHeight: 72,
			inlineFilters: false,
			layout: "fixed",
		});
	},
	after_datatable_render: function (datatable) {
		bind_sheet_bs_frozen_columns(datatable);
		if (datatable.style && typeof datatable.style.refreshColumnWidth === "function") {
			datatable.style.refreshColumnWidth();
		}
	},
};

const SHEET_BS_FROZEN_COLUMNS = ["_rowIndex", "employee_name", "summary"];

function is_sheet_bs_frozen_column(col) {
	if (!col) return false;
	return SHEET_BS_FROZEN_COLUMNS.includes(col.id) || SHEET_BS_FROZEN_COLUMNS.includes(col.fieldname);
}

function bind_sheet_bs_frozen_columns(datatable) {
	if (!datatable || !datatable.bodyScrollable) return;

	const paint = () => {
		const scrollLeft = datatable.bodyScrollable.scrollLeft || 0;
		const cols = (datatable.getColumns() || []).filter(is_sheet_bs_frozen_column);
		const lastIndex = cols.length ? cols[cols.length - 1].colIndex : null;
		const frozenIndexes = new Set(cols.map((c) => c.colIndex));
		const offset = scrollLeft ? `translateX(${scrollLeft}px)` : "";

		datatable.wrapper.querySelectorAll(".dt-cell--sheet-bs-frozen").forEach((cell) => {
			const colIndex = parseInt(cell.dataset.colIndex, 10);
			if (!frozenIndexes.has(colIndex)) {
				cell.classList.remove("dt-cell--sheet-bs-frozen", "dt-cell--sheet-bs-frozen-last");
				cell.style.transform = "";
			}
		});

		cols.forEach((col) => {
			datatable.wrapper.querySelectorAll(`.dt-cell--col-${col.colIndex}`).forEach((cell) => {
				// Header/filter cells already stay put via datatable sticky-top compensation.
				if (cell.classList.contains("dt-cell--sticky-top")) return;
				cell.classList.add("dt-cell--sheet-bs-frozen");
				cell.classList.toggle("dt-cell--sheet-bs-frozen-last", col.colIndex === lastIndex);
				cell.style.transform = offset;
			});
		});
	};

	if (!datatable.__sheet_bs_frozen_bound) {
		datatable.__sheet_bs_frozen_bound = true;
		datatable.bodyScrollable.addEventListener("scroll", paint, { passive: true });
		const restore = datatable.bodyRenderer.restoreState.bind(datatable.bodyRenderer);
		datatable.bodyRenderer.restoreState = function () {
			restore();
			paint();
		};
	}

	paint();
}

// ============================================================================
// TIME BAR RENDERER
// ============================================================================

function renderTimeBar(barData, status, wh, checks, targetAmount, leaveType, halfDay, lateEntry, earlyExit) {
	// No shift assigned
	if (barData.no_shift) return "";

	// Weekly Off or Full Leave — don't show bar if no segments
	if ((barData.is_weekly_off || barData.is_leave) && !barData.segments.length) return "";

	// No data (no attendance, no checkins)
	if (status === "NONE" && !barData.segments.length) return "";

	// Build the time bar
	let shiftStart = barData.shift_start ? timeToMinutes(barData.shift_start) : 0;
	let shiftEnd = barData.shift_end ? timeToMinutes(barData.shift_end) : 1440;
	if (shiftEnd <= shiftStart) shiftEnd += 1440;
	let shiftDuration = shiftEnd - shiftStart;

	let bufferMins = Math.round(shiftDuration * 0.125);
	let barStart = shiftStart - bufferMins;
	let barEnd = shiftEnd + bufferMins;
	let totalBarMins = barEnd - barStart;

	let segmentHTML = "";
	let tooltipLines = [];
	let colorTotals = { normal: 0, ooo: 0, halfday: 0, gap: 0, extra: 0 };
	let colorMap = {
		normal: { bg: "#22c55e", label: "In Office" },
		ooo: { bg: "#3b82f6", label: "OOO Work" },
		wfh: { bg: "#0d9488", label: "Work From Home" },
		halfday: { bg: "#a855f7", label: "Half Day Leave" },
		gap: { bg: "#ef4444", label: "Gap (Absent)" },
		extra: { bg: "#f97316", label: "Extra Work" },
		holiday: { bg: "#94a3b8", label: "Holiday / WO" }
	};

	if (barData.segments && barData.segments.length) {
		barData.segments.forEach(seg => {
			let segStart = timeToMinutes(seg.start);
			let segEnd = timeToMinutes(seg.end);
			if (segEnd <= segStart) segEnd = segStart + 1;

			let duration = segEnd - segStart;
			let leftPct = Math.max(0, ((segStart - barStart) / totalBarMins) * 100);
			let widthPct = Math.max(0.5, (duration / totalBarMins) * 100);

			if (leftPct + widthPct > 100) widthPct = 100 - leftPct;

			let colors = colorMap[seg.type] || colorMap.normal;
			segmentHTML += `<div class="bar-segment bar-segment-${seg.type}" style="position:absolute;left:${leftPct.toFixed(1)}%;width:${widthPct.toFixed(1)}%;background:${colors.bg};"></div>`;

			let durMins = duration;
			let durH = Math.floor(durMins / 60);
			let durM = durMins % 60;
			let durStr = durH > 0 ? `${durH}h ${durM}m` : `${durM}m`;

			tooltipLines.push({
				color: colors.bg,
				label: colors.label,
				start: seg.start,
				end: seg.end,
				duration: durStr
			});

			colorTotals[seg.type] = (colorTotals[seg.type] || 0) + durMins;
		});
	}

	let shiftStartPct = ((shiftStart - barStart) / totalBarMins) * 100;
	let shiftEndPct = ((shiftEnd - barStart) / totalBarMins) * 100;
	let shiftMarkers = `
		<div style="position:absolute;left:${shiftStartPct.toFixed(1)}%;top:0;bottom:0;width:1px;background:#94a3b8;z-index:2;opacity:0.5;"></div>
		<div style="position:absolute;left:${shiftEndPct.toFixed(1)}%;top:0;bottom:0;width:1px;background:#94a3b8;z-index:2;opacity:0.5;"></div>
	`;

	let tooltipHTML = "";
	if (tooltipLines.length) {
		let lines = tooltipLines.map(t =>
			`<div class="tooltip-line">
				<span class="tooltip-color-dot" style="background:${t.color};"></span>
				<span class="tooltip-time">${t.start} - ${t.end}</span>
				<span class="tooltip-label">${t.label}</span>
				<span class="tooltip-duration">${t.duration}</span>
			</div>`
		).join("");

		let summaryItems = Object.entries(colorTotals)
			.filter(([, v]) => v > 0)
			.map(([k, v]) => {
				let h = Math.floor(v / 60);
				let m = v % 60;
				let total = h > 0 ? `${h}h ${m}m` : `${m}m`;
				let c = colorMap[k];
				return `<span class="tooltip-summary-item">
					<span class="tooltip-color-dot" style="background:${c.bg};"></span>
					${c.label}: ${total}
				</span>`;
			}).join("");

		const halfDayHeader = halfDay || isHalfDayCell(status, false, targetAmount)
			? `<div class="bar-tooltip-half-day">Half Day · Target: ${targetAmount}h</div>`
			: "";
		const targetLineColor = halfDay || isHalfDayCell(status, false, targetAmount) ? "#c084fc" : "#67e8f9";
		tooltipHTML = `<div class="bar-tooltip">
			${halfDayHeader}
			${lines}
			${summaryItems ? `<div class="tooltip-summary">${summaryItems}</div>` : ""}
			${wh ? `<div style="margin-top:4px;font-size:10px;color:${targetLineColor};">Total: ${wh} | Target: ${targetAmount}h</div>` : ""}
		</div>`;
	}

	return `<div class="attendance-bar" style="height:8px; border-radius:4px;">
		${shiftMarkers}
		${segmentHTML}
		${tooltipHTML}
	</div>`;
}

// ============================================================================
// PILL RENDERER
// ============================================================================

function cnrDocLink(doctypeSlug, name, innerHTML, title) {
	if (!name) return innerHTML;
	const href = `/app/${doctypeSlug}/${encodeURIComponent(name)}`;
	return `<a href="${href}" target="_blank" title="${frappe.utils.escape_html(title || name)}" style="text-decoration:none;color:inherit;display:inline-flex;align-items:center;" onclick="event.stopPropagation();">${innerHTML}</a>`;
}

function cnrAppListLink(doctype, employee, periodStart, periodEnd, count) {
	const filters = {
		employee: employee,
		attendance_date: ["between", [periodStart, periodEnd]],
		docstatus: 1,
		status: "Approved",
	};
	const filtersJson = frappe.utils.escape_html(JSON.stringify(filters));
	const doctypeJson = frappe.utils.escape_html(JSON.stringify(doctype));
	return `<a href="#" style="font-weight:bold; text-decoration:underline;"
		onclick='event.preventDefault(); event.stopPropagation(); frappe.route_options=${filtersJson}; frappe.set_route("List", ${doctypeJson});'>
		${count}
	</a>`;
}

function cint(v) {
	const n = parseInt(v, 10);
	return isNaN(n) ? 0 : n;
}

function lateKindLabel(kind) {
	if (kind === "grace") return "within grace";
	if (kind === "excused") return "application approved";
	if (kind === "unexcused") return "no application";
	return "—";
}

function cnrKindBadge(prefix, kind, appName, doctypeSlug, mins) {
	if (!kind) return "";
	const styles = {
		grace: "background:#fbbf24;color:#78350f;",
		unexcused: "background:#ef4444;color:#fff;",
		excused: "background:#16a34a;color:#fff;",
	};
	const labels = {
		grace: `${prefix}g`,
		unexcused: `${prefix}!`,
		excused: `${prefix}✓`,
	};
	const title = `${prefix === "L" ? "Late" : "Early"} ${lateKindLabel(kind)}${mins ? ` · ${formatMins(mins)}` : ""}${appName ? ` · ${appName}` : ""}`;
	const badge = `<span style="${styles[kind] || ""}font-weight:700;font-size:9px;padding:1px 5px;border-radius:999px;line-height:1;white-space:nowrap;display:inline-block;margin:0;" title="${frappe.utils.escape_html(title)}">${labels[kind] || prefix}</span>`;
	if (appName) {
		return cnrDocLink(doctypeSlug, appName, badge, title);
	}
	return badge;
}

function isHalfDayCell(status, halfDayFlag, targetAmount) {
	if (halfDayFlag || status === "HD/P" || status === "HD/A") return true;
	const targetHours = parseFloat(targetAmount);
	return targetHours > 0 && targetHours < 8;
}

function getPillHTML(status, wh, targetAmount, lateEntry, earlyExit, attendance_doc, appLinks, halfDayFlag, leaveAcronym) {
	appLinks = appLinks || {};
	if (status === "NONE" || !status) {
		return `<div style='height:8px;width:8px;border-radius:50%;background:#cbd5e1;'></div>`;
	}

	let bgColor = "#f3f4f6", color = "#1f2937", text = wh ? wh : status;
	if (status === "Lv") {
		text = (leaveAcronym || "Lv").toString().slice(0, 3);
	}
	let workedHours = parseFloat((wh || "0").toString().replace('h', '')) || 0;
	let targetHours = parseFloat(targetAmount) || 0;
	const isHalfDay = isHalfDayCell(status, halfDayFlag, targetAmount);

	if (targetHours === 0 && workedHours > 0) {
		bgColor = "#f97316";
		color = "#ffffff";
	} else if (isHalfDay) {
		bgColor = "#a855f7";
		color = "#faf5ff";
	} else if (status === "P" || status === "WFH") {
		if (workedHours > 0 && workedHours < targetHours) { bgColor = "#ffd43b"; color = "#453403"; }
		else { bgColor = "#6fe5a9"; color = "#042f1c"; }
	} else if (status === "Ab") {
		bgColor = "#ff6b7e"; color = "#450a0a"; text = "Ab";
	} else if (status === "Lv") {
		bgColor = "#dae5ff"; color = "#1e293b";
	} else if (status === "WO" || status === "Hol") { bgColor = "#e5e7eb"; color = "#4b5563"; text = status; }

	let linkStart = attendance_doc ? `<a href="/app/attendance/${attendance_doc}" target="_blank" style="text-decoration: none; color: inherit; display: inline-block;">` : "";
	let linkEnd = attendance_doc ? `</a>` : "";

	// Status pill only — L/E badges are rendered under the time bar (L left, E right)
	return `${linkStart}<div style='display:flex;align-items:center;justify-content:center;background-color:${bgColor}; color:${color}; font-size:11px; font-weight:700;
		padding:3px 10px; border-radius:12px; text-align:center; border: 1px solid rgba(0,0,0,0.1); min-width:40px; line-height:1; margin:0; ${attendance_doc ? 'cursor:pointer;' : ''}'>
		<span style="line-height:1;">${text}</span>
	</div>${linkEnd}`;
}

function renderLegacyCell(status, wh, checks, targetAmount, leaveType, halfDay, lateEntry, earlyExit, fieldname, data, attendance_doc, appLinks) {
	appLinks = appLinks || {};
	let logDetails = checks ? `\nLogs: ${checks.split(",").join(" -> ")}` : "";
	let leaveDetails = leaveType ? `\nLeave: ${leaveType}${halfDay ? " (Half Day)" : ""}` : "";
	const isHalfDay = isHalfDayCell(status, halfDay, targetAmount);
	const halfDayLabel = status === "HD/A" ? "Half Day (Absent half)" : status === "HD/P" ? "Half Day (Present half)" : "Half Day";
	const hoverTitle = isHalfDay
		? `${halfDayLabel} · Target: ${targetAmount} hr${leaveDetails}${logDetails}`
		: `Target: ${targetAmount} hr${leaveDetails}${logDetails}`;
	let hoverAttr = ` title="${frappe.utils.escape_html(hoverTitle)}" `;
	const cellClass = isHalfDay ? "attendance-cell-container attendance-cell--half-day" : "attendance-cell-container";

	let lateBadge = cnrKindBadge("L", appLinks.late_kind, appLinks.late_entry_app, "late-entry-application", appLinks.late_mins);
	let earlyBadge = cnrKindBadge("E", appLinks.early_kind, appLinks.early_exit_app, "early-exit-application", appLinks.early_mins);
	let oooBadge = appLinks.ooo_app
		? cnrDocLink(
			"out-of-office-application",
			appLinks.ooo_app,
			`<span style="background:#3b82f6;color:#fff;font-weight:700;font-size:9px;padding:1px 5px;border-radius:999px;line-height:1;margin:0;">O</span>`,
			appLinks.ooo_app
		)
		: "";
	let legacyAcronym = data[fieldname + "_leave_acronym"] || "";
	let pillHTML = getPillHTML(status, wh, targetAmount, lateEntry, earlyExit, attendance_doc, appLinks, halfDay, legacyAcronym);

	const badgeRow = (lateBadge || earlyBadge || oooBadge)
		? `<div class="cnr-badge-row">
			<div class="cnr-badge-slot cnr-badge-left">${lateBadge || ""}</div>
			<div class="cnr-badge-slot cnr-badge-mid">${oooBadge || ""}</div>
			<div class="cnr-badge-slot cnr-badge-right">${earlyBadge || ""}</div>
		</div>`
		: "";

	return `<div ${hoverAttr} class="${cellClass}" style="cursor:help;">
		<div class="attendance-bar attendance-bar-placeholder"></div>
		<div class="cnr-pill-row">${pillHTML}</div>
		${badgeRow}
	</div>`;
}

// ============================================================================
// UTILITY
// ============================================================================

function timeToMinutes(timeStr) {
	if (!timeStr) return 0;
	let parts = timeStr.split(":");
	return parseInt(parts[0]) * 60 + parseInt(parts[1] || 0);
}

function formatMins(mins) {
	if (!mins || mins <= 0) return "0m";
	let h = Math.floor(mins / 60);
	let m = mins % 60;
	if (h > 0) return `${h}h ${m}m`;
	return `${m}m`;
}
