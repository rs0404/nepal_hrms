# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Spreadsheet export for Monthly Attendance Sheet BS.

Standard report export dumps day cells as JSON. These downloads expand each day into
plain columns:
  - daily: Status, Check In, Check Out, Worked Hrs
  - full:  Status, Check In, Check Out, Worked Hrs, Logs, Late/Early mins, leave, apps
"""

from __future__ import annotations

import json
import re
from copy import copy
from io import BytesIO

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate

import nepal_compliance.nepali_date_utils.nepali_date as nepali_date


SUMMARY_EXPORT_FIELDS = (
	("total_days_in_period", "Total Period Days"),
	("payable_days", "Total Paid Days"),
	("total_absent", "Absent Days"),
	("lwp_days", "Leave Without Pay"),
	("paid_leave_days", "Paid Leaves"),
	("annual_home_leave_days", "Annual/Home Leaves"),
	("sick_leave_days", "Sick Leaves"),
	("other_paid_leave_days", "Other Paid Leaves"),
	("holiday_extra_present", "Present on WO/Hol"),
	("holiday_extra_hours", "Extra Hrs (WO/Hol)"),
	("penalty_half_days", "½P Penalty"),
	("penalty_full_days", "1P Penalty"),
	("attendance_request_apps", "Attendance Request"),
	("late_entry_apps", "Late Entry"),
	("early_exit_apps", "Early Exit"),
	("out_of_office_apps", "Out of Office"),
)

BOLD_TOTAL_EXPORT_FIELDS = {
	"total_days_in_period",
	"payable_days",
	"total_absent",
	"lwp_days",
	"paid_leave_days",
	"holiday_extra_present",
	"holiday_extra_hours",
}

APPLICATION_EXPORT_KINDS = (
	("attendance_request", "Attendance Request"),
	("late_entry", "Late Entry"),
	("early_exit", "Early Exit"),
	("out_of_office", "Out of Office"),
)


def _strip_html(label) -> str:
	if label is None:
		return ""
	text = re.sub(r"<[^>]+>", " ", str(label))
	return re.sub(r"\s+", " ", text).strip()


def _parse_day_cell(raw) -> dict:
	if isinstance(raw, dict):
		return raw
	if raw in (None, ""):
		return {}
	if isinstance(raw, (bytes, bytearray)):
		raw = raw.decode("utf-8", errors="ignore")
	try:
		parsed = json.loads(raw)
		return parsed if isinstance(parsed, dict) else {"status": str(raw)}
	except Exception:
		return {"status": str(raw)}


def _day_fieldnames(start_ad, end_ad):
	curr = getdate(start_ad)
	end = getdate(end_ad)
	fields = []
	while curr <= end:
		bs = nepali_date.ad_to_bs(curr)
		day = bs["day"]
		weekday = curr.strftime("%a")
		fieldname = f"day_{curr.strftime('%Y_%m_%d')}"
		label_prefix = f"{day:02d} {weekday} ({curr.strftime('%d %b %Y')})"
		fields.append(
			{
				"ad": curr,
				"fieldname": fieldname,
				"label_prefix": label_prefix,
				"bs_label": f"{bs['year']}-{bs['month']:02d}-{bs['day']:02d}",
			}
		)
		curr = add_days(curr, 1)
	return fields


def _resolve_period(filters):
	"""Reuse report date resolution without re-running the full column builder."""
	from nepal_hrms.nepal_hrms.report.monthly_attendance_sheet_bs.monthly_attendance_sheet_bs import (
		get_bs_date_with_offset,
	)

	nepali_date._ensure_loaded()
	filters = frappe._dict(filters or {})

	if filters.get("filter_based_on") == "BS Date Range":
		from_bs = filters.get("from_bs_date")
		to_bs = filters.get("to_bs_date")
		if not from_bs or not to_bs:
			frappe.throw(_("Please provide both From and To BS Dates"))
		f_y, f_m, f_d = map(int, from_bs.split("-"))
		t_y, t_m, t_d = map(int, to_bs.split("-"))
		start_ad = nepali_date.bs_to_ad(f_y, f_m, f_d)
		end_ad = nepali_date.bs_to_ad(t_y, t_m, t_d)
	else:
		bs_year = int(filters.get("bs_year") or 2081)
		bs_month = int(filters.get("bs_month") or 1)
		if filters.get("use_custom_period"):
			s_day = int(filters.get("custom_start_day") or 1)
			s_type = filters.get("start_month_type")
			e_day = int(filters.get("custom_end_day") or 30)
			e_type = filters.get("end_month_type")
			s_offset = -1 if s_type == "Previous Month" else 0
			e_offset = 1 if e_type == "Next Month" else 0
			start_ad = get_bs_date_with_offset(bs_year, bs_month, s_day, s_offset)
			end_ad = get_bs_date_with_offset(bs_year, bs_month, e_day, e_offset)
		else:
			days_in_month = nepali_date._bs_months[bs_year][bs_month - 1]
			start_ad = nepali_date.bs_to_ad(bs_year, bs_month, 1)
			end_ad = nepali_date.bs_to_ad(bs_year, bs_month, days_in_month)

	return getdate(start_ad), getdate(end_ad)


def _time_display(value) -> str:
	if value in (None, ""):
		return ""
	text = str(value)
	# "HH:MM:SS" or datetime-like → HH:MM
	if " " in text:
		text = text.split(" ")[-1]
	return text[:5] if len(text) >= 5 else text


def _worked_hours(row: dict, fieldname: str, cell: dict):
	wh = row.get(f"{fieldname}_wh")
	if wh not in (None, ""):
		return round(flt(wh), 2)
	wh_str = cell.get("wh") or ""
	if not wh_str:
		return ""
	# "8h" / "7.5h"
	cleaned = str(wh_str).replace("h", "").strip()
	try:
		return round(float(cleaned), 2)
	except Exception:
		return wh_str


def build_export_table(filters, export_mode="daily"):
	"""Return (headers, rows) ready for Excel/CSV — no JSON day blobs."""
	from nepal_hrms.nepal_hrms.report.monthly_attendance_sheet_bs.monthly_attendance_sheet_bs import (
		execute,
	)

	export_mode = (export_mode or "daily").strip().lower()
	if export_mode not in ("daily", "full"):
		frappe.throw(_("Invalid export mode. Use daily or full."))

	filters = frappe._dict(filters or {})
	show_details = bool(cint(filters.get("show_details")))

	_columns, data, _message = execute(filters)
	if not data:
		frappe.throw(_("No data found for the selected filters."))

	start_ad, end_ad = _resolve_period(filters)
	day_fields = _day_fieldnames(start_ad, end_ad)

	headers = [_("Employee"), _("Employee Name"), _("Summary")]
	headers.extend(_(label) for _fieldname, label in SUMMARY_EXPORT_FIELDS)

	paid_leave_types = sorted(
		{
			leave_type
			for row in data
			for leave_type in (row.get("leave_breakdown") or {})
		}
	)
	if show_details:
		for day in day_fields:
			prefix = day["label_prefix"]
			headers.append(f"{prefix} {_('Status')}")
			headers.append(f"{prefix} {_('Check In')}")
			headers.append(f"{prefix} {_('Check Out')}")
			headers.append(f"{prefix} {_('Worked Hrs')}")
			headers.append(f"{prefix} {_('Penalty')}")
			headers.append(f"{prefix} {_('Late Grace')}")
			headers.append(f"{prefix} {_('Late Max')}")
			headers.append(f"{prefix} {_('Late Applied')}")
			headers.append(f"{prefix} {_('Late Approved')}")
			headers.append(f"{prefix} {_('Early Grace')}")
			headers.append(f"{prefix} {_('Early Max')}")
			headers.append(f"{prefix} {_('Early Applied')}")
			headers.append(f"{prefix} {_('Early Approved')}")
			headers.append(f"{prefix} {_('OOO Applied')}")
			headers.append(f"{prefix} {_('OOO Approved')}")
			if export_mode == "full":
				headers.extend(
					[
						f"{prefix} {_('Logs')}",
						f"{prefix} {_('Late Mins')}",
						f"{prefix} {_('Early Mins')}",
						f"{prefix} {_('Leave')}",
						f"{prefix} {_('Late App')}",
						f"{prefix} {_('Early App')}",
						f"{prefix} {_('OOO App')}",
					]
				)
		headers.extend(
			[
				_("Absent Full"),
				_("Absent Half"),
				_("LWP Full"),
				_("LWP Half"),
				_("Paid Leave Full"),
				_("Paid Leave Half"),
			]
		)
		headers.extend(f"{_('Paid Leave')}: {leave_type}" for leave_type in paid_leave_types)
		headers.extend(
			[
				_("Paid Days: Period - LWP - Absent"),
				_("Paid Days: Present + Paid Leave + Holidays"),
				_("Paid Days: Canonical Daily Flags"),
			]
		)
		for _kind, label in APPLICATION_EXPORT_KINDS:
			headers.extend([f"{_(label)} {_('Pending')}", f"{_(label)} {_('Rejected')}"])
		headers.extend(
			[
				_("Late Pool Occurrences"),
				_("Late Major Occurrences"),
				_("Early Pool Occurrences"),
				_("Early Major Occurrences"),
				_("Initial Grace Occurrences"),
				_("Subsequent Grace Step"),
				_("Free Occurrences Remaining"),
				_("Late Half-Day Equivalents"),
				_("Late Full-Day Equivalents"),
				_("Early Half-Day Equivalents"),
				_("Early Full-Day Equivalents"),
				_("Full-Day Escalation Threshold"),
				_("Combined Late/Early Pool"),
				_("Occurrence Penalty Treatment"),
			]
		)

	out_rows = []
	for row in data:
		line = [
			row.get("employee") or "",
			row.get("employee_name") or "",
			row.get("summary") or "",
		]
		line.extend(row.get(fieldname) for fieldname, _label in SUMMARY_EXPORT_FIELDS)
		if show_details:
			for day in day_fields:
				fname = day["fieldname"]
				cell = _parse_day_cell(row.get(fname))
				status = cell.get("status") or ""
				if status == "NONE":
					status = ""
				check_in = _time_display(row.get(f"{fname}_in") or "")
				check_out = _time_display(row.get(f"{fname}_out") or "")
				if not check_in and cell.get("checks"):
					parts = [
						part.strip()
						for part in str(cell.get("checks")).split(",")
						if part.strip()
					]
					if parts:
						check_in = parts[0]
						check_out = parts[-1] if len(parts) > 1 else ""
				worked = _worked_hours(row, fname, cell)
				apps = cell.get("applications") or []
				late_apps = [app for app in apps if app.get("doctype") == "Late Entry Application"]
				early_apps = [app for app in apps if app.get("doctype") == "Early Exit Application"]
				ooo_apps = [app for app in apps if app.get("doctype") == "Out of Office Application"]
				line.extend(
					[
						status,
						check_in,
						check_out,
						worked,
						cell.get("penalty_mark") or "",
						cint(cell.get("late_grace") or 0) or "",
						cint(cell.get("late_max") or 0) or "",
						len(late_apps) or "",
						sum(1 for app in late_apps if app.get("status") == "approved") or "",
						cint(cell.get("early_grace") or 0) or "",
						cint(cell.get("early_max") or 0) or "",
						len(early_apps) or "",
						sum(1 for app in early_apps if app.get("status") == "approved") or "",
						len(ooo_apps) or "",
						sum(1 for app in ooo_apps if app.get("status") == "approved") or "",
					]
				)
				if export_mode == "full":
					line.extend(
						[
							cell.get("checks") or row.get(f"{fname}_checks") or "",
							cint(cell.get("late_mins") or 0) or "",
							cint(cell.get("early_mins") or 0) or "",
							cell.get("leave_type") or "",
							cell.get("late_entry_app") or "",
							cell.get("early_exit_app") or "",
							cell.get("ooo_app") or "",
						]
					)
			line.extend(
				[
					row.get("absent_full"),
					row.get("absent_half"),
					row.get("lwp_full"),
					row.get("lwp_half"),
					row.get("paid_leave_full"),
					row.get("paid_leave_half"),
				]
			)
			line.extend(
				(row.get("leave_breakdown") or {}).get(leave_type, 0)
				for leave_type in paid_leave_types
			)
			line.extend(
				[
					row.get("paid_days_period_method"),
					row.get("paid_days_component_method"),
					row.get("paid_days_daily_method"),
				]
			)
			app_audits = row.get("application_audits") or {}
			for kind, _label in APPLICATION_EXPORT_KINDS:
				stats = app_audits.get(kind) or {}
				line.extend([cint(stats.get("pending")), cint(stats.get("rejected"))])
			occurrence = row.get("occurrence_audit") or {}
			free_remaining = occurrence.get("free_remaining")
			if isinstance(free_remaining, dict):
				free_remaining = (
					f"Late {cint(free_remaining.get('late'))}; "
					f"Early {cint(free_remaining.get('early'))}"
				)
			line.extend(
				[
					cint(occurrence.get("late_minor")),
					cint(occurrence.get("late_major")),
					cint(occurrence.get("early_minor")),
					cint(occurrence.get("early_major")),
					cint(occurrence.get("initial_grace_occurrences")),
					cint(occurrence.get("subsequent_grace_step_occurrences")),
					free_remaining if free_remaining is not None else "",
					flt(occurrence.get("late_half_days")),
					flt(occurrence.get("late_full_days")),
					flt(occurrence.get("early_half_days")),
					flt(occurrence.get("early_full_days")),
					cint(occurrence.get("full_day_escalation_threshold")),
					_("Yes") if cint(occurrence.get("combine_pools")) else _("No"),
					_(
						"½P / 1P counted as Absent (gross)"
						if cint(occurrence.get("penalty_enabled"))
						else "Policy disabled; audit projection only"
					),
				]
			)
		out_rows.append(line)

	return headers, out_rows


def _styled_xlsx_bytes(headers, rows):
	from openpyxl import load_workbook
	from frappe.utils.xlsxutils import make_xlsx

	content = make_xlsx([headers] + rows, "Attendance Sheet BS").getvalue()
	workbook = load_workbook(BytesIO(content))
	sheet = workbook.active
	bold_labels = {
		str(_(label))
		for fieldname, label in SUMMARY_EXPORT_FIELDS
		if fieldname in BOLD_TOTAL_EXPORT_FIELDS
	}
	for column_index, header in enumerate(headers, start=1):
		if str(header) not in bold_labels:
			continue
		for row_index in range(2, sheet.max_row + 1):
			cell = sheet.cell(row=row_index, column=column_index)
			font = copy(cell.font)
			font.bold = True
			cell.font = font
	output = BytesIO()
	workbook.save(output)
	return output.getvalue()


@frappe.whitelist()
def download_monthly_attendance_sheet_bs(filters=None, export_mode="daily", file_format="Excel"):
	"""Download Monthly Attendance Sheet BS with expanded daily columns (no JSON)."""
	from frappe.desk.utils import get_csv_bytes, provide_binary_file, pop_csv_params

	if isinstance(filters, str):
		filters = frappe.parse_json(filters) or {}

	frappe.permissions.can_export("Attendance", raise_exception=True)

	headers, rows = build_export_table(filters, export_mode=export_mode)
	xlsx_data = [headers] + rows

	file_format = (file_format or "Excel").strip()
	mode_suffix = "daily" if (export_mode or "daily").lower() == "daily" else "full"
	report_name = f"Monthly Attendance Sheet BS ({mode_suffix})"

	if file_format.lower() == "csv":
		csv_params = pop_csv_params(frappe._dict(frappe.local.form_dict))
		content = get_csv_bytes(
			[[frappe.as_unicode(v) if v is not None else "" for v in r] for r in xlsx_data],
			csv_params,
		)
		provide_binary_file(report_name, "csv", content)
	else:
		content = _styled_xlsx_bytes(headers, rows)
		provide_binary_file(report_name, "xlsx", content)
