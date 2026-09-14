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

const SHEET_BS_TOTAL_SUMMARY_COLUMNS = new Set([
	"total_days_in_period",
	"payable_days",
	"total_absent",
	"lwp_days",
	"paid_leave_days",
]);

const SHEET_BS_SUMMARY_FLOAT_FIELDS = new Set([
	"total_holiday", "total_present", "total_absent", "payable_days",
	"present_full", "present_half", "absent_full", "absent_half",
	"lwp_days", "lwp_full", "lwp_half",
	"paid_leave_days", "paid_leave_full", "paid_leave_half",
	"annual_home_leave_days", "sick_leave_days", "other_paid_leave_days",
	"holiday_extra_present", "holiday_extra_hours", "total_no_of_days",
]);
const SHEET_BS_DAILY_HOVER_DATA = new Map();
const SHEET_BS_AUDIT_HOVER_DATA = new Map();
let sheetBsAuditHoverSeq = 0;

function sheetBsFormatOneDecimal(n) {
	const num = parseFloat(n);
	if (Number.isNaN(num)) return n;
	const rounded = Math.round(num * 10) / 10;
	if (Math.abs(rounded - Math.round(rounded)) < 1e-9) {
		return String(Math.round(rounded));
	}
	return rounded.toFixed(1);
}

function sheetBsFormatSummaryNumber(fieldname, raw, column) {
	if (raw === null || raw === undefined || raw === "") {
		return "0";
	}
	const num = parseFloat(raw);
	if (Number.isNaN(num)) {
		return raw;
	}
	if (fieldname && fieldname.endsWith("_full")) {
		return String(Math.round(num));
	}
	if (fieldname && fieldname.endsWith("_half")) {
		return sheetBsFormatOneDecimal(num);
	}
	if (SHEET_BS_SUMMARY_FLOAT_FIELDS.has(fieldname)) {
		return sheetBsFormatOneDecimal(num);
	}
	if (column && column.fieldtype === "Float" && fieldname && !fieldname.startsWith("day_")) {
		return sheetBsFormatOneDecimal(num);
	}
	return null;
}

function sheetBsEsc(value) {
	return frappe.utils.escape_html(String(value === null || value === undefined ? "" : value));
}

function sheetBsAuditRow(label, value, note) {
	return `<div class="sheet-bs-audit-row">
		<span class="sheet-bs-audit-label">${sheetBsEsc(label)}</span>
		<span class="sheet-bs-audit-value">${sheetBsEsc(value)}</span>
		${note ? `<span class="sheet-bs-audit-note">${sheetBsEsc(note)}</span>` : ""}
	</div>`;
}

function sheetBsBreakdownHTML(items, emptyLabel) {
	const entries = Object.entries(items || {}).filter(([, value]) => (parseFloat(value) || 0) !== 0);
	if (!entries.length) {
		return `<div class="sheet-bs-audit-empty">${sheetBsEsc(emptyLabel || __("No entries"))}</div>`;
	}
	return entries
		.sort(([a], [b]) => a.localeCompare(b))
		.map(([label, value]) => sheetBsAuditRow(label, sheetBsFormatOneDecimal(value)))
		.join("");
}

function sheetBsAuditCell(display, title, body, options) {
	options = options || {};
	const classes = [
		"sheet-bs-summary-cell",
		"sheet-bs-audit-cell",
		options.cellClass || "",
		options.tone ? `sheet-bs-audit-cell--${options.tone}` : "",
	].filter(Boolean).join(" ");
	// Keep hover HTML out of the cell so DataTable does not flatten it into a native title tooltip.
	const key = `audit-${++sheetBsAuditHoverSeq}`;
	SHEET_BS_AUDIT_HOVER_DATA.set(key, { title, body });
	return `<div class="${classes}" tabindex="0" data-sheet-bs-audit-key="${sheetBsEsc(key)}">
		<span class="sheet-bs-audit-main">${sheetBsEsc(display)}</span>
	</div>`;
}

function sheetBsStripNativeTitles(root) {
	if (!root || !root.querySelectorAll) return;
	root.querySelectorAll(
		".sheet-bs-audit-cell[title], .sheet-bs-hover-host[title], .sheet-bs-summary-cell[title], .attendance-cell-container[title]"
	).forEach((el) => el.removeAttribute("title"));
}

