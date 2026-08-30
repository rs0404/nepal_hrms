# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Scheduled Payroll Entry creation, one per configured salary structure.

Fires from the daily scheduler. On the configured BS day it resolves the period
that just ended and creates a Payroll Entry per enabled row in Nepal HRMS
Settings, restricted to that row's salary structure.

Deliberately conservative:

* Draft-only by default. Slips are created, and submitted, only when the setting
  explicitly says so -- submitting posts the accrual journal entry.
* One row failing never stops the rest; each is isolated by a savepoint.
* Idempotent per period: a run that already produced an entry for the same
  company / structure / period is skipped, so a second scheduler tick or a
  manual re-run cannot double-post.
"""

import frappe
from frappe import _
from frappe.utils import cint, getdate, today


def _settings():
	from nepal_hrms.custom_code.attendance_policy import get_hr_settings

	return get_hr_settings()


def _previous_bs_period(settings):
	"""(from_date, to_date) of the period that ended before today."""
	from nepal_hrms.custom_code.payroll.period import bs_month_of, resolve_bs_period

	year, month = bs_month_of(today())
	if not year:
		return None, None
	# The run fires at the start of a period and pays the one before it.
	prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
	start, end, _days = resolve_bs_period(prev_year, prev_month, settings)
	return start, end


def _already_run(company, structure, start_date, end_date):
	return frappe.db.exists(
		"Payroll Entry",
		{
			"company": company,
			"custom_salary_structure": structure,
			"start_date": start_date,
			"end_date": end_date,
			"docstatus": ["<", 2],
		},
	)


def _create_entry(row, start_date, end_date, action):
	entry = frappe.new_doc("Payroll Entry")
	entry.company = row.company
	entry.posting_date = today()
	entry.payroll_frequency = "Monthly"
	entry.start_date = start_date
	entry.end_date = end_date
	entry.cost_center = row.cost_center
	entry.payroll_payable_account = row.payroll_payable_account
	if row.payment_account:
		entry.payment_account = row.payment_account
	entry.currency = frappe.db.get_value("Company", row.company, "default_currency") or "NPR"
	entry.exchange_rate = 1
	if entry.meta.has_field("custom_salary_structure"):
		entry.custom_salary_structure = row.salary_structure
	if entry.meta.has_field("custom_created_by_scheduler"):
		entry.custom_created_by_scheduler = 1

	entry.insert(ignore_permissions=True)
	entry.fill_employee_details()
	entry.save(ignore_permissions=True)

	if action == "Create Payroll Entry Only":
		return entry, "draft with employees"

	entry.submit()
	entry.create_salary_slips()
	if action == "Create Payroll Entry and Salary Slips":
		return entry, "slips created (draft)"

	entry.submit_salary_slips()
	return entry, "slips submitted"


def run_scheduled_payroll(force=False):
	"""Daily scheduler entry point."""
	settings = _settings()
	if not cint(settings.get("enable_scheduled_payroll") or 0):
		return

	from nepal_hrms.custom_code.payroll.period import bs_month_of

	if not force:
		try:
			import nepal_compliance.nepali_date_utils.nepali_date as nd

			nd._ensure_loaded()
			bs_today = nd.ad_to_bs(getdate(today()))
			run_day = min(max(cint(settings.get("scheduled_payroll_run_day") or 1), 1), 28)
			if cint(bs_today["day"]) != run_day:
				return
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Scheduled payroll: BS date unavailable")
			return

	rows = [r for r in (settings.get("scheduled_payroll_runs") or []) if cint(r.get("enabled"))]
	if not rows:
		return

	start_date, end_date = _previous_bs_period(settings)
	if not start_date or not end_date:
		frappe.log_error("Could not resolve the previous BS period", "Scheduled payroll")
		return

	action = settings.get("scheduled_payroll_action") or "Create Payroll Entry Only"
	results = []

	for row in rows:
		row = frappe._dict(row) if isinstance(row, dict) else row
		label = f"{row.company} / {row.salary_structure}"
		existing = _already_run(row.company, row.salary_structure, start_date, end_date)
		if existing:
			results.append({"row": label, "status": "skipped", "detail": f"already exists: {existing}"})
			continue

		savepoint = "nepal_scheduled_payroll"
		try:
			frappe.db.savepoint(savepoint)
			entry, detail = _create_entry(row, start_date, end_date, action)
		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			frappe.log_error(frappe.get_traceback(), f"Scheduled payroll failed: {label}")
			results.append({"row": label, "status": "failed", "detail": str(e)[:200]})
		else:
			results.append({"row": label, "status": "ok", "detail": f"{entry.name} - {detail}"})

	_notify(settings, start_date, end_date, action, results)
	return results


def _notify(settings, start_date, end_date, action, results):
	role = settings.get("scheduled_payroll_notify") or "HR Manager"
	recipients = frappe.get_all(
		"Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent"
	)
	recipients = [
		u for u in set(recipients)
		if frappe.db.get_value("User", u, "enabled") and u not in ("Administrator", "Guest")
	]
	if not recipients:
		return

	failed = [r for r in results if r["status"] == "failed"]
	lines = "".join(
		f"<li><b>{frappe.utils.escape_html(r['row'])}</b>: {r['status']} &mdash; "
		f"{frappe.utils.escape_html(r['detail'])}</li>"
		for r in results
	)
	subject = _("Scheduled payroll {0}").format(_("completed with errors") if failed else _("completed"))
	message = _(
		"Payroll period {0} to {1}. Mode: {2}.<ul>{3}</ul>"
	).format(start_date, end_date, action, lines)

	for user in recipients:
		try:
			notification = frappe.new_doc("Notification Log")
			notification.subject = subject
			notification.email_content = message
			notification.for_user = user
			notification.type = "Alert"
			notification.document_type = "Payroll Entry"
			notification.insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Scheduled payroll notification failed")


@frappe.whitelist()
def run_now():
	"""Desk button: run the scheduled payroll immediately, ignoring the day check."""
	frappe.only_for(("System Manager", "HR Manager"))
	return run_scheduled_payroll(force=True)
