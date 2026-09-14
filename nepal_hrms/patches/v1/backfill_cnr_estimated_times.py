import frappe


def execute():
	if frappe.db.has_column(
		"Late Entry Application", "estimated_late_entry_time"
	):
		frappe.db.sql(
			"""
			UPDATE `tabLate Entry Application`
			SET estimated_late_entry_time = late_entry_time
			WHERE estimated_late_entry_time IS NULL
				AND late_entry_time IS NOT NULL
			"""
		)

	if frappe.db.has_column(
		"Out of Office Application", "estimated_from_time"
	):
		frappe.db.sql(
			"""
			UPDATE `tabOut of Office Application`
			SET estimated_from_time = from_time
			WHERE estimated_from_time IS NULL
				AND from_time IS NOT NULL
			"""
		)

	if frappe.db.has_column(
		"Out of Office Application", "estimated_to_time"
	):
		frappe.db.sql(
			"""
			UPDATE `tabOut of Office Application`
			SET estimated_to_time = to_time
			WHERE estimated_to_time IS NULL
				AND to_time IS NOT NULL
			"""
		)
