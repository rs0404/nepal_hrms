import frappe

from nepal_hrms.custom_field import create_custom_fields


ANNUAL_HOME_NAMES = {
	"Annual Home Leave",
	"Annual/Home Leave",
	"archived home leave",
}
SICK_NAMES = {
	"Annual Sick Leave",
	"Sick Leave",
}


def execute():
	create_custom_fields()
	meta = frappe.get_meta("Leave Type")
	fieldname = "custom_attendance_sheet_leave_group"
	if not meta.has_field(fieldname):
		return

	for leave_type in frappe.get_all(
		"Leave Type", fields=["name", "is_lwp", fieldname]
	):
		if leave_type.get(fieldname):
			continue
		if leave_type.name in ANNUAL_HOME_NAMES:
			group = "Annual/Home"
		elif leave_type.name in SICK_NAMES:
			group = "Sick"
		elif not leave_type.is_lwp:
			group = "Other Paid"
		else:
			continue
		frappe.db.set_value(
			"Leave Type", leave_type.name, fieldname, group, update_modified=False
		)
