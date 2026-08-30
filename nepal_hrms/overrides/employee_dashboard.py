# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe


def get_data(data=None):
	"""Extend Employee connections with Attendance Policy Escape."""
	data = frappe._dict(data or {})
	data.fieldname = data.fieldname or "employee"

	extra_items = ["Attendance Policy Escape"]

	transactions = list(data.transactions or [])
	if not transactions:
		data.transactions = [{"label": "Attendance Policy", "items": extra_items}]
		return data

	# Prefer an HR/Attendance group if present; else append to first group
	placed = False
	for i, group in enumerate(transactions):
		g = frappe._dict(group)
		label = (g.get("label") or "").lower()
		items = list(g.get("items") or [])
		if any(k in label for k in ("attendance", "leave", "hr", "employee")):
			g["items"] = list(dict.fromkeys(items + extra_items))
			transactions[i] = g
			placed = True
			break

	if not placed:
		first = frappe._dict(transactions[0])
		first["items"] = list(dict.fromkeys(list(first.get("items") or []) + extra_items))
		transactions[0] = first

	data.transactions = transactions
	return data
