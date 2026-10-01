"""Tick both deduction checkboxes on the Leave and Late Deduction components.

Its amount is taken out of earnings by the earned-salary pass and changes every
month, so it is neither a real deduction off net pay nor a tax exemption to
repeat for the rest of the year. Repeating one month's penalty for every
remaining month is what cut taxable income by about 11 times that penalty.

The fields are created here as well: patches run before after_migrate creates
custom fields, and a live site may take this patch without a full migrate.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from nepal_hrms.custom_field import SALARY_COMPONENT_DEDUCTION_FLAGS
from nepal_hrms.overrides.salary_slip import ATTENDANCE_DEDUCTION_COMPONENTS, _matches_component


def execute():
	create_custom_fields({"Salary Component": SALARY_COMPONENT_DEDUCTION_FLAGS}, update=True)

	for name in frappe.get_all("Salary Component", filters={"type": "Deduction"}, pluck="name"):
		if _matches_component(name, ATTENDANCE_DEDUCTION_COMPONENTS):
			frappe.db.set_value(
				"Salary Component",
				name,
				{"custom_taken_from_earnings": 1, "custom_skip_tax_projection": 1},
			)
