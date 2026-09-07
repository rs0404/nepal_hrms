# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""PWA helpers for Leave Application."""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate

MAX_LEAVE_RANGES = 20


def _session_employee():
	return frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")


@frappe.whitelist()
def cancel_own_leave_application(name: str):
	"""Applicant can withdraw an Open (not yet approved) leave to correct it.

	Unsubmitted Open applications cannot use Frappe cancel (docstatus 2),
	and Employee typically has no Delete permission — so this deletes the draft.
	"""
	if not name:
		frappe.throw(_("Leave Application is required"))

	session_employee = _session_employee()
	if not session_employee:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	doc = frappe.get_doc("Leave Application", name)
	if doc.employee != session_employee:
		frappe.throw(_("You can only cancel your own leave application"))

	if cint(doc.docstatus) != 0:
		frappe.throw(_("Only leave applications waiting for approval can be cancelled"))

	if (doc.status or "Open") != "Open":
		frappe.throw(_("Only leave applications waiting for approval can be cancelled"))

	frappe.delete_doc("Leave Application", name, ignore_permissions=True, force=1)
	return {"ok": True, "name": name}


def get_configured_frequent_leave_types() -> list[str]:
	"""Leave types marked as frequent in Nepal HRMS Settings, in settings order."""
	if not frappe.db.exists("DocType", "Nepal HRMS Frequent Leave Type"):
		return []

	rows = frappe.get_all(
		"Nepal HRMS Frequent Leave Type",
		filters={"parent": "Nepal HRMS Settings", "parentfield": "frequent_leave_types"},
		fields=["leave_type", "idx"],
		order_by="idx asc",
	)
	seen: set[str] = set()
	out: list[str] = []
	for row in rows:
		name = (row.leave_type or "").strip()
		if not name or name in seen:
			continue
		seen.add(name)
		out.append(name)
	return out


def _format_remaining(value):
	if value is None:
		return None
	num = flt(value)
	if num == int(num):
		return int(num)
	return round(num, 2)


def build_frequent_leave_type_list(
	configured: list[str],
	leave_allocation: dict | None,
	lwps: list[str] | None,
) -> list[dict]:
	"""Keep configured types that the employee can actually apply, with remaining balance.

	Remaining is allocation remaining minus leaves already pending approval for that type.
	"""
	allocation = leave_allocation or {}
	lwp_set = set(lwps or [])
	available = set(allocation.keys()) | lwp_set
	result: list[dict] = []
	for leave_type in configured or []:
		if leave_type not in available:
			continue
		allocated = leave_type in allocation
		is_lwp = leave_type in lwp_set and not allocated
		remaining = None
		pending = 0
		if allocated:
			details = allocation[leave_type] or {}
			pending = flt(details.get("leaves_pending_approval") or 0)
			raw = details.get("remaining_leaves")
			if raw is not None:
				remaining = _format_remaining(max(0, flt(raw) - pending))
			pending = _format_remaining(pending) or 0
		result.append(
			{
				"leave_type": leave_type,
				"remaining": remaining,
				"pending": pending,
				"is_lwp": 1 if is_lwp else 0,
			}
		)
	return result


def has_available_leave(remaining, is_lwp=False) -> bool:
	"""True when the type can still be selected (LWP always, else remaining > 0)."""
	if is_lwp:
		return True
	if remaining is None:
		return False
	return flt(remaining) > 0


def leave_type_balance_map(employee, date=None) -> dict:
	"""Leave type -> remaining/pending/is_lwp, with Open drafts already deducted."""
	from hrms.hr.doctype.leave_application.leave_application import get_leave_details

	if not employee:
		return {}

	date = getdate(date) if date else getdate()
	details = get_leave_details(employee, date)
	allocation = details.get("leave_allocation") or {}
	lwps = details.get("lwps") or []
	for leave_type, data in allocation.items():
		if isinstance(data, dict):
			data["leaves_pending_approval"] = get_open_leave_days(employee, leave_type)
	names = list(dict.fromkeys([*allocation.keys(), *lwps]))
	rows = build_frequent_leave_type_list(names, allocation, lwps)
	return {row["leave_type"]: row for row in rows}


