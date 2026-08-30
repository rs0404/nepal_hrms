# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Bulk assign Attendance Policy Escape rows (one per employee)."""

import frappe
from frappe import _
from frappe.utils import cint, getdate

from nepal_hrms.nepal_hrms.doctype.attendance_policy_escape.attendance_policy_escape import (
	_ranges_overlap,
)


def _parse_employees(employees):
	if not employees:
		return []
	if isinstance(employees, str):
		try:
			parsed = frappe.parse_json(employees)
		except Exception:
			parsed = [p.strip() for p in employees.split(",") if p.strip()]
		if isinstance(parsed, str):
			return [parsed]
		if isinstance(parsed, list):
			return [str(x).strip() for x in parsed if str(x).strip()]
		return []
	if isinstance(employees, (list, tuple)):
		return [str(x).strip() for x in employees if str(x).strip()]
	return []


@frappe.whitelist()
def bulk_assign_attendance_policy_escapes(
	employees=None,
	from_date=None,
	to_date=None,
	escape_sandwich=0,
	escape_late_early=0,
	escape_continuous_lwp_gross=0,
	escape_absent_gross=0,
	escape_applications=0,
	reason=None,
	is_active=1,
):
	"""Create one Attendance Policy Escape per employee. Skip overlapping active rows."""
	frappe.has_permission("Attendance Policy Escape", "create", throw=True)

	emp_list = _parse_employees(employees)
	if not emp_list:
		frappe.throw(_("Select at least one employee"))

	if len(emp_list) > 200:
		frappe.throw(_("Too many employees ({0}). Select at most 200.").format(len(emp_list)))

	flags = {
		"escape_sandwich": cint(escape_sandwich),
		"escape_late_early": cint(escape_late_early),
		"escape_continuous_lwp_gross": cint(escape_continuous_lwp_gross),
		"escape_absent_gross": cint(escape_absent_gross),
		"escape_applications": cint(escape_applications),
	}
	if not any(flags.values()):
		frappe.throw(_("Select at least one escape rule"))

	if from_date and to_date and getdate(to_date) < getdate(from_date):
		frappe.throw(_("To Date cannot be before From Date"))

	created = []
	skipped = []

	for emp in emp_list:
		if not frappe.db.exists("Employee", emp):
			skipped.append({"employee": emp, "reason": _("Employee not found")})
			continue

		if cint(is_active):
			others = frappe.get_all(
				"Attendance Policy Escape",
				filters={"employee": emp, "is_active": 1},
				fields=["name", "from_date", "to_date"],
			)
			overlap = next(
				(
					o
					for o in others
					if _ranges_overlap(from_date, to_date, o.from_date, o.to_date)
				),
				None,
			)
			if overlap:
				skipped.append(
					{
						"employee": emp,
						"employee_name": frappe.db.get_value("Employee", emp, "employee_name"),
						"reason": _("Overlaps active escape {0}").format(overlap.name),
					}
				)
				continue

		doc = frappe.get_doc(
			{
				"doctype": "Attendance Policy Escape",
				"employee": emp,
				"from_date": from_date or None,
				"to_date": to_date or None,
				"is_active": 1 if cint(is_active) else 0,
				"reason": reason,
				**flags,
			}
		)
		doc.insert(ignore_permissions=False)
		created.append(
			{
				"name": doc.name,
				"employee": emp,
				"employee_name": doc.employee_name,
			}
		)

	return {
		"ok": 1,
		"created_count": len(created),
		"skipped_count": len(skipped),
		"created": created,
		"skipped": skipped,
	}