function sheetBsPaidDaysCell(row) {
	const daily = parseFloat(row.paid_days_daily_method ?? row.payable_days) || 0;
	const period = parseFloat(row.paid_days_period_method) || 0;
	const components = parseFloat(row.paid_days_component_method) || 0;
	const mismatch = cint(row.payable_days_mismatch) === 1;
	const difference = (value) => sheetBsFormatOneDecimal(value - daily);
	let body = `<div class="sheet-bs-audit-section">
		${sheetBsAuditRow(__("Period − LWP − Absent"), sheetBsFormatOneDecimal(period), __("Difference {0}", [difference(period)]))}
		${sheetBsAuditRow(__("Present + Paid Leave + Holidays"), sheetBsFormatOneDecimal(components), __("Difference {0}", [difference(components)]))}
		${sheetBsAuditRow(__("Canonical daily paid flags"), sheetBsFormatOneDecimal(daily), __("Displayed value"))}
	</div>`;
	const causes = [];
	if (cint(row.unmarked)) causes.push(__("{0} unmarked day(s)", [cint(row.unmarked)]));
	if (cint(row.unclassified_leave)) causes.push(__("{0} leave day(s) without a configured Leave Type", [cint(row.unclassified_leave)]));
	if ((parseFloat(row.sandwich) || 0) > 0) causes.push(__("{0} sandwich-adjusted day(s)", [sheetBsFormatOneDecimal(row.sandwich)]));
	if (cint(row.future_days_excluded)) causes.push(__("{0} future day(s) excluded", [cint(row.future_days_excluded)]));
	if (cint(row.unmarked_today_excluded)) causes.push(__("Today is pending and excluded until attendance is marked"));
	if (mismatch && !causes.length) causes.push(__("Check overlapping or unsupported attendance statuses."));
	body += `<div class="sheet-bs-audit-result sheet-bs-audit-result--${mismatch ? "bad" : "good"}">
		${mismatch ? __("Checks do not reconcile") : __("All three checks reconcile within 0.05")}
	</div>`;
	if (causes.length) {
		body += `<div class="sheet-bs-audit-causes">${causes.map((cause) => `<span>${sheetBsEsc(cause)}</span>`).join("")}</div>`;
	}
	return sheetBsAuditCell(
		sheetBsFormatOneDecimal(daily),
		__("Total Paid Days audit"),
		body,
		{
			cellClass: `sheet-bs-payable-days${mismatch ? " sheet-bs-payable-days--mismatch" : ""}`,
			tone: mismatch ? "rejected" : "approved",
		}
	);
}

function sheetBsPeriodDaysCell(row) {
	const included = cint(row.total_days_in_period);
	const selected = cint(row.selected_period_days || included);
	const body = `<div class="sheet-bs-audit-section">
		${sheetBsAuditRow(__("Selected period days"), selected)}
		${sheetBsAuditRow(__("Days included in paid-day audit"), included)}
		${sheetBsAuditRow(__("Audit through"), row.audit_through_date || __("No eligible day yet"))}
		${sheetBsAuditRow(__("Future days excluded"), cint(row.future_days_excluded))}
		${sheetBsAuditRow(__("Unmarked today excluded"), cint(row.unmarked_today_excluded) ? __("Yes") : __("No"))}
	</div>
	<div class="sheet-bs-audit-info">${__("Past unmarked days remain included so genuine attendance gaps are still reported.")}</div>`;
	return sheetBsAuditCell(included, __("Total Period Days used for paid-day audit"), body, {
		cellClass: "sheet-bs-summary-cell--total sheet-bs-period-days",
	});
}

