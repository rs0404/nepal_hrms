# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint

from nepal_hrms.notifications.events import (
	DESTINATIONS,
	NOTIFICATION_EVENTS,
	catalog_for_client,
	notification_name,
	seeded_row_defaults,
)
from nepal_hrms.notifications.raven_guard import raven_available

EMPLOYEE_JINJA = '{{ frappe.db.get_value("Employee", doc.employee, "user_id") or "" }}'
REPORTS_TO_JINJA = (
	'{{ frappe.db.get_value("Employee",'
	' frappe.db.get_value("Employee", doc.employee, "reports_to") or "-",'
	' "user_id") or "" }}'
)
APPROVER_JINJA = (
	'{{ doc.get("leave_approver") or'
	' frappe.db.get_value("Employee", doc.employee, "leave_approver") or "" }}'
)

EMPLOYEE_USER = 'frappe.db.get_value("Employee", doc.employee, "user_id")'
REPORTS_TO_USER = (
	'frappe.db.get_value("Employee",'
	' frappe.db.get_value("Employee", doc.employee, "reports_to") or "-",'
	' "user_id")'
)
APPROVER_USER = (
	'(doc.get("leave_approver") or frappe.db.get_value("Employee", doc.employee, "leave_approver"))'
)

EMPLOYEE_CONDITION = f'frappe.db.exists("Raven User", {EMPLOYEE_USER} or "-")'
REPORTS_TO_CONDITION = (
	f"{REPORTS_TO_USER} and {REPORTS_TO_USER} != {EMPLOYEE_USER}"
	f' and frappe.db.exists("Raven User", {REPORTS_TO_USER} or "-")'
)


def seed_notification_rows_on_migrate():
	"""Persist catalog rows after migrate so the settings grid is not empty."""
	if not raven_available():
		return
	if not frappe.db.exists("DocType", "Nepal HRMS Raven Notification"):
		return
	try:
		existing = set(
			frappe.get_all(
				"Nepal HRMS Raven Notification",
				filters={"parent": "Nepal HRMS Settings"},
				pluck="event_key",
			)
		)
		idx = len(existing)
		for event in NOTIFICATION_EVENTS:
			if event["key"] in existing:
				continue
			idx += 1
			frappe.get_doc(
				{
					"doctype": "Nepal HRMS Raven Notification",
					"parent": "Nepal HRMS Settings",
					"parenttype": "Nepal HRMS Settings",
					"parentfield": "raven_notifications",
					"idx": idx,
					"event_key": event["key"],
					"event_label": event["label"],
					**seeded_row_defaults(event["key"]),
				}
			).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			title="Nepal HRMS Raven notification seed",
			message=frappe.get_traceback(),
		)


def seed_notification_rows(settings):
	"""Append missing catalog rows. No-op when Raven is not installed."""
	if not raven_available():
		return

	existing = {row.event_key for row in settings.get("raven_notifications") or [] if row.event_key}
	for event in NOTIFICATION_EVENTS:
		if event["key"] in existing:
			continue
		settings.append(
			"raven_notifications",
			{
				"event_key": event["key"],
				"event_label": event["label"],
				**seeded_row_defaults(event["key"]),
			},
		)


def sync_raven_notifications(settings):
	"""Create or update Raven Bot, Channel, and Document Notifications.

	Never raises to the settings form. Missing Raven is a silent skip.
	"""
	if not raven_available():
		return

	try:
		_sync(settings)
	except Exception:
		frappe.log_error(
			title="Nepal HRMS Raven notification sync",
			message=frappe.get_traceback(with_context=True),
		)


def _existing_channel(name):
	name = (name or "").strip()
	if name and frappe.db.exists("Raven Channel", name):
		return frappe.get_doc("Raven Channel", name)
	return None


def _row_needs_default_channel(row):
	return cint(row.enabled) and cint(row.send_to_channel) and not (row.get("channel") or "").strip()


def _channel_for_row(row, default_channel):
	if not row:
		return default_channel
	return _existing_channel(row.get("channel")) or default_channel


