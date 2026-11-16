# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""PWA Notification grants no role write, so the app cannot mark one read
through frappe.client.set_value. HRMS only offers "mark all"; this is one.
"""

import frappe


@frappe.whitelist(methods=["POST"])
def mark_notification_as_read(name):
	"""Mark one of the user's own notifications read. Someone else's is left alone."""
	frappe.db.set_value(
		"PWA Notification",
		{"name": name, "to_user": frappe.session.user, "read": 0},
		"read",
		1,
		update_modified=False,
	)
