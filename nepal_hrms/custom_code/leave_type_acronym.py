# -*- coding: utf-8 -*-
"""3-letter acronyms for leave types on attendance sheet pills."""

from __future__ import annotations

import re

import frappe

# Preferred acronyms (max 3 letters)
CANONICAL_ACRONYMS = {
	"Leave Without Pay": "LWP",
	"Sick Leave": "SL",
	"Annual/Home Leave": "AHL",
	"Annual Leave": "AL",
	"Casual Leave": "CL",
	"Compensatory Off": "CO",
	"Marriage Leave": "ML",
	"Maternity Leave": "MTL",
	"Paternity Leave": "PTL",
	"Bereavement Leave": "BL",
}


def format_leave_type_acronym(
	leave_type: str | None, custom_acronym: str | None = None
) -> str:
	if not leave_type:
		return "Lv"
	name = (leave_type or "").strip()
	if not name:
		return "Lv"
	if name in CANONICAL_ACRONYMS:
		return CANONICAL_ACRONYMS[name]
	if custom_acronym:
		return str(custom_acronym).strip().upper()[:3]

	# Initials from words (slashes/hyphens split like words)
	parts = re.split(r"[\s/\-]+", name)
	letters = [p[0] for p in parts if p]
	if len(letters) >= 2:
		return "".join(letters).upper()[:3]
	return name.upper()[:3]


def leave_type_acronym(leave_type: str | None) -> str:
	if not leave_type:
		return "Lv"
	name = (leave_type or "").strip()
	if not name:
		return "Lv"
	if name in CANONICAL_ACRONYMS:
		return CANONICAL_ACRONYMS[name]

	custom = None
	if frappe.get_meta("Leave Type").has_field("custom_attendance_sheet_acronym"):
		custom = frappe.db.get_value("Leave Type", name, "custom_attendance_sheet_acronym")
	return format_leave_type_acronym(name, custom)


@frappe.whitelist()
def get_attendance_sheet_leave_legend():
	"""All leave types with acronyms for the attendance sheet legend dialog."""
	fields = ["name"]
	acronym_field = "custom_attendance_sheet_acronym"
	if frappe.get_meta("Leave Type").has_field(acronym_field):
		fields.append(acronym_field)
	rows = frappe.get_all("Leave Type", fields=fields, order_by="name")
	return [
		{
			"leave_type": row.name,
			"acronym": format_leave_type_acronym(
				row.name, getattr(row, acronym_field, None)
			),
		}
		for row in rows
	]
