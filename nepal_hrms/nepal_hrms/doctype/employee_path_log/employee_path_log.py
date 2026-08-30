# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EmployeePathLog(Document):
    def validate(self):
        """Validate that the employee exists and coordinates are valid."""
        if not self.employee:
            frappe.throw("Employee is required")

        if self.latitude and (self.latitude < -90 or self.latitude > 90):
            frappe.throw("Latitude must be between -90 and 90")

        if self.longitude and (self.longitude < -180 or self.longitude > 180):
            frappe.throw("Longitude must be between -180 and 180")

    def before_insert(self):
        """Set employee name from employee link."""
        if self.employee and not self.employee_name:
            self.employee_name = frappe.db.get_value("Employee", self.employee, "employee_name")