function sheetBsLeaveSummaryCell(row, fieldname) {
	const value = sheetBsFormatOneDecimal(row[fieldname] || 0);
	let title = "";
	let body = "";
	if (fieldname === "total_absent") {
		title = __("Absent Days");
		body = `<div class="sheet-bs-audit-section">
			${sheetBsAuditRow(__("Full-day absences"), sheetBsFormatOneDecimal(row.absent_full || 0))}
			${sheetBsAuditRow(__("Half-day absence entries"), sheetBsFormatOneDecimal((parseFloat(row.absent_half) || 0) * 2), __("{0} day units", [sheetBsFormatOneDecimal(row.absent_half || 0)]))}
			${sheetBsAuditRow(__("Sandwich absences"), sheetBsFormatOneDecimal(row.sandwich_absent || 0))}
		</div>`;
	} else if (fieldname === "lwp_days") {
		title = __("Leave Without Pay");
		body = `<div class="sheet-bs-audit-section">
			${sheetBsAuditRow(__("Full day"), sheetBsFormatOneDecimal(row.lwp_full || 0))}
			${sheetBsAuditRow(__("Half-day entries"), sheetBsFormatOneDecimal((parseFloat(row.lwp_half) || 0) * 2), __("{0} day units", [sheetBsFormatOneDecimal(row.lwp_half || 0)]))}
		</div>
		<div class="sheet-bs-audit-subtitle">${__("By leave type")}</div>
		${sheetBsBreakdownHTML(row.lwp_breakdown, __("No unpaid leave"))}`;
	} else if (fieldname === "paid_leave_days") {
		title = __("Paid Leaves");
		body = `<div class="sheet-bs-audit-section">
			${sheetBsAuditRow(__("Full day"), sheetBsFormatOneDecimal(row.paid_leave_full || 0))}
			${sheetBsAuditRow(__("Half-day entries"), sheetBsFormatOneDecimal((parseFloat(row.paid_leave_half) || 0) * 2), __("{0} day units", [sheetBsFormatOneDecimal(row.paid_leave_half || 0)]))}
			${sheetBsAuditRow(__("Annual/Home"), sheetBsFormatOneDecimal(row.annual_home_leave_days || 0))}
			${sheetBsAuditRow(__("Sick"), sheetBsFormatOneDecimal(row.sick_leave_days || 0))}
			${sheetBsAuditRow(__("Other Paid"), sheetBsFormatOneDecimal(row.other_paid_leave_days || 0))}
		</div>
		<div class="sheet-bs-audit-subtitle">${__("By leave type")}</div>
		${sheetBsBreakdownHTML(row.leave_breakdown, __("No paid leave"))}`;
		const unconfigured = sheetBsBreakdownHTML(row.unconfigured_paid_leave_breakdown, "");
		if (Object.keys(row.unconfigured_paid_leave_breakdown || {}).length) {
			body += `<div class="sheet-bs-audit-warning">
				<div class="sheet-bs-audit-subtitle">${__("Unconfigured (fallback: Other Paid)")}</div>${unconfigured}
			</div>`;
		}
	} else if (fieldname === "other_paid_leave_days") {
		title = __("Other Paid Leaves");
		body = `<div class="sheet-bs-audit-subtitle">${__("By leave type")}</div>
			${sheetBsBreakdownHTML(row.other_paid_breakdown, __("No other paid leave"))}`;
	}
	return sheetBsAuditCell(value, title, body, {
		cellClass: ["total_absent", "lwp_days", "paid_leave_days"].includes(fieldname)
			? "sheet-bs-summary-cell--total"
			: "",
	});
}

function sheetBsApplicationDetail(detail, doctype) {
	const slug = String(doctype || "").toLowerCase().replace(/\s+/g, "-");
	const date = detail.attendance_date
		? detail.attendance_date
		: `${detail.from_date || "?"} → ${detail.to_date || "?"}`;
	const reason = detail.custom_rejection_reason || detail.reason || detail.type_of_work || "";
	const timeDetails = [
		[__("Estimated arrival"), detail.estimated_late_entry_time],
		[__("Actual check-in"), detail.late_entry_time],
		[__("Estimated from"), detail.estimated_from_time],
		[__("Estimated to"), detail.estimated_to_time],
		[__("Actual from"), detail.from_time],
		[__("Actual to"), detail.to_time],
	].filter(([, value]) => value);
	return `<a class="sheet-bs-app-detail" href="/app/${sheetBsEsc(slug)}/${encodeURIComponent(detail.name)}" target="_blank" onclick="event.stopPropagation();">
		<span class="sheet-bs-app-name">${sheetBsEsc(detail.name)}</span>
		<span class="sheet-bs-app-date">${sheetBsEsc(date)}</span>
		${timeDetails.map(([label, value]) => `<span class="sheet-bs-app-date">${sheetBsEsc(label)}: ${sheetBsEsc(value)}</span>`).join("")}
		${reason ? `<span class="sheet-bs-app-reason">${sheetBsEsc(reason)}</span>` : ""}
	</a>`;
}

function sheetBsApplicationSection(label, kind, details, doctype) {
	if (!details.length) return "";
	return `<div class="sheet-bs-app-section sheet-bs-app-section--${kind}">
		<div class="sheet-bs-app-section-title">${sheetBsEsc(label)} <span>${details.length}</span></div>
		${details.map((detail) => sheetBsApplicationDetail(detail, doctype)).join("")}
	</div>`;
}

