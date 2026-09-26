# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Predefined attendance events synced to Raven Document Notification records."""

NOT_OOO = 'doc.get("custom_attendance_type") != "OOO Work"'
IS_OOO = 'doc.get("custom_attendance_type") == "OOO Work"'

NOTIFICATION_EVENTS = [
	{
		"key": "checkin_in",
		"label": "Check-in",
		"document_type": "Employee Checkin",
		"send_alert_on": "New Document",
		"condition": f'doc.log_type == "IN" and {NOT_OOO}',
		"message": "**Check-in:** {{ doc.employee_name }} at {{ doc.time }}",
	},
	{
		"key": "checkin_out",
		"label": "Check-out",
		"document_type": "Employee Checkin",
		"send_alert_on": "New Document",
		"condition": f'doc.log_type == "OUT" and {NOT_OOO}',
		"message": "**Check-out:** {{ doc.employee_name }} at {{ doc.time }}",
	},
	{
		"key": "checkin_ooo_in",
		"label": "OOO Check-in",
		"document_type": "Employee Checkin",
		"send_alert_on": "New Document",
		"condition": f'doc.log_type == "IN" and {IS_OOO}',
		"message": "**OOO Check-in:** {{ doc.employee_name }} at {{ doc.time }}",
	},
	{
		"key": "checkin_ooo_out",
		"label": "OOO Check-out",
		"document_type": "Employee Checkin",
		"send_alert_on": "New Document",
		"condition": f'doc.log_type == "OUT" and {IS_OOO}',
		"message": "**OOO Check-out:** {{ doc.employee_name }} at {{ doc.time }}",
	},
	{
		"key": "attendance_present",
		"label": "Attendance Present",
		"document_type": "Attendance",
		"send_alert_on": "Submit",
		"condition": 'doc.status == "Present"',
		"message": "**Present:** {{ doc.employee_name }} on {{ doc.attendance_date }}",
	},
	{
		"key": "attendance_absent",
		"label": "Attendance Absent",
		"document_type": "Attendance",
		"send_alert_on": "Submit",
		"condition": 'doc.status == "Absent"',
		"message": "**Absent:** {{ doc.employee_name }} on {{ doc.attendance_date }}",
	},
	{
		"key": "attendance_half_day",
		"label": "Attendance Half Day",
		"document_type": "Attendance",
		"send_alert_on": "Submit",
		"condition": 'doc.status == "Half Day"',
		"message": "**Half Day:** {{ doc.employee_name }} on {{ doc.attendance_date }}",
	},
	{
		"key": "attendance_on_leave",
		"label": "Attendance On Leave",
		"document_type": "Attendance",
		"send_alert_on": "Submit",
		"condition": 'doc.status == "On Leave"',
		"message": "**On Leave:** {{ doc.employee_name }} on {{ doc.attendance_date }}",
	},
	{
		"key": "attendance_wfh",
		"label": "Attendance Work From Home",
		"document_type": "Attendance",
		"send_alert_on": "Submit",
		"condition": 'doc.status == "Work From Home"',
		"message": "**Work From Home:** {{ doc.employee_name }} on {{ doc.attendance_date }}",
	},
	{
		"key": "attendance_late",
		"label": "Attendance Late Entry",
		"document_type": "Attendance",
		"send_alert_on": "Submit",
		"condition": "doc.late_entry == 1",
		"message": "**Late Entry:** {{ doc.employee_name }} on {{ doc.attendance_date }}{% if doc.custom_late_mins %} ({{ doc.custom_late_mins }} min){% endif %}",
	},
	{
		"key": "attendance_early",
		"label": "Attendance Early Exit",
		"document_type": "Attendance",
		"send_alert_on": "Submit",
		"condition": "doc.early_exit == 1",
		"message": "**Early Exit:** {{ doc.employee_name }} on {{ doc.attendance_date }}{% if doc.custom_early_mins %} ({{ doc.custom_early_mins }} min){% endif %}",
	},
	{
		"key": "attendance_cancelled",
		"label": "Attendance Cancelled",
		"document_type": "Attendance",
		"send_alert_on": "Cancel",
		"condition": "",
		"message": "**Attendance Cancelled:** {{ doc.employee_name }} on {{ doc.attendance_date }}",
	},
	{
		"key": "attendance_request_new",
		"label": "Attendance Request Created",
		"document_type": "Attendance Request",
		"send_alert_on": "New Document",
		"condition": "",
		"message": "**Attendance Request:** {{ doc.employee_name }} from {{ doc.from_date }}{% if doc.to_date %} to {{ doc.to_date }}{% endif %}",
	},
	{
		"key": "attendance_request_submit",
		"label": "Attendance Request Submitted",
		"document_type": "Attendance Request",
		"send_alert_on": "Submit",
		"condition": "",
		"message": "**Attendance Request Submitted:** {{ doc.employee_name }} from {{ doc.from_date }}{% if doc.to_date %} to {{ doc.to_date }}{% endif %}",
	},
	{
		"key": "attendance_request_cancel",
		"label": "Attendance Request Cancelled",
		"document_type": "Attendance Request",
		"send_alert_on": "Cancel",
		"condition": "",
		"message": "**Attendance Request Cancelled:** {{ doc.employee_name }} from {{ doc.from_date }}",
	},
	{
		"key": "late_entry_app_new",
		"label": "Late Entry Application Created",
		"document_type": "Late Entry Application",
		"send_alert_on": "New Document",
		"condition": "",
		"message": "**Late Entry Application:** {{ doc.employee_name }} on {{ doc.attendance_date }}",
	},
	{
		"key": "late_entry_app_submit",
		"label": "Late Entry Application Submitted",
		"document_type": "Late Entry Application",
		"send_alert_on": "Submit",
		"condition": "",
		"message": "**Late Entry Application Submitted:** {{ doc.employee_name }} on {{ doc.attendance_date }}",
	},
	{
		"key": "late_entry_app_cancel",
		"label": "Late Entry Application Cancelled",
		"document_type": "Late Entry Application",
		"send_alert_on": "Cancel",
		"condition": "",
		"message": "**Late Entry Application Cancelled:** {{ doc.employee_name }} on {{ doc.attendance_date }}",
	},
	{
		"key": "early_exit_app_new",
		"label": "Early Exit Application Created",
		"document_type": "Early Exit Application",
		"send_alert_on": "New Document",
		"condition": "",
		"message": "**Early Exit Application:** {{ doc.employee_name }} on {{ doc.attendance_date }}",
	},
	{
		"key": "early_exit_app_submit",
		"label": "Early Exit Application Submitted",
		"document_type": "Early Exit Application",
		"send_alert_on": "Submit",
		"condition": "",
		"message": "**Early Exit Application Submitted:** {{ doc.employee_name }} on {{ doc.attendance_date }}",
	},
	{
		"key": "early_exit_app_cancel",
		"label": "Early Exit Application Cancelled",
		"document_type": "Early Exit Application",
		"send_alert_on": "Cancel",
		"condition": "",
		"message": "**Early Exit Application Cancelled:** {{ doc.employee_name }} on {{ doc.attendance_date }}",
	},
	{
		"key": "ooo_app_new",
		"label": "Out of Office Application Created",
		"document_type": "Out of Office Application",
		"send_alert_on": "New Document",
		"condition": "",
		"message": "**Out of Office Application:** {{ doc.employee_name }} on {{ doc.attendance_date }}",
	},
	{
		"key": "ooo_app_submit",
		"label": "Out of Office Application Submitted",
		"document_type": "Out of Office Application",
		"send_alert_on": "Submit",
		"condition": "",
		"message": "**Out of Office Application Submitted:** {{ doc.employee_name }} on {{ doc.attendance_date }}",
	},
	{
		"key": "ooo_app_cancel",
		"label": "Out of Office Application Cancelled",
		"document_type": "Out of Office Application",
		"send_alert_on": "Cancel",
		"condition": "",
		"message": "**Out of Office Application Cancelled:** {{ doc.employee_name }} on {{ doc.attendance_date }}",
	},
	{
		"key": "leave_app_new",
		"label": "Leave Application Created",
		"document_type": "Leave Application",
		"send_alert_on": "New Document",
		"condition": "",
		"message": "**Leave Application:** {{ doc.employee_name }} ({{ doc.leave_type }}) from {{ doc.from_date }} to {{ doc.to_date }}",
	},
	{
		"key": "leave_app_submit",
		"label": "Leave Application Submitted",
		"document_type": "Leave Application",
		"send_alert_on": "Submit",
		"condition": "",
		"message": "**Leave Application Submitted:** {{ doc.employee_name }} ({{ doc.leave_type }}) from {{ doc.from_date }} to {{ doc.to_date }}",
	},
	{
		"key": "leave_app_cancel",
		"label": "Leave Application Cancelled",
		"document_type": "Leave Application",
		"send_alert_on": "Cancel",
		"condition": "",
		"message": "**Leave Application Cancelled:** {{ doc.employee_name }} ({{ doc.leave_type }}) from {{ doc.from_date }} to {{ doc.to_date }}",
	},
	{
		# No automatic hook fires this one. It exists so the PWA's "remind the
		# approver" button has a row to read recipients and wording from, the
		# same as every other application type.
		"key": "shift_request_new",
		"label": "Shift Request Created",
		"document_type": "Shift Request",
		"send_alert_on": "New Document",
		"condition": "",
		"message": "**Shift Request:** {{ doc.employee_name }} ({{ doc.shift_type }}) from {{ doc.from_date }}{% if doc.to_date %} to {{ doc.to_date }}{% endif %}",
	},
	{
		"key": "policy_escape_new",
		"label": "Attendance Policy Escape Created",
		"document_type": "Attendance Policy Escape",
		"send_alert_on": "New Document",
		"condition": "",
		"message": "**Attendance Policy Escape:** {{ doc.employee_name }} from {{ doc.from_date }}{% if doc.to_date %} to {{ doc.to_date }}{% endif %}",
	},
]