def _sync(settings):
	rows = {row.event_key: row for row in settings.get("raven_notifications") or []}
	want_default_channel = any(_row_needs_default_channel(row) for row in rows.values())
	want_any_channel = any(cint(row.enabled) and cint(row.send_to_channel) for row in rows.values())
	want_dm = any(
		cint(row.enabled)
		and (cint(row.send_to_employee) or cint(row.send_to_reports_to) or cint(row.send_to_approver))
		for row in rows.values()
	)

	bot = None
	default_channel = None
	if want_any_channel or want_dm:
		bot = _resolve_bot(settings)
	if want_default_channel and bot:
		default_channel = _resolve_channel(settings)

	if bot:
		settings.db_set("raven_bot", bot.name, update_modified=False)
	if default_channel:
		settings.db_set("raven_channel", default_channel.name, update_modified=False)
		if default_channel.workspace:
			settings.db_set("raven_workspace", default_channel.workspace, update_modified=False)

	used_channels = {}
	for event in NOTIFICATION_EVENTS:
		row = rows.get(event["key"])
		dedupe_reports_to = bool(row and cint(row.enabled) and cint(row.send_to_reports_to))
		row_channel = None
		if row and cint(row.enabled) and cint(row.send_to_channel):
			row_channel = _channel_for_row(row, default_channel)
			if row_channel:
				used_channels[row_channel.name] = row_channel
		for dest_slug, flag, dest_kind in DESTINATIONS:
			enabled = bool(row and cint(row.enabled) and cint(row.get(flag)))
			if dest_kind == "channel" and not row_channel:
				enabled = False
			if dest_kind != "channel" and not bot:
				enabled = False
			_upsert_notification(
				event=event,
				dest_slug=dest_slug,
				dest_kind=dest_kind,
				enabled=enabled,
				bot_name=bot.name if bot else None,
				channel_name=row_channel.name if row_channel else None,
				message=_row_message(row, event),
				dedupe_reports_to=dedupe_reports_to,
			)

	if bot:
		for channel in used_channels.values():
			_add_bot_and_role_members(bot, channel, settings)


def _row_message(row, event):
	custom = (row.message or "").strip() if row else ""
	return custom or event["message"]


def _resolve_bot(settings):
	if settings.raven_bot_source == "Existing Bot":
		name = (settings.raven_bot or "").strip()
		if name and frappe.db.exists("Raven Bot", name):
			return frappe.get_doc("Raven Bot", name)
		return None

	name = (settings.new_raven_bot_name or "Nepal HRMS").strip()
	if frappe.db.exists("Raven Bot", name):
		return frappe.get_doc("Raven Bot", name)

	bot = frappe.get_doc(
		{
			"doctype": "Raven Bot",
			"bot_name": name,
			"description": "Attendance notifications from Nepal HRMS",
		}
	)
	bot.insert(ignore_permissions=True)
	return bot


def _default_workspace():
	if frappe.db.exists("Raven Workspace", "Raven"):
		return "Raven"
	workspaces = frappe.get_all("Raven Workspace", pluck="name", limit=1, order_by="creation asc")
	return workspaces[0] if workspaces else None


def _channel_docname(workspace, channel_name):
	return (
		str(workspace).lower().replace(" ", "-")
		+ "-"
		+ str(channel_name).strip().lower().replace(" ", "-")
	)


def _resolve_channel(settings):
	if settings.raven_channel_source == "Existing Channel":
		name = (settings.raven_channel or "").strip()
		if name and frappe.db.exists("Raven Channel", name):
			return frappe.get_doc("Raven Channel", name)
		return None

	workspace = (settings.raven_workspace or "").strip() or _default_workspace()
	if not workspace:
		return None

	channel_name = (settings.new_raven_channel_name or "hr-attendance").strip()
	channel_type = settings.new_raven_channel_type or "Private"
	slug = channel_name.strip().lower().replace(" ", "-")
	docname = _channel_docname(workspace, slug)

	if frappe.db.exists("Raven Channel", docname):
		return frappe.get_doc("Raven Channel", docname)

	found = frappe.db.get_value(
		"Raven Channel",
		{"channel_name": slug, "workspace": workspace, "is_direct_message": 0},
	)
	if found:
		return frappe.get_doc("Raven Channel", found)

	channel = frappe.get_doc(
		{
			"doctype": "Raven Channel",
			"channel_name": channel_name,
			"channel_description": "Nepal HRMS attendance notifications",
			"type": channel_type,
			"workspace": workspace,
		}
	)
	channel.insert(ignore_permissions=True)
	return channel


