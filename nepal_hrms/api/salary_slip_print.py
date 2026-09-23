"""Render a Salary Slip through its print format, for the BSHRMS PWA.

The app ships Nepal Standard Salary Slip -- the layout people actually recognise
as their payslip. The PWA only ever showed the raw doctype fields, so an employee
opening their salary saw Details, Earnings, Net Pay Info and had to download a
PDF to see the slip itself.
"""

import re

import frappe
from frappe import _

APP_PRINT_FORMAT = "Nepal Standard Salary Slip"


def default_print_format():
	"""The app's own format when it is available, else whatever the site prefers."""
	if frappe.db.exists("Print Format", {"name": APP_PRINT_FORMAT, "disabled": 0}):
		return APP_PRINT_FORMAT

	configured = frappe.db.get_value(
		"Property Setter",
		{"doc_type": "Salary Slip", "property": "default_print_format"},
		"value",
	)
	if configured and frappe.db.exists("Print Format", {"name": configured, "disabled": 0}):
		return configured
	return "Standard"


@frappe.whitelist()
def get_salary_slip_html(name, print_format=None):
	"""Rendered payslip HTML for one Salary Slip.

	Permission is checked against the document, so an employee sees their own slip
	and nobody else's -- the same rule the desk print view applies.
	"""
	if not name:
		frappe.throw(_("Salary Slip is required."))

	frappe.has_permission("Salary Slip", "read", doc=name, throw=True)

	chosen = print_format or default_print_format()
	try:
		html = frappe.get_print("Salary Slip", name, print_format=chosen)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Nepal HRMS: salary slip print render")
		# A broken or missing format must not leave the tab empty for good.
		html = frappe.get_print("Salary Slip", name)
		chosen = "Standard"

	return {"name": name, "print_format": chosen, "html": _strip_action_banner(html)}


# printview.html opens with a Print / Get PDF bar. The app shows the slip to read,
# not to print or download, so the bar goes. The banner holds only two links,
# so the first </div> after it closes it.
ACTION_BANNER = re.compile(r'<div class="action-banner[^"]*">.*?</div>', re.DOTALL)


def _strip_action_banner(html):
	return ACTION_BANNER.sub("", html or "", count=1)
