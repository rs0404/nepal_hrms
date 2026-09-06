import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from frappe.utils.safe_exec import safe_eval
from typing import Union


def check_app_permission():
	if frappe.session.user in ("Administrator", "Guest"):
		return frappe.session.user == "Administrator"

	if frappe.db.exists("Employee", {"user_id": frappe.session.user, "status": "Active"}):
		return True

	return frappe.has_permission("Employee", ptype="read")


@frappe.whitelist()
def evaluate_tax_formula(formula: str, taxable_salary: Union[str, float]) -> float:
	try:
		taxable_salary = flt(taxable_salary)
		context = {
			"taxable_salary": taxable_salary,
			"if": lambda x, y, z: y if x else z,
		}
		# nosemgrep: frappe-semgrep-rules.rules.security.frappe-codeinjection-eval
		result = safe_eval(formula, {"__builtins__": {}}, context)
		return flt(result)
	except Exception as e:
		frappe.throw(
			_("Invalid tax formula: {0}. Payroll calculation stopped. Please fix the formula.").format(
				str(e)
			)
		)


@frappe.whitelist()
def get_suggested_payroll_dates(employee=None, start_date=None):
	"""Suggest start/end for Payroll Entry / Salary Slip from Nepal HRMS Settings.

	Uses the period that *contains* the reference date (Custom Day Range aware),
	and sets is_first_day when that date is the period's opening day so the Desk
	client can auto-fill the end date (e.g. picking the 29th fills through the 28th).
	"""
	from nepal_compliance.nepali_date_utils.nepali_date import (
		bs_to_ad,
		_ensure_loaded,
		_bs_months,
	)
	from nepal_hrms.custom_code.payroll.period import (
		bs_month_of,
		is_period_start_date,
		period_containing,
	)

	ref_date = None
	if start_date:
		ref_date = getdate(start_date)
	elif employee:
		last_slip = frappe.db.get_list(
			"Salary Slip",
			filters={"employee": employee, "docstatus": 1},
			fields=["end_date"],
			order_by="end_date desc",
			limit=1,
		)
		if last_slip and last_slip[0].end_date:
			ref_date = frappe.utils.add_days(last_slip[0].end_date, 1)

	if not ref_date:
		ref_date = getdate(nowdate())

	_ensure_loaded()
	start_ad, end_ad, days = period_containing(ref_date)
	if not start_ad:
		bs_year, bs_month = bs_month_of(ref_date)
		if not bs_year or not bs_month:
			return {}
		days_in_month = _bs_months.get(bs_year, [])[bs_month - 1]
		start_ad = bs_to_ad(bs_year, bs_month, 1)
		end_ad = bs_to_ad(bs_year, bs_month, days_in_month)
		days = days_in_month

	return {
		"start_date": str(start_ad) if start_ad else None,
		"end_date": str(end_ad) if end_ad else None,
		"period_days": days,
		# Kept as is_first_day for existing Desk JS; means "period opening day".
		"is_first_day": is_period_start_date(ref_date),
	}
