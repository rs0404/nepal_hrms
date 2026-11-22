import frappe


def execute():
	"""HRMS 16 removed Upload Attendance; drop the BS date fields we had added to it."""
	if frappe.db.exists("DocType", "Upload Attendance"):
		return
	for name in frappe.get_all("Custom Field", filters={"dt": "Upload Attendance"}, pluck="name"):
		frappe.delete_doc("Custom Field", name, ignore_missing=True, force=True)