EVENT_KEYS = [event["key"] for event in NOTIFICATION_EVENTS]
EVENT_BY_KEY = {event["key"]: event for event in NOTIFICATION_EVENTS}

DESTINATIONS = (
	("channel", "send_to_channel", "channel"),
	("employee", "send_to_employee", "employee"),
	("reports-to", "send_to_reports_to", "reports_to"),
	("approver", "send_to_approver", "approver"),
)


# Events a new site starts with switched on. An application sitting unseen is
# the problem these notifications exist to solve, so the ones that reach an
# approver are on by default; everything else stays opt-in, because a site that
# has not asked for check-in or attendance traffic should not suddenly get it.
# The master switch in Nepal HRMS Settings still gates the lot.
DEFAULT_ON_EVENTS = frozenset(
	{
		"late_entry_app_new",
		"early_exit_app_new",
		"ooo_app_new",
		"attendance_request_new",
		"leave_app_new",
		"shift_request_new",
	}
)


def seeded_row_defaults(event_key):
	"""Checkbox state a freshly seeded settings row starts with.

	Approver and PWA together, because either alone sends nothing: the row needs
	a channel and a recipient before it delivers anything at all.
	"""
	on = event_key in DEFAULT_ON_EVENTS
	return {
		"enabled": 1 if on else 0,
		"send_to_channel": 0,
		"send_to_employee": 0,
		"send_to_reports_to": 0,
		"send_to_approver": 1 if on else 0,
		"send_to_pwa": 1 if on else 0,
	}


def notification_name(event_key, dest_slug):
	return f"NH-{event_key}-{dest_slug}"


def catalog_for_client():
	return [{"key": event["key"], "label": event["label"]} for event in NOTIFICATION_EVENTS]
