# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe


def get_data(data=None):
	"""Extend Attendance connections. Must accept `data=` from override_doctype_dashboards."""
	data = frappe._dict(data or {})
	data.fieldname = data.fieldname or "attendance"

	extra_items = [
		"Employee Checkin",
		"Late Entry Application",
		"Early Exit Application",
		"Out of Office Application",
	]

	transactions = list(data.transactions or [])
	if not transactions:
		data.transactions = [{"label": "Attendance Links", "items": extra_items}]
		return data

	first = frappe._dict(transactions[0])
	first["items"] = list(dict.fromkeys(list(first.get("items") or []) + extra_items))
	transactions[0] = first
	data.transactions = transactions
	return data
