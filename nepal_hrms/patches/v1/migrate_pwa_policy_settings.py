import frappe


POLICY_FIELDS = {
	"custom_prevent_self_attendance_request_approval": "prevent_self_attendance_request_approval",
	"custom_prevent_self_cnr_application_approval": "prevent_self_cnr_application_approval",
	"custom_prevent_self_ooo_checkin_approval": "prevent_self_ooo_checkin_approval",
}

PWA_ROLE_FIELDS = (
	"pwa_live_board_roles",
	"pwa_leave_board_roles",
	"pwa_calendar_history_roles",
	"pwa_calendar_view_others_roles",
)


def execute():
	_copy_self_approval_policy()
	_copy_pwa_role_tables()


def _copy_self_approval_policy():
	if not frappe.db.exists("DocType", "HR Settings"):
		return

	source = frappe.db.get_singles_dict("HR Settings") or {}
	for old_field, new_field in POLICY_FIELDS.items():
		value = source.get(old_field)
		if value is not None:
			frappe.db.set_single_value("Nepal HRMS Settings", new_field, value)


def _copy_pwa_role_tables():
	if not (
		frappe.db.exists("DocType", "Nepal Compliance Role")
		and frappe.db.exists("DocType", "Nepal HRMS Role")
	):
		return

	for fieldname in PWA_ROLE_FIELDS:
		if frappe.db.exists(
			"Nepal HRMS Role",
			{"parent": "Nepal HRMS Settings", "parentfield": fieldname},
		):
			continue

		roles = frappe.get_all(
			"Nepal Compliance Role",
			filters={
				"parent": "Nepal Compliance Settings",
				"parentfield": fieldname,
				"parenttype": "Nepal Compliance Settings",
			},
			pluck="role",
			order_by="idx asc",
		)
		for idx, role in enumerate((role for role in roles if role), start=1):
			frappe.get_doc(
				{
					"doctype": "Nepal HRMS Role",
					"parent": "Nepal HRMS Settings",
					"parentfield": fieldname,
					"parenttype": "Nepal HRMS Settings",
					"idx": idx,
					"role": role,
				}
			).db_insert()
