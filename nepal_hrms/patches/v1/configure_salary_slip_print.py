import frappe


DEFAULT_ADDITIONAL_EARNINGS = ("Overtime", "Bonus", "Earning Adjustment")


def execute():
	if not frappe.db.exists("DocType", "Nepal HRMS Settings"):
		return

	settings = frappe.get_doc("Nepal HRMS Settings")
	if not settings.salary_slip_employee_id_field:
		settings.salary_slip_employee_id_field = "name"

	for fieldname in (
		"show_salary_slip_department",
		"show_salary_slip_branch",
		"show_salary_slip_pay_date",
		"show_salary_slip_bank_details",
	):
		settings.set(fieldname, 1)

	if not settings.get("salary_slip_additional_earning_components"):
		for component in DEFAULT_ADDITIONAL_EARNINGS:
			if frappe.db.exists("Salary Component", component):
				settings.append(
					"salary_slip_additional_earning_components",
					{"salary_component": component},
				)

	settings.flags.ignore_mandatory = True
	settings.save(ignore_permissions=True)

	if frappe.db.exists("Print Format", "Nepal Earned Salary Slip"):
		frappe.delete_doc(
			"Print Format",
			"Nepal Earned Salary Slip",
			force=True,
			ignore_permissions=True,
		)
