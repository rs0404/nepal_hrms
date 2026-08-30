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
	from nepal_compliance.nepali_date_utils.nepali_date import (
		ad_to_bs,
		bs_to_ad,
		_ensure_loaded,
		_bs_months,
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

	bs_date = ad_to_bs(ref_date)
	_ensure_loaded()

	bs_year = bs_date.get("year") if isinstance(bs_date, dict) else getattr(bs_date, "year", None)
	bs_month = bs_date.get("month") if isinstance(bs_date, dict) else getattr(bs_date, "month", None)
	bs_day = bs_date.get("day") if isinstance(bs_date, dict) else getattr(bs_date, "day", None)

	if not bs_year or not bs_month:
		return {}

	# Honour the configured payroll period basis: a whole BS month, or a custom
	# range such as the 29th of one month to the 28th of the next.
	from nepal_hrms.custom_code.payroll.period import resolve_bs_period

	start_ad, end_ad, days = resolve_bs_period(bs_year, bs_month)
	if not start_ad:
		days_in_month = _bs_months.get(bs_year, [])[bs_month - 1]
		start_ad = bs_to_ad(bs_year, bs_month, 1)
		end_ad = bs_to_ad(bs_year, bs_month, days_in_month)
		days = days_in_month

	return {
		"start_date": str(start_ad) if start_ad else None,
		"end_date": str(end_ad) if end_ad else None,
		"period_days": days,
		"is_first_day": bs_day == 1,
	}