@frappe.whitelist()
def get_frequent_leave_types(employee=None, date=None):
	"""Frequent leave types for the BSHRMS leave form, with remaining balance.

	Configured in Nepal HRMS Settings. Only types available to the employee
	(allocated or LWP) are returned, in settings order.
	"""
	configured = get_configured_frequent_leave_types()
	if not configured:
		return []

	employee = employee or _session_employee()
	if not employee:
		return []

	date = getdate(date) if date else getdate()
	balances = leave_type_balance_map(employee, date)
	return [balances[name] for name in configured if name in balances]


@frappe.whitelist()
def get_leave_type_balances(employee=None, date=None):
	"""Remaining leave by type for the PWA picker, minus Open drafts."""
	employee = employee or _session_employee()
	if not employee:
		return {}
	return leave_type_balance_map(employee, date)


def group_contiguous_dates(dates: list | None) -> list[dict]:
	"""Group YYYY-MM-DD dates into stretches of adjacent calendar days.

	Weekends that were not selected remain gaps, so Fri + Mon stay two ranges.
	"""
	unique = sorted({getdate(d) for d in (dates or []) if d})
	ranges: list[dict] = []
	for day in unique:
		if ranges and add_days(getdate(ranges[-1]["to_date"]), 1) == day:
			ranges[-1]["to_date"] = str(day)
		else:
			ranges.append({"from_date": str(day), "to_date": str(day)})
	return ranges


def normalize_leave_ranges(ranges) -> list[dict]:
	"""Parse, sort, and merge overlapping or adjacent leave ranges."""
	if isinstance(ranges, str):
		ranges = json.loads(ranges or "[]")

	parsed: list[list] = []
	for row in ranges or []:
		if not isinstance(row, dict):
			continue
		start = row.get("from_date")
		if not start:
			continue
		end = row.get("to_date") or start
		start, end = getdate(start), getdate(end)
		if end < start:
			start, end = end, start
		parsed.append([start, end])

	parsed.sort(key=lambda row: row[0])
	merged: list[list] = []
	for start, end in parsed:
		if merged and add_days(merged[-1][1], 1) >= start:
			merged[-1][1] = max(merged[-1][1], end)
		else:
			merged.append([start, end])

	return [{"from_date": str(start), "to_date": str(end)} for start, end in merged]


def get_open_leave_days(employee, leave_type, exclude_name=None) -> float:
	"""Total days on Open (draft / waiting approval) applications for this type."""
	if not employee or not leave_type:
		return 0

	filters = {
		"employee": employee,
		"leave_type": leave_type,
		"status": "Open",
		"docstatus": ["<", 2],
	}
	if exclude_name and not str(exclude_name).startswith("New "):
		filters["name"] = ["!=", exclude_name]

	rows = frappe.get_all(
		"Leave Application",
		filters=filters,
		pluck="total_leave_days",
	)
	return flt(sum(flt(days) for days in rows))


def skip_leave_balance_check(leave_type) -> bool:
	"""LWP and allow-negative types are not limited by remaining balance."""
	if not leave_type:
		return False
	row = frappe.db.get_value(
		"Leave Type",
		leave_type,
		["is_lwp", "allow_negative"],
		as_dict=True,
	)
	if not row:
		return False
	return bool(cint(row.is_lwp) or cint(row.allow_negative))


def should_block_combined_leave(
	total_days, available, is_lwp=False, allow_negative=False
) -> bool:
	"""True when combined selected days exceed remaining for a non-LWP type."""
	if is_lwp or allow_negative:
		return False
	total = flt(total_days)
	avail = flt(available)
	return (not avail) or avail < total


def total_leave_days_for_ranges(employee, leave_type, ranges) -> float:
	from hrms.hr.doctype.leave_application.leave_application import get_number_of_leave_days

	precision = cint(frappe.db.get_single_value("System Settings", "float_precision")) or 2
	total = 0
	for row in ranges or []:
		total += flt(
			get_number_of_leave_days(
				employee,
				leave_type,
				row["from_date"],
				row["to_date"],
			),
			precision,
		)
	return flt(total, precision)


