# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Attendance Request: update existing same-day attendance even when shift names differ.

HRMS only matches Attendance by exact `shift`. Auto-attendance often uses the
assigned shift (e.g. Production Full Time) while the request may carry the
employee default (e.g. Full Time) or be blank. Overlapping / duplicate
Attendance errors then block submit for an Absent day that already has a row.

Also supports Open / Approved / Rejected approval status with rejection reason.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import format_date, get_link_to_form, getdate

from hrms.hr.doctype.attendance.attendance import has_overlapping_timings
from hrms.hr.doctype.attendance_request.attendance_request import AttendanceRequest


def _can_approve_attendance_request(employee: str) -> bool:
	"""Leave Approver of the employee, or HR / System Manager."""
	user = frappe.session.user
	roles = set(frappe.get_roles(user))
	if roles & {"HR Manager", "HR User", "System Manager", "Administrator"}:
		return True
	approver = frappe.db.get_value("Employee", employee, "leave_approver")
	return bool(approver and approver == user)


class CustomAttendanceRequest(AttendanceRequest):
	def validate(self):
		super().validate()
		if not self.status:
			self.status = "Open"
		if self.status == "Rejected" and not (self.custom_rejection_reason or "").strip():
			frappe.throw(_("Rejection Reason is required when status is Rejected"))
		if self.status != "Rejected":
			self.custom_rejection_reason = None

	def before_submit(self):
		if self.status == "Rejected":
			frappe.throw(_("Cannot submit a Rejected Attendance Request"))
		# Submitting an Open request implies approval
		if self.status in (None, "", "Open"):
			self.status = "Approved"

	def get_attendance_doc(self, attendance_date: str):
		"""Prefer exact shift match; else reuse same-day attendance (overlapping / only row)."""
		day = getdate(attendance_date)
		base = {
			"employee": self.employee,
			"attendance_date": day,
			"docstatus": ("!=", 2),
		}

		if self.shift:
			exact = frappe.db.exists("Attendance", {**base, "shift": self.shift})
			if exact:
				return frappe.get_doc("Attendance", exact)

		rows = frappe.get_all(
			"Attendance",
			filters=base,
			fields=["name", "shift", "status"],
			order_by="creation asc",
		)
		if not rows:
			return None

		# No shift on the request — update the day's attendance
		if not self.shift:
			return frappe.get_doc("Attendance", rows[0].name)

		for row in rows:
			existing_shift = row.shift
			if not existing_shift or has_overlapping_timings(self.shift, existing_shift):
				return frappe.get_doc("Attendance", row.name)

		# Single attendance that day (typical Absent / Present) — update it
		if len(rows) == 1:
			return frappe.get_doc("Attendance", rows[0].name)

		return None

	def create_or_update_attendance(self, date: str):
		"""Always update an existing same-day Attendance instead of inserting a duplicate."""
		doc = self.get_attendance_doc(date)
		status = self.get_attendance_status(date)

		# Safety net: any same-day row (HRMS empty-shift lookup misses assigned shifts)
		if not doc:
			name = frappe.db.exists(
				"Attendance",
				{
					"employee": self.employee,
					"attendance_date": getdate(date),
					"docstatus": ("!=", 2),
				},
			)
			if name:
				doc = frappe.get_doc("Attendance", name)

		if doc:
			old_status = doc.status
			updates = {"attendance_request": self.name}
			if old_status != status:
				updates["status"] = status
				if status == "Half Day":
					updates["half_day_status"] = "Absent"

			doc.db_set(updates, update_modified=True)

			if old_status != status:
				if status == "Half Day":
					text = _(
						"Changed the status from {0} to {1} and Status for Other Half to {2} via Attendance Request"
					).format(frappe.bold(old_status), frappe.bold(status), frappe.bold("Absent"))
				else:
					text = _("Changed the status from {0} to {1} via Attendance Request").format(
						frappe.bold(old_status), frappe.bold(status)
					)
				doc.add_comment(comment_type="Info", text=text)
				frappe.msgprint(
					_("Updated status from {0} to {1} for date {2} in the attendance record {3}").format(
						frappe.bold(old_status),
						frappe.bold(status),
						frappe.bold(format_date(date)),
						get_link_to_form("Attendance", doc.name),
					),
					title=_("Attendance Updated"),
				)
			return

		# No existing row — create new (original HRMS path)
		doc = frappe.new_doc("Attendance")
		doc.employee = self.employee
		doc.attendance_date = date
		doc.shift = self.shift
		doc.company = self.company
		doc.attendance_request = self.name
		doc.status = status
		doc.half_day_status = "Absent" if status == "Half Day" else None
		doc.insert(ignore_permissions=True)
		doc.submit()


@frappe.whitelist()
def can_approve_attendance_request(employee=None, name=None):
	"""Whether current user may approve/reject this Attendance Request."""
	if name and not employee:
		employee = frappe.db.get_value("Attendance Request", name, "employee")
	if not employee:
		return False
	return _can_approve_attendance_request(employee)


@frappe.whitelist()
def set_attendance_request_approval(name, status, rejection_reason=None):
	"""Approve or reject an Attendance Request from bshrms (with optional reason)."""
	status = (status or "").strip()
	if status not in ("Approved", "Rejected"):
		frappe.throw(_("Invalid status"))

	doc = frappe.get_doc("Attendance Request", name)
	if doc.docstatus != 0:
		frappe.throw(_("Only draft Attendance Requests can be approved or rejected"))

	if not _can_approve_attendance_request(doc.employee):
		frappe.throw(_("Not permitted to approve or reject this Attendance Request"), frappe.PermissionError)

	if status == "Rejected":
		reason = (rejection_reason or "").strip()
		if not reason:
			frappe.throw(_("Rejection Reason is required"))
		doc.status = "Rejected"
		doc.custom_rejection_reason = reason
	else:
		doc.status = "Approved"
		doc.custom_rejection_reason = None

	doc.save(ignore_permissions=True)
	return {"name": doc.name, "status": doc.status}
