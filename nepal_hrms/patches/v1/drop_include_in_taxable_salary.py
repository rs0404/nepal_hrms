"""Remove the Include In Taxable Salary checkbox from Salary Component.

Nothing ever read it -- not this app, Nepal Compliance or Frappe HR. Income
tax follows the stock Is Tax Applicable checkbox, so a second box that looked
like it mattered only invited the wrong one to be ticked.
"""

import frappe


FIELDNAME = "include_in_taxable_salary"


def execute():
	name = frappe.db.get_value(
		"Custom Field", {"dt": "Salary Component", "fieldname": FIELDNAME}
	)
	if name:
		frappe.delete_doc("Custom Field", name, ignore_missing=True, force=True)
		frappe.clear_cache(doctype="Salary Component")
