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

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate

import nepal_compliance.nepali_date_utils.nepali_date as nepali_date


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
		label_prefix = f"{day:02d} {weekday}"
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
	# Force detail fields to be populated even if UI checkbox is off
	filters["show_details"] = 1

	columns, data, _message = execute(filters)
	if not data:
		frappe.throw(_("No data found for the selected filters."))

	start_ad, end_ad = _resolve_period(filters)
	day_fields = _day_fieldnames(start_ad, end_ad)

	headers = [_("Employee"), _("Employee Name"), _("Summary")]
	for day in day_fields:
		prefix = day["label_prefix"]
		headers.append(f"{prefix} {_('Status')}")
		headers.append(f"{prefix} {_('Check In')}")
		headers.append(f"{prefix} {_('Check Out')}")
		headers.append(f"{prefix} {_('Worked Hrs')}")
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

	# Totals / leave columns from report (skip day_* and detail suffixes)
	skip_prefixes = ("day_",)
	skip_exact = {
		"employee",
		"employee_name",
		"summary",
		"period_start",
		"period_end",
	}
	extra_cols = []
	for col in columns:
		fname = col.get("fieldname")
		if not fname or fname in skip_exact:
			continue
		if fname.startswith(skip_prefixes):
			continue
		if fname.endswith(("_in", "_out", "_wh", "_checks")):
			continue
		extra_cols.append(col)
		headers.append(_strip_html(col.get("label") or fname))

	out_rows = []
	for row in data:
		line = [
			row.get("employee") or "",
			row.get("employee_name") or "",
			row.get("summary") or "",
		]
		for day in day_fields:
			fname = day["fieldname"]
			cell = _parse_day_cell(row.get(fname))
			status = cell.get("status") or ""
			if status == "NONE":
				status = ""
			check_in = _time_display(row.get(f"{fname}_in") or "")
			check_out = _time_display(row.get(f"{fname}_out") or "")
			if not check_in and cell.get("checks"):
				parts = [p.strip() for p in str(cell.get("checks")).split(",") if p.strip()]
				if parts:
					check_in = parts[0]
					check_out = parts[-1] if len(parts) > 1 else ""
			worked = _worked_hours(row, fname, cell)
			line.extend([status, check_in, check_out, worked])
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

		for col in extra_cols:
			line.append(row.get(col.get("fieldname")))
		out_rows.append(line)

	return headers, out_rows


@frappe.whitelist()
def download_monthly_attendance_sheet_bs(filters=None, export_mode="daily", file_format="Excel"):
	"""Download Monthly Attendance Sheet BS with expanded daily columns (no JSON)."""
	from frappe.desk.utils import get_csv_bytes, provide_binary_file, pop_csv_params
	from frappe.utils.xlsxutils import make_xlsx

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
		content = make_xlsx(xlsx_data, "Attendance Sheet BS").getvalue()
		provide_binary_file(report_name, "xlsx", content)