function sheetBsOccurrenceHTML(audit, kind) {
	if (!audit || !Object.keys(audit).length || !["late_entry", "early_exit"].includes(kind)) return "";
	const prefix = kind === "late_entry" ? "late" : "early";
	const free = typeof audit.free_remaining === "object"
		? audit.free_remaining[prefix]
		: audit.free_remaining;
	return `<div class="sheet-bs-occurrence-audit">
		<div class="sheet-bs-audit-subtitle">${__("Occurrence pool audit")}${cint(audit.combine_pools) ? ` · ${__("Combined late/early")}` : ""}</div>
		${sheetBsAuditRow(__("Penalty policy enabled"), cint(audit.penalty_enabled) ? __("Yes") : __("No"))}
		${sheetBsAuditRow(__("Pool occurrences"), cint(audit[`${prefix}_minor`]))}
		${sheetBsAuditRow(__("Major occurrences"), cint(audit[`${prefix}_major`]))}
		${sheetBsAuditRow(__("Initial free threshold"), cint(audit.initial_grace_occurrences))}
		${sheetBsAuditRow(__("Subsequent free step"), cint(audit.subsequent_grace_step_occurrences))}
		${sheetBsAuditRow(__("Free remaining"), cint(free))}
		${sheetBsAuditRow(__("Half-day equivalents"), sheetBsFormatOneDecimal(audit[`${prefix}_half_days`] || 0))}
		${sheetBsAuditRow(__("Full-day escalation equivalents"), sheetBsFormatOneDecimal(audit[`${prefix}_full_days`] || 0), __("Threshold {0}", [cint(audit.full_day_escalation_threshold)]))}
		${sheetBsAuditRow(__("Full-day escalation active"), audit[`${prefix}_escalated`] ? __("Yes") : __("No"))}
		<div class="sheet-bs-audit-info">${cint(audit.penalty_enabled)
			? __("Audit only — occurrence-pool penalties are monetary deductions and are not subtracted from Total Paid Days.")
			: __("Penalty policy is disabled. Values are audit projections only and are not subtracted from Total Paid Days.")}</div>
	</div>`;
}

function sheetBsApplicationCell(row, kind) {
	const stats = (row.application_audits || {})[kind] || {};
	const approved = cint(stats.approved);
	const pending = cint(stats.pending);
	const rejected = cint(stats.rejected);
	const details = Array.isArray(stats.details) ? stats.details : [];
	const grouped = {
		approved: details.filter((item) => item.status === "approved"),
		pending: details.filter((item) => item.status === "pending"),
		rejected: details.filter((item) => item.status === "rejected"),
	};
	let tone = approved ? "approved" : "neutral";
	if (pending) tone = "pending";
	if (rejected) tone = "rejected";
	const body = `<div class="sheet-bs-app-counts">
		${sheetBsAuditRow(__("Approved"), approved)}
		${sheetBsAuditRow(__("Applied / Pending"), pending)}
		${sheetBsAuditRow(__("Rejected"), rejected)}
	</div>
	${sheetBsApplicationSection(__("Approved"), "approved", grouped.approved, stats.doctype)}
	${sheetBsApplicationSection(__("Applied / Pending"), "pending", grouped.pending, stats.doctype)}
	${sheetBsApplicationSection(__("Rejected"), "rejected", grouped.rejected, stats.doctype)}
	${sheetBsOccurrenceHTML(row.occurrence_audit, kind)}`;
	return sheetBsAuditCell(approved, stats.label || __("Applications"), body, { tone });
}

function sheetBsDailyDocumentRow(label, doctypeSlug, name) {
	if (!name) return "";
	return `<a class="sheet-bs-daily-doc" href="/app/${sheetBsEsc(doctypeSlug)}/${encodeURIComponent(name)}" target="_blank" onclick="event.stopPropagation();">
		<span>${sheetBsEsc(label)}</span>
		<strong>${sheetBsEsc(name)}</strong>
	</a>`;
}