def _add_bot_and_role_members(bot, channel, settings):
	if bot:
		bot.add_to_channel(channel.name)

	roles = [row.role for row in settings.get("raven_channel_roles") or [] if row.role]
	if not roles:
		return

	user_names = frappe.get_all(
		"Has Role",
		filters={"role": ["in", roles], "parenttype": "User"},
		pluck="parent",
	)
	if not user_names:
		return

	user_names = frappe.get_all(
		"User",
		filters={"name": ["in", user_names], "enabled": 1},
		pluck="name",
	)
	if not user_names:
		return

	raven_users = frappe.get_all(
		"Raven User",
		filters={"name": ["in", user_names], "enabled": 1, "type": "User"},
		pluck="name",
	)
	if raven_users:
		channel.add_members(raven_users)


def _combine_conditions(*parts):
	cleaned = [part.strip() for part in parts if part and str(part).strip()]
	if not cleaned:
		return ""
	if len(cleaned) == 1:
		return cleaned[0]
	return " and ".join(f"({part})" for part in cleaned)


def _approver_condition(dedupe_reports_to):
	parts = [
		APPROVER_USER,
		f"{APPROVER_USER} != {EMPLOYEE_USER}",
		f'frappe.db.exists("Raven User", {APPROVER_USER} or "-")',
	]
	if dedupe_reports_to:
		parts.append(f"{APPROVER_USER} != {REPORTS_TO_USER}")
	return " and ".join(parts)


def _recipient(dest_kind, channel_name):
	if dest_kind == "channel":
		return {
			"channel_type": "Channel",
			"variable_type": "Static",
			"value": channel_name,
		}
	jinja = {
		"employee": EMPLOYEE_JINJA,
		"reports_to": REPORTS_TO_JINJA,
		"approver": APPROVER_JINJA,
	}[dest_kind]
	return {
		"channel_type": "User",
		"variable_type": "Jinja",
		"value": jinja,
	}


def _dm_condition(dest_kind, dedupe_reports_to):
	if dest_kind == "employee":
		return EMPLOYEE_CONDITION
	if dest_kind == "reports_to":
		return REPORTS_TO_CONDITION
	if dest_kind == "approver":
		return _approver_condition(dedupe_reports_to)
	return ""


def _upsert_notification(event, dest_slug, dest_kind, enabled, bot_name, channel_name, message, dedupe_reports_to):
	name = notification_name(event["key"], dest_slug)
	exists = frappe.db.exists("Raven Document Notification", name)

	if not enabled:
		if exists:
			current = frappe.db.get_value("Raven Document Notification", name, "enabled")
			if cint(current):
				frappe.db.set_value(
					"Raven Document Notification",
					name,
					"enabled",
					0,
					update_modified=False,
				)
				frappe.cache().hdel("raven_doc_notifications", event["document_type"])
		return

	if dest_kind == "channel" and not channel_name:
		return
	if not bot_name:
		return

	condition = _combine_conditions(
		event.get("condition"),
		_dm_condition(dest_kind, dedupe_reports_to) if dest_kind != "channel" else "",
	)
	recipient = _recipient(dest_kind, channel_name)

	if exists:
		doc = frappe.get_doc("Raven Document Notification", name)
		doc.enabled = 1
		doc.sender = bot_name
		doc.send_alert_on = event["send_alert_on"]
		doc.document_type = event["document_type"]
		doc.do_not_attach_doc = 0
		doc.condition = condition
		doc.message = message
		doc.set("recipients", [])
		doc.append("recipients", recipient)
		doc.save(ignore_permissions=True)
		return

	doc = frappe.get_doc(
		{
			"doctype": "Raven Document Notification",
			"notification_name": name,
			"enabled": 1,
			"sender": bot_name,
			"send_alert_on": event["send_alert_on"],
			"document_type": event["document_type"],
			"do_not_attach_doc": 0,
			"condition": condition,
			"message": message,
			"recipients": [recipient],
		}
	)
	doc.insert(ignore_permissions=True)


@frappe.whitelist()
def get_notification_event_catalog():
	if not raven_available():
		return []
	return catalog_for_client()
