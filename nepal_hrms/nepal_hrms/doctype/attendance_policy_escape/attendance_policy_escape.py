# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate


ESCAPE_FLAGS = (
	"escape_sandwich",
	"escape_late_early",
	"escape_continuous_lwp_gross",
	"escape_absent_gross",
	"escape_applications",
	"escape_attendance_deduction",
	"escape_ssf_earned_scaling",
	"allow_self_approval",
	"allow_approve_all",
)


def _ranges_overlap(a_from, a_to, b_from, b_to):
	"""Open-ended None bounds; inclusive date overlap."""
	a_start = getdate(a_from) if a_from else None
	a_end = getdate(a_to) if a_to else None
	b_start = getdate(b_from) if b_from else None
	b_end = getdate(b_to) if b_to else None
	if a_start and b_end and a_start > b_end:
		return False
	if b_start and a_end and b_start > a_end:
		return False
	return True


class AttendancePolicyEscape(Document):
	def validate(self):
		self._set_defaults_from_employee()
		self._validate_dates()
		self._validate_flags()
		self._validate_approval_grants()
		self._validate_no_overlap()

	def on_update(self):
		self._clear_escape_cache()

	def on_trash(self):
		self._clear_escape_cache()

	def _set_defaults_from_employee(self):
		if not self.employee:
			return
		emp = frappe.db.get_value(
			"Employee", self.employee, ["employee_name", "department", "company"], as_dict=True
		)
		if not emp:
			return
		self.employee_name = emp.employee_name
		self.department = emp.department
		if not self.company:
			self.company = emp.company

	def _validate_dates(self):
		if self.from_date and self.to_date and getdate(self.to_date) < getdate(self.from_date):
			frappe.throw(_("To Date cannot be before From Date"))

	def _validate_flags(self):
		if not any(cint(self.get(f)) for f in ESCAPE_FLAGS):
			frappe.throw(_("Select at least one escape rule"))

	# Approval grants, and the fields that decide who holds one and when.
	GRANTS = {"allow_approve_all": "Allow Approving Everyone", "allow_self_approval": "Allow Self-Approval"}
	GRANT_FIELDS = ("employee", "is_active", "from_date", "to_date")

	def _validate_approval_grants(self):
		"""Approval grants are System Manager's to give, move or extend.

		The fields are permlevel 1, but an HR Manager can still edit the rest of
		the row: point it at another employee (themself), stretch its dates,
		reactivate it. Any of those on a row carrying a grant needs System Manager
		too.
		"""
		if "System Manager" in frappe.get_roles():
			return
		before = self.get_doc_before_save()
		for flag, label in self.GRANTS.items():
			carries_grant = cint(self.get(flag)) or (before and cint(before.get(flag)))
			if not carries_grant:
				continue
			if self.is_new() or any(
				str(self.get(f) or "") != str(before.get(f) or "") for f in (flag, *self.GRANT_FIELDS)
			):
				frappe.throw(
					_("Only a System Manager can set {0}, or change who holds it and when.").format(_(label)),
					frappe.PermissionError,
				)

	def _validate_no_overlap(self):
		if not cint(self.is_active) or not self.employee:
			return
		others = frappe.get_all(
			"Attendance Policy Escape",
			filters={
				"employee": self.employee,
				"is_active": 1,
				"name": ["!=", self.name or ""],
			},
			fields=["name", "from_date", "to_date"],
		)
		for row in others:
			if _ranges_overlap(self.from_date, self.to_date, row.from_date, row.to_date):
				frappe.throw(
					_(
						"Active escape {0} already overlaps this date range for {1}. "
						"Deactivate it or adjust dates, and consolidate flags on one row when possible."
					).format(row.name, self.employee_name or self.employee)
				)

	def _clear_escape_cache(self):
		from nepal_hrms.custom_code.policy_escape import clear_policy_escape_cache

		clear_policy_escape_cache(self.employee)