function sheetBsDailyHoverHTML(cellData, attendanceDate) {
	const statusLabels = {
		P: __("Present"),
		Ab: __("Absent"),
		Lv: __("On Leave"),
		"HD/P": __("Half Day · other half present"),
		"HD/A": __("Half Day · other half absent"),
		WFH: __("Work From Home"),
		WO: __("Weekly Off"),
		Hol: __("Holiday"),
		NONE: __("Not Marked"),
	};
	const status = cellData.status || "NONE";
	const barData = cellData.bar_data || {};
	const lateMins = cint(cellData.late_mins || barData.late_mins);
	const earlyMins = cint(cellData.early_mins || barData.early_mins);
	const logs = cellData.checks
		? String(cellData.checks).split(",").filter(Boolean).join(" → ")
		: __("No check-in logs");
	let body = `<div class="sheet-bs-audit-section">
		${sheetBsAuditRow(__("Status"), statusLabels[status] || status)}
		${sheetBsAuditRow(__("Worked"), cellData.wh || "0h")}
		${sheetBsAuditRow(__("Target"), `${sheetBsFormatOneDecimal(cellData.target || 0)}h`)}
		${cellData.leave_type ? sheetBsAuditRow(__("Leave Type"), cellData.leave_type) : ""}
		${cellData.other_half_label ? sheetBsAuditRow(__("Other Half"), cellData.other_half_title || cellData.other_half_label) : ""}
		${sheetBsAuditRow(__("Logs"), logs)}
	</div>`;

	if (lateMins || earlyMins || cint(barData.ooo_mins) || cint(barData.extra_mins) || cellData.worked_on_holiday) {
		body += `<div class="sheet-bs-audit-subtitle">${__("Time audit")}</div>
		<div class="sheet-bs-audit-section">
			${lateMins ? sheetBsAuditRow(__("Late"), formatMins(lateMins), lateKindLabel(cellData.late_kind)) : ""}
			${earlyMins ? sheetBsAuditRow(__("Early"), formatMins(earlyMins), lateKindLabel(cellData.early_kind)) : ""}
			${cint(barData.ooo_mins) ? sheetBsAuditRow(__("Out of Office Work"), formatMins(barData.ooo_mins)) : ""}
			${cint(barData.extra_mins) ? sheetBsAuditRow(__("Extra Work"), formatMins(barData.extra_mins)) : ""}
			${cellData.worked_on_holiday ? sheetBsAuditRow(__("WO/Holiday Work"), __("Counted as extra work")) : ""}
		</div>`;
	}
	const segmentLabels = {
		normal: __("In Office"),
		ooo: __("Out of Office Work"),
		wfh: __("Work From Home"),
		halfday: __("Half Day Leave"),
		gap: __("Attendance Gap"),
		extra: __("Extra Work"),
		holiday: __("Holiday / Weekly Off"),
	};
	if (Array.isArray(barData.segments) && barData.segments.length) {
		body += `<div class="sheet-bs-audit-subtitle">${__("Time segments")}</div>
			<div class="sheet-bs-audit-section">${barData.segments.map((segment) => {
				const start = timeToMinutes(segment.start);
				let end = timeToMinutes(segment.end);
				if (end < start) end += 1440;
				return sheetBsAuditRow(
					segmentLabels[segment.type] || segment.type,
					formatMins(Math.max(0, end - start)),
					`${segment.start} → ${segment.end}`
				);
			}).join("")}</div>`;
	}

	const documents = [
		sheetBsDailyDocumentRow(__("Attendance"), "attendance", cellData.attendance_doc),
		sheetBsDailyDocumentRow(__("Late Entry Application"), "late-entry-application", cellData.late_entry_app),
		sheetBsDailyDocumentRow(__("Early Exit Application"), "early-exit-application", cellData.early_exit_app),
		sheetBsDailyDocumentRow(__("Out of Office Application"), "out-of-office-application", cellData.ooo_app),
	].filter(Boolean).join("");
	if (documents) {
		body += `<div class="sheet-bs-audit-subtitle">${__("Documents")}</div>
			<div class="sheet-bs-daily-documents">${documents}</div>`;
	}
	if (cellData.paid_day_audit_included === false) {
		body += `<div class="sheet-bs-audit-info">${__("Pending/future day — excluded from the paid-day audit.")}</div>`;
	}
	return `<div class="sheet-bs-audit-hover sheet-bs-daily-audit" role="tooltip">
		<div class="sheet-bs-audit-title">${sheetBsEsc(__("Attendance details · {0}", [attendanceDate]))}</div>
		${body}
	</div>`;
}

