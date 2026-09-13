import frappe
from frappe.utils import getdate


def get_data(data=None):
	"""Extend Attendance connections. Must accept `data=` from override_doctype_dashboards."""
	data = frappe._dict(data or {})
	data.fieldname = data.fieldname or "attendance"
	# Prefer our counter so Leave / Attendance Request include covering docs by date.
	data.method = "nepal_hrms.overrides.attendance_dashboard.get_open_count"

	extra_items = [
		"Employee Checkin",
		"Leave Application",
		"Attendance Request",
		"Late Entry Application",
		"Early Exit Application",
		"Out of Office Application",
	]

	# Use internal_and_external_links (not internal_links) so the Connections "+"
	# button still renders. Counts still come from Attendance.leave_application /
	# attendance_request, plus covering docs by employee + date.
	iae = frappe._dict(data.internal_and_external_links or {})
	iae["Leave Application"] = "leave_application"
	iae["Attendance Request"] = "attendance_request"
	data.internal_and_external_links = iae

	# Avoid hiding "+" via the form_links template check on internal_links.
	internal_links = frappe._dict(data.internal_links or {})
	internal_links.pop("Leave Application", None)
	internal_links.pop("Attendance Request", None)
	data.internal_links = internal_links

	transactions = list(data.transactions or [])
	if not transactions:
		data.transactions = [{"label": "Attendance Links", "items": extra_items}]
		return data

	first = frappe._dict(transactions[0])
	first["items"] = list(dict.fromkeys(list(first.get("items") or []) + extra_items))
	transactions[0] = first
	data.transactions = transactions
	return data


@frappe.whitelist()
def get_open_count(doctype, name, items=None):
	"""Like frappe.desk.notifications.get_open_count, with richer Leave/AR counts."""
	from frappe.desk.notifications import (
		get_external_links,
		get_internal_links,
		_get_linked_document_counts,
	)

	if doctype != "Attendance":
		return _get_linked_document_counts(doctype, name, items)

	doc = frappe.get_doc(doctype, name)
	doc.check_permission()
	links = doc.meta.get_dashboard_data()

	if items is None:
		items = []
		for group in links.transactions or []:
			items.extend(group.get("items") or [])
	elif not isinstance(items, list):
		import json

		items = json.loads(items)

	out = {"external_links_found": [], "internal_links_found": []}

	for d in items:
		internal_link_for_doctype = (links.get("internal_links") or {}).get(d) or (
			links.get("internal_and_external_links") or {}
		).get(d)

		if internal_link_for_doctype:
			internal = get_internal_links(doc, internal_link_for_doctype, d)
			if d in ("Leave Application", "Attendance Request"):
				_merge_covering_applications(doc, d, internal)
			if internal["count"]:
				out["internal_links_found"].append(internal)
			else:
				try:
					out["external_links_found"].append(get_external_links(d, name, links))
				except Exception:
					out["external_links_found"].append(
						{"doctype": d, "open_count": 0, "count": 0}
					)
		else:
			out["external_links_found"].append(get_external_links(d, name, links))

	result = {"count": out}
	module = frappe.get_meta_module(doctype)
	if hasattr(module, "get_timeline_data"):
		result["timeline_data"] = module.get_timeline_data(doctype, name)
	return result


def _merge_covering_applications(attendance, link_doctype, internal):
	"""Add Leave Application / Attendance Request covering this employee+date."""
	employee = attendance.employee
	day = getdate(attendance.attendance_date)
	if not employee or not day:
		return

	names = list(internal.get("names") or [])
	if link_doctype == "Leave Application":
		rows = frappe.get_all(
			"Leave Application",
			filters={
				"employee": employee,
				"docstatus": ["<", 2],
				"from_date": ["<=", day],
				"to_date": [">=", day],
			},
			pluck="name",
		)
	else:
		rows = frappe.get_all(
			"Attendance Request",
			filters={
				"employee": employee,
				"docstatus": ["<", 2],
				"from_date": ["<=", day],
				"to_date": [">=", day],
			},
			pluck="name",
		)

	for name in rows:
		if name not in names:
			names.append(name)

	internal["names"] = names
	internal["count"] = len(names)
	internal["open_count"] = 0
