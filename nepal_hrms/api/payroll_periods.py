"""Payroll periods for the PWA's salary slip filter.

Sites that have customised Payroll Period's role permissions often leave the
Employee role with only "select", and select returns names without dates. The
PWA needs the dates to filter slips, so it asks here: the logged-in employee
gets their own company's periods, name and dates only.
"""

import frappe


@frappe.whitelist()
def get_my_payroll_periods():
	company = frappe.db.get_value(
		"Employee", {"user_id": frappe.session.user, "status": "Active"}, "company"
	)
	if not company:
		return []

	return frappe.get_all(
		"Payroll Period",
		filters={"company": company},
		fields=["name", "start_date", "end_date"],
		order_by="start_date desc",
	)