function sheetBsTimeBarLegendHtml(leaveLegendRows) {
	const timeBar = `
		<div class="attendance-bar-legend-section">
			<div class="attendance-bar-legend-title">${__("Time bar")}</div>
			<div class="attendance-bar-legend-grid">
				<span class="legend-item"><span class="legend-swatch" style="background:#22c55e;"></span>${__("Office")}</span>
				<span class="legend-item"><span class="legend-swatch" style="background:#3b82f6;"></span>${__("OOO Work")}</span>
				<span class="legend-item"><span class="legend-swatch" style="background:#0d9488;"></span>${__("WFH")}</span>
				<span class="legend-item"><span class="legend-swatch" style="background:#a855f7;"></span>${__("Half day — hours worked")}</span>
				<span class="legend-item"><span class="legend-swatch legend-swatch--pill-leave"></span>${__("Other half — leave (acronym pill)")}</span>
				<span class="legend-item"><span class="legend-swatch legend-swatch--pill-absent"></span>${__("Other half — absent (Ab)")}</span>
				<span class="legend-item"><span class="legend-swatch" style="background:#1e40af;"></span>${__("Extra")}</span>
				<span class="legend-item"><span class="legend-swatch" style="background:#2563eb;border:1px solid #1d4ed8;"></span>${__("Worked on WO/Hol (in Holiday count, not in Present)")}</span>
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
			SHEET_BS_DAILY_HOVER_DATA.clear();
			SHEET_BS_AUDIT_HOVER_DATA.clear();
			sheetBsAuditHoverSeq = 0;
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
					status, wh, checks, target, leave_type, leave_acronym, half_day,
					bar_data, attendance_doc, late_entry_app, early_exit_app, ooo_app,
					late_mins, early_mins, late_kind, early_kind,
					other_half_label, other_half_kind, worked_on_holiday,
				} = cellData;

				const lateMinsVal = late_mins || (bar_data && bar_data.late_mins) || 0;
				const earlyMinsVal = early_mins || (bar_data && bar_data.early_mins) || 0;
				const isHalfDay = isHalfDayCell(status, half_day, target);
				let cellClass = "attendance-cell-container sheet-bs-hover-host";
				if (worked_on_holiday) cellClass += " attendance-cell--holiday-extra";
				if (isHalfDay) cellClass += " attendance-cell--half-day";

				let barHTML = "";
				if (bar_data) {
					try {
						barHTML = renderTimeBar(bar_data, status);
					} catch (barErr) { console.error(barErr); }
				}

				let appLinks = { late_entry_app, early_exit_app, ooo_app, late_kind, early_kind, late_mins: lateMinsVal, early_mins: earlyMinsVal };
				let lateBadge = cnrKindBadge("L", appLinks.late_kind, appLinks.late_entry_app, "late-entry-application");
				let earlyBadge = cnrKindBadge("E", appLinks.early_kind, appLinks.early_exit_app, "early-exit-application");
				let oooBadge = appLinks.ooo_app
					? cnrDocLink(
						"out-of-office-application",
						appLinks.ooo_app,
						`<span style="background:#3b82f6;color:#fff;font-weight:700;font-size:9px;padding:1px 5px;border-radius:999px;line-height:1;margin:0;">O</span>`
					)
					: "";
				let pillHTML = getHalfDayPillsHTML(
					status, wh, target, attendance_doc, half_day, leave_acronym,
					other_half_label, other_half_kind
				);
				let badgeRow = (lateBadge || earlyBadge || oooBadge)
					? `<div class="cnr-badge-row">
						<div class="cnr-badge-slot cnr-badge-left">${lateBadge || ""}</div>
						<div class="cnr-badge-slot cnr-badge-mid">${oooBadge || ""}</div>
						<div class="cnr-badge-slot cnr-badge-right">${earlyBadge || ""}</div>
					</div>`
					: "";

				const pillRow = pillHTML.includes("cnr-pill-row--dual")
					? pillHTML
					: `<div class="cnr-pill-row">${pillHTML}</div>`;
				const attendanceDate = colId.slice(4).replaceAll("_", "-");
				const hoverKey = `${(rowData && (rowData.employee || rowData.employee_name)) || row}:${colId}`;
				SHEET_BS_DAILY_HOVER_DATA.set(hoverKey, {
					attendanceDate,
					cellData: Object.assign({}, cellData, {
						late_mins: lateMinsVal,
						early_mins: earlyMinsVal,
					}),
				});

				return `<div class="${cellClass}" tabindex="0" data-sheet-bs-hover-key="${sheetBsEsc(hoverKey)}">
					${barHTML || `<div class="attendance-bar attendance-bar-placeholder"></div>`}
					${pillRow}
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

		if ((colId === "holiday_extra_present" || colId === "holiday_extra_hours") && rowData) {
			const raw = rowData[colId];
			const num = parseFloat(raw) || 0;
			const display =
				colId === "holiday_extra_hours"
					? (num > 0 ? `${sheetBsFormatOneDecimal(num)}h` : "0")
					: sheetBsFormatOneDecimal(num);
			return `<div class="sheet-bs-summary-cell sheet-bs-holiday-extra-col">${frappe.utils.escape_html(display)}</div>`;
		}

		if (colId === "payable_days" && rowData) {
			return sheetBsPaidDaysCell(rowData);
		}

		if (["total_absent", "lwp_days", "paid_leave_days", "other_paid_leave_days"].includes(colId) && rowData) {
			return sheetBsLeaveSummaryCell(rowData, colId);
		}

		const applicationFields = {
			attendance_request_apps: "attendance_request",
			late_entry_apps: "late_entry",
			early_exit_apps: "early_exit",
			out_of_office_apps: "out_of_office",
		};
		if (applicationFields[colId] && rowData) {
			return sheetBsApplicationCell(rowData, applicationFields[colId]);
		}

		if (colId === "total_days_in_period" && rowData) {
			return sheetBsPeriodDaysCell(rowData);
		}

		const summaryFormatted = sheetBsFormatSummaryNumber(
			colId,
			rowData && rowData[colId] !== undefined ? rowData[colId] : value,
			column
		);
		if (summaryFormatted !== null) {
			const totalCls = SHEET_BS_TOTAL_SUMMARY_COLUMNS.has(colId)
				? " sheet-bs-summary-cell--total"
				: "";
			return `<div class="sheet-bs-summary-cell${totalCls}">${frappe.utils.escape_html(summaryFormatted)}</div>`;
		}

		value = default_formatter(value, row, column, data);

		return `<div class="sheet-bs-summary-cell" style="height: 68px; display: flex; align-items: center;">${value}</div>`;
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
		bind_sheet_bs_audit_hovers(datatable);
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

function bind_sheet_bs_audit_hovers(datatable) {
	if (!datatable || !datatable.wrapper || datatable.__sheet_bs_audit_bound) return;
	datatable.__sheet_bs_audit_bound = true;
	const wrapper = datatable.wrapper;
	let portal = null;
	let closeTimer = null;

	const close = () => {
		if (portal) portal.remove();
		portal = null;
	};
	const scheduleClose = () => {
		window.clearTimeout(closeTimer);
		closeTimer = window.setTimeout(close, 120);
	};
	const open = (cell) => {
		sheetBsStripNativeTitles(cell);
		let content = null;
		if (cell.dataset.sheetBsAuditKey) {
			const payload = SHEET_BS_AUDIT_HOVER_DATA.get(cell.dataset.sheetBsAuditKey);
			if (payload) {
				const holder = document.createElement("div");
				holder.innerHTML = `<div class="sheet-bs-audit-hover" role="tooltip">
					<div class="sheet-bs-audit-title">${sheetBsEsc(payload.title)}</div>
					${payload.body}
				</div>`;
				content = holder.firstElementChild;
			}
		} else if (cell.dataset.sheetBsHoverKey) {
			const payload = SHEET_BS_DAILY_HOVER_DATA.get(cell.dataset.sheetBsHoverKey);
			if (payload) {
				const holder = document.createElement("div");
				holder.innerHTML = sheetBsDailyHoverHTML(payload.cellData, payload.attendanceDate);
				content = holder.firstElementChild;
			}
		} else {
			content = cell.querySelector(".sheet-bs-audit-hover");
		}
		if (!content) return;
		window.clearTimeout(closeTimer);
		close();
		portal = content.cloneNode(true);
		portal.classList.add("sheet-bs-audit-hover--portal");
		document.body.appendChild(portal);
		const rect = cell.getBoundingClientRect();
		const width = Math.min(420, window.innerWidth - 24);
		portal.style.width = `${width}px`;
		portal.style.left = `${Math.max(12, Math.min(rect.right - width, window.innerWidth - width - 12))}px`;
		portal.style.top = `${rect.bottom + 8}px`;
		portal.style.maxHeight = `${Math.max(48, window.innerHeight - rect.bottom - 20)}px`;
		portal.addEventListener("mouseenter", () => window.clearTimeout(closeTimer));
		portal.addEventListener("mouseleave", scheduleClose);
	};

	sheetBsStripNativeTitles(wrapper);
	// DataTable injects title= from flattened cell textContent; keep stripping after paint/scroll.
	const stripObserver = new MutationObserver(() => sheetBsStripNativeTitles(wrapper));
	stripObserver.observe(wrapper, { childList: true, subtree: true, attributes: true, attributeFilter: ["title"] });
	datatable.__sheet_bs_title_stripper = stripObserver;

	wrapper.addEventListener("mouseover", (event) => {
		const cell = event.target.closest(".sheet-bs-audit-cell, .sheet-bs-hover-host");
		if (cell && !cell.contains(event.relatedTarget)) open(cell);
	});
	wrapper.addEventListener("mouseout", (event) => {
		const cell = event.target.closest(".sheet-bs-audit-cell, .sheet-bs-hover-host");
		if (cell && !cell.contains(event.relatedTarget)) scheduleClose();
	});
	wrapper.addEventListener("focusin", (event) => {
		const cell = event.target.closest(".sheet-bs-audit-cell, .sheet-bs-hover-host");
		if (cell) open(cell);
	});
	wrapper.addEventListener("focusout", scheduleClose);
	if (datatable.bodyScrollable) {
		datatable.bodyScrollable.addEventListener("scroll", close, { passive: true });
	}
}

// ============================================================================
// TIME BAR RENDERER
// ============================================================================

function renderTimeBar(barData, status) {
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
	let colorMap = {
		normal: "#22c55e",
		ooo: "#3b82f6",
		wfh: "#0d9488",
		halfday: "#a855f7",
		gap: "#ef4444",
		extra: "#1e40af",
		holiday: "#94a3b8",
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

			let color = colorMap[seg.type] || colorMap.normal;
			segmentHTML += `<div class="bar-segment bar-segment-${seg.type}" style="position:absolute;left:${leftPct.toFixed(1)}%;width:${widthPct.toFixed(1)}%;background:${color};"></div>`;
		});
	}

	let shiftStartPct = ((shiftStart - barStart) / totalBarMins) * 100;
	let shiftEndPct = ((shiftEnd - barStart) / totalBarMins) * 100;
	let shiftMarkers = `
		<div style="position:absolute;left:${shiftStartPct.toFixed(1)}%;top:0;bottom:0;width:1px;background:#94a3b8;z-index:2;opacity:0.5;"></div>
		<div style="position:absolute;left:${shiftEndPct.toFixed(1)}%;top:0;bottom:0;width:1px;background:#94a3b8;z-index:2;opacity:0.5;"></div>
	`;

	return `<div class="attendance-bar" style="height:8px; border-radius:4px;">
		${shiftMarkers}
		${segmentHTML}
	</div>`;
}

