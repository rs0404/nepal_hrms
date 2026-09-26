# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Share an application with its approver from the PWA.

Two small things the employee needs once a request is raised: a link they can
paste into a chat, and a nudge when the approver has not looked yet.

The nudge deliberately goes through notifications.pwa.notify rather than
writing a PWA Notification directly, so a manual reminder obeys exactly the
same Nepal HRMS Settings row as the automatic one -- master PWA switch, event
enabled, send_to_pwa, and the recipient boxes. That means the button has to be
able to say *in advance* whether a nudge would land, otherwise it would look
broken when the row is off; get_share_info answers that so the form can
disable the button and say why.

The link itself is built in the browser from the PWA router, not here: the
router already owns the doctype -> route mapping and the /hr base.
"""

import frappe
from frappe import _

from nepal_hrms.notifications.pwa import _approver_user, _settings_row, notify

# The application types the PWA lets an employee raise, and the "new document"
# event each one's reminder borrows.
APPROVER_EVENT = {
	"Late Entry Application": "late_entry_app_new",
	"Early Exit Application": "early_exit_app_new",
	"Out of Office Application": "ooo_app_new",
	"Attendance Request": "attendance_request_new",
	"Leave Application": "leave_app_new",
	"Shift Request": "shift_request_new",
}


def _readable(doctype, name):
	"""The document, or a clean permission error. Never leaks another employee's."""
	if doctype not in APPROVER_EVENT:
		frappe.throw(_("{0} cannot be shared from the app.").format(_(doctype)))

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	return doc


def _approver_label(user):
	if not user:
		return None
	return frappe.db.get_value("User", user, "full_name") or user


@frappe.whitelist()
def get_share_info(doctype: str, name: str) -> dict:
	"""Who would be nudged, and whether a nudge would actually reach them."""
	doc = _readable(doctype, name)

	approver = _approver_user(doc)
	row = _settings_row(APPROVER_EVENT[doctype])

	if not approver:
		reason = _("No approver is set for this request.")
	elif not row:
		reason = _("PWA notifications are off for this application type.")
	elif not row.get("send_to_approver"):
		reason = _("This notification is not configured to reach the approver.")
	elif approver == frappe.session.user:
		reason = _("You are the approver on this request.")
	else:
		reason = None

	return {
		"approver": approver,
		"approver_name": _approver_label(approver),
		"can_notify": reason is None,
		"reason": reason,
	}


@frappe.whitelist()
def notify_approver(doctype: str, name: str) -> dict:
	"""Send the approver the same PWA notification the document raised."""
	doc = _readable(doctype, name)

	info = get_share_info(doctype, name)
	if not info["can_notify"]:
		frappe.throw(info["reason"], title=_("Cannot notify"))

	sent = notify(APPROVER_EVENT[doctype], doc)
	if not sent:
		# notify() returns 0 for an empty render or a recipient list that
		# collapsed to nothing -- neither is worth a traceback, but the employee
		# must not be told a reminder went out when it did not.
		frappe.throw(
			_("Nothing was sent. Check the notification settings for this application type."),
			title=_("Cannot notify"),
		)

	return {"sent": sent, "approver_name": info["approver_name"]}
