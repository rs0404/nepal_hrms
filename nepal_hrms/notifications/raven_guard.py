# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe


def raven_available():
	"""True only when the Raven app is installed and its doctypes are synced.

	Never raises. Sites without Raven must keep Nepal HRMS Settings usable.
	"""
	try:
		return bool(
			"raven" in frappe.get_installed_apps() and frappe.db.exists("DocType", "Raven Bot")
		)
	except Exception:
		return False
