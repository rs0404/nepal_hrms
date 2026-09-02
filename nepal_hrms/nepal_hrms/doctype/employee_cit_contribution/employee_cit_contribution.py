# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class EmployeeCITContribution(Document):
	def validate(self):
		self._set_employee_details()
		self._validate_amount()
		self._validate_effective_date()
		self._validate_unique_effective_date()

	def _set_employee_details(self):
		employee = frappe.db.get_value(
			"Employee",
			self.employee,
			["employee_name", "department", "company", "date_of_joining", "relieving_date"],
			as_dict=True,
		)
		if not employee:
			frappe.throw(_("Employee {0} does not exist.").format(self.employee))

		self.employee_name = employee.employee_name
		self.department = employee.department
		self.company = employee.company
		self._employee_dates = employee

	def _validate_amount(self):
		if flt(self.monthly_amount) < 0:
			frappe.throw(_("Monthly CIT Amount cannot be negative. Use zero to stop contributions."))

	def _validate_effective_date(self):
		effective_from = getdate(self.effective_from)
		joining_date = (
			getdate(self._employee_dates.date_of_joining)
			if self._employee_dates.date_of_joining
			else None
		)
		relieving_date = (
			getdate(self._employee_dates.relieving_date)
			if self._employee_dates.relieving_date
			else None
		)

		if joining_date and effective_from < joining_date:
			frappe.throw(
				_("Effective From cannot be before the employee's joining date {0}.").format(
					frappe.format_value(joining_date, {"fieldtype": "Date"})
				)
			)
		if relieving_date and effective_from > relieving_date:
			frappe.throw(
				_("Effective From cannot be after the employee's relieving date {0}.").format(
					frappe.format_value(relieving_date, {"fieldtype": "Date"})
				)
			)

	def _validate_unique_effective_date(self):
		existing = frappe.db.get_value(
			"Employee CIT Contribution",
			{
				"employee": self.employee,
				"effective_from": self.effective_from,
				"docstatus": ("!=", 2),
				"name": ("!=", self.name or ""),
			},
			"name",
		)
		if existing:
			frappe.throw(
				_("CIT contribution {0} already exists for {1} from {2}.").format(
					frappe.bold(existing),
					frappe.bold(self.employee_name or self.employee),
					frappe.bold(frappe.format_value(self.effective_from, {"fieldtype": "Date"})),
				)
			)