def available_days_for_new_leave(
	employee, leave_type, from_date, to_date, exclude_name=None
):
	"""Days still available after Open drafts. None = skip check (LWP / allow negative)."""
	if skip_leave_balance_check(leave_type):
		return None

	from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on

	precision = cint(frappe.db.get_single_value("System Settings", "float_precision")) or 2
	balance = get_leave_balance_on(
		employee,
		leave_type,
		getdate(from_date),
		getdate(to_date),
		consider_all_leaves_in_the_allocation_period=True,
		for_consumption=True,
	)
	remaining = flt((balance or {}).get("leave_balance_for_consumption"), precision)
	pending = get_open_leave_days(employee, leave_type, exclude_name=exclude_name)
	return max(0, flt(remaining - pending, precision))


def validate_combined_leave_balance(employee, leave_type, ranges):
	"""Block Save when all selected stretches together exceed remaining balance."""
	from hrms.hr.doctype.leave_application.leave_application import InsufficientLeaveBalanceError

	available = available_days_for_new_leave(
		employee, leave_type, ranges[0]["from_date"], ranges[-1]["to_date"]
	)
	if available is None:
		return

	total = total_leave_days_for_ranges(employee, leave_type, ranges)
	if not should_block_combined_leave(total, available):
		return

	frappe.throw(
		_(
			"Insufficient leave balance for Leave Type {0}. {1} day(s) selected, {2} remaining."
		).format(
			frappe.bold(leave_type),
			_format_remaining(total),
			_format_remaining(available) or 0,
		),
		exc=InsufficientLeaveBalanceError,
		title=_("Insufficient Balance"),
	)


def validate_document_leave_balance(doc, method=None):
	"""Block Save when this application plus other Open drafts exceed remaining."""
	from hrms.hr.doctype.leave_application.leave_application import InsufficientLeaveBalanceError

	if not doc.employee or not doc.leave_type or not doc.from_date or not doc.to_date:
		return
	if (doc.status or "Open") == "Rejected":
		return
	if skip_leave_balance_check(doc.leave_type):
		return

	this_days = flt(doc.total_leave_days)
	if this_days <= 0:
		return

	exclude_name = None if doc.is_new() else doc.name
	available = available_days_for_new_leave(
		doc.employee,
		doc.leave_type,
		doc.from_date,
		doc.to_date,
		exclude_name=exclude_name,
	)
	if available is None:
		return
	if not should_block_combined_leave(this_days, available):
		return

	pending = get_open_leave_days(doc.employee, doc.leave_type, exclude_name=exclude_name)
	frappe.throw(
		_(
			"Insufficient leave balance for Leave Type {0}. {1} day(s) selected, {2} remaining after {3} pending day(s)."
		).format(
			frappe.bold(doc.leave_type),
			_format_remaining(this_days),
			_format_remaining(available) or 0,
			_format_remaining(pending) or 0,
		),
		exc=InsufficientLeaveBalanceError,
		title=_("Insufficient Balance"),
	)


@frappe.whitelist()
def create_leave_applications(
	employee=None,
	leave_type=None,
	ranges=None,
	description=None,
	leave_approver=None,
	leave_approver_name=None,
):
	"""Create one draft Leave Application per contiguous date range.

	Used by the PWA when the employee selected discontinuous days. Each insert
	runs standard Leave Application validation. A failure rolls back all.
	"""
	session_employee = _session_employee()
	if not session_employee:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	employee = employee or session_employee
	if employee != session_employee:
		frappe.throw(_("You can only create leave applications for yourself"), frappe.PermissionError)

	if not leave_type:
		frappe.throw(_("Leave Type is required"))
	if not description or not str(description).strip():
		frappe.throw(_("Reason is required"))

	ranges = normalize_leave_ranges(ranges)
	if not ranges:
		frappe.throw(_("Leave dates are required"))
	if len(ranges) > MAX_LEAVE_RANGES:
		frappe.throw(_("Too many leave periods"))

	validate_combined_leave_balance(employee, leave_type, ranges)

	names = []
	for row in ranges:
		payload = {
			"doctype": "Leave Application",
			"employee": employee,
			"leave_type": leave_type,
			"from_date": row["from_date"],
			"to_date": row["to_date"],
			"description": str(description).strip(),
			"status": "Open",
			"posting_date": getdate(),
		}
		if leave_approver:
			payload["leave_approver"] = leave_approver
		if leave_approver_name:
			payload["leave_approver_name"] = leave_approver_name
		doc = frappe.get_doc(payload)
		doc.insert()
		names.append(doc.name)

	return {"ok": True, "names": names, "count": len(names)}