// ============================================================================
// PILL RENDERER
// ============================================================================

function cnrDocLink(doctypeSlug, name, innerHTML) {
	if (!name) return innerHTML;
	const href = `/app/${doctypeSlug}/${encodeURIComponent(name)}`;
	return `<a href="${href}" target="_blank" style="text-decoration:none;color:inherit;display:inline-flex;align-items:center;" onclick="event.stopPropagation();">${innerHTML}</a>`;
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

function cnrKindBadge(prefix, kind, appName, doctypeSlug) {
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
	const badge = `<span style="${styles[kind] || ""}font-weight:700;font-size:9px;padding:1px 5px;border-radius:999px;line-height:1;white-space:nowrap;display:inline-block;margin:0;">${labels[kind] || prefix}</span>`;
	if (appName) {
		return cnrDocLink(doctypeSlug, appName, badge);
	}
	return badge;
}

function isHalfDayCell(status, halfDayFlag, targetAmount) {
	if (halfDayFlag || status === "HD/P" || status === "HD/A") return true;
	const targetHours = parseFloat(targetAmount);
	return targetHours > 0 && targetHours < 8;
}

function getOtherHalfPillHTML(label, kind, attendance_doc) {
	if (!label) return "";
	const isLeave = kind === "leave";
	const bg = isLeave ? "#dae5ff" : "#fecdd3";
	const color = isLeave ? "#1e293b" : "#450a0a";
	let linkStart = attendance_doc ? `<a href="/app/attendance/${attendance_doc}" target="_blank" style="text-decoration:none;color:inherit;">` : "";
	let linkEnd = attendance_doc ? `</a>` : "";
	return `${linkStart}<div class="cnr-pill-other cnr-pill-other--${kind || "absent"}" style="display:flex;align-items:center;justify-content:center;background:${bg};color:${color};font-size:10px;font-weight:700;padding:2px 8px;border-radius:12px;border:1px solid rgba(0,0,0,0.08);min-width:28px;line-height:1;margin:0;${attendance_doc ? "cursor:pointer;" : ""}">
		<span style="line-height:1;">${frappe.utils.escape_html(String(label).slice(0, 3))}</span>
	</div>${linkEnd}`;
}

function getHalfDayPillsHTML(status, wh, targetAmount, attendance_doc, halfDayFlag, leaveAcronym, otherHalfLabel, otherHalfKind) {
	const main = getPillHTML(status, wh, targetAmount, false, false, attendance_doc, {}, halfDayFlag, leaveAcronym);
	const isHalfDay = isHalfDayCell(status, halfDayFlag, targetAmount);
	if (!isHalfDay || !otherHalfLabel) {
		return main;
	}
	const other = getOtherHalfPillHTML(otherHalfLabel, otherHalfKind, attendance_doc);
	return `<div class="cnr-pill-row cnr-pill-row--dual">${main}${other}</div>`;
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
		bgColor = "#1e40af";
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
	const isHalfDay = isHalfDayCell(status, halfDay, targetAmount);
	const cellClass = isHalfDay ? "attendance-cell-container attendance-cell--half-day" : "attendance-cell-container";

	let lateBadge = cnrKindBadge("L", appLinks.late_kind, appLinks.late_entry_app, "late-entry-application");
	let earlyBadge = cnrKindBadge("E", appLinks.early_kind, appLinks.early_exit_app, "early-exit-application");
	let oooBadge = appLinks.ooo_app
		? cnrDocLink(
			"out-of-office-application",
			appLinks.ooo_app,
			`<span style="background:#3b82f6;color:#fff;font-weight:700;font-size:9px;padding:1px 5px;border-radius:999px;line-height:1;margin:0;">O</span>`
		)
		: "";
	let legacyAcronym = data[fieldname + "_leave_acronym"] || "";
	let pillHTML = getHalfDayPillsHTML(
		status, wh, targetAmount, attendance_doc, halfDay, legacyAcronym,
		data[fieldname + "_other_half_label"], data[fieldname + "_other_half_kind"]
	);

	const badgeRow = (lateBadge || earlyBadge || oooBadge)
		? `<div class="cnr-badge-row">
			<div class="cnr-badge-slot cnr-badge-left">${lateBadge || ""}</div>
			<div class="cnr-badge-slot cnr-badge-mid">${oooBadge || ""}</div>
			<div class="cnr-badge-slot cnr-badge-right">${earlyBadge || ""}</div>
		</div>`
		: "";

	return `<div class="${cellClass}">
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
