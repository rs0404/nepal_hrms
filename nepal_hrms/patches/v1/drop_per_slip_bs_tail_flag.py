"""Remove the short-lived per-Salary-Slip BS tail checkbox.

The extension only ever applies to the fiscal year's first month, which the
calendar decides on its own. A per-slip override offered a choice that was
meaningless on every other month, so the rule lives in Nepal HRMS Settings alone.
"""

import frappe


FIELDNAME = "custom_extend_to_previous_bs_month_tail"


def execute():
	name = frappe.db.get_value(
		"Custom Field", {"dt": "Salary Slip", "fieldname": FIELDNAME}
	)
	if name:
		frappe.delete_doc("Custom Field", name, ignore_missing=True, force=True)
		frappe.clear_cache(doctype="Salary Slip")
