# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Payroll period resolution and the per-day divisor.

Two independent choices, both in Nepal HRMS Settings:

* **Payroll period basis** -- what span a run covers. Either a whole BS month, or
  a custom range straddling two months (e.g. the 29th to the 28th).
* **Daily rate basis** -- how a monthly figure becomes a per-day rate: a fixed
  number of days, the period's own length, the BS month's true length, or the
  slip's working days.

A Nepal Payroll Period Override can replace the day count for one period. It only
applies to slips created on or after its `applies_from`, and every slip snapshots
the divisor it was calculated with, so historical pay is never restated.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate

BASIS_FIXED = "Fixed Days"
BASIS_PERIOD = "Days in Payroll Period"
BASIS_BS_MONTH = "Days in BS Month"
BASIS_WORKING = "Working Days in Period"


def _nd():
	import nepal_compliance.nepali_date_utils.nepali_date as nd

	nd._ensure_loaded()
	return nd


def bs_month_length(bs_year, bs_month):
	"""True length of a BS month (29-32 days)."""
	try:
		return cint(_nd()._bs_months[cint(bs_year)][cint(bs_month) - 1])
	except Exception:
		return 0


def custom_period_start_day(settings=None):
	"""Configured BS opening day for Custom Day Range (1–29).

	Shortest BS months are 29 days, so day 29 exists in every month. Day 30+ does not.
	"""
	settings = settings if settings is not None else get_settings()
	return min(max(cint(settings.get("payroll_period_start_day") or 1), 1), 29)


def resolve_bs_period(bs_year, bs_month, settings=None):
	"""(from_date, to_date, days) for a BS month under the configured basis.

	Nepali Month     -> day 1 .. last day of the month
	Custom Day Range -> start_day of this month .. (start_day - 1) of the next
	"""
	settings = settings if settings is not None else get_settings()
	bs_year, bs_month = cint(bs_year), cint(bs_month)
	try:
		nd = _nd()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "nepali_date unavailable")
		return None, None, 0

	length = bs_month_length(bs_year, bs_month)
	if not length:
		return None, None, 0

	basis = settings.get("payroll_period_basis") or "Nepali Month"
	if basis != "Custom Day Range":
		start = nd.bs_to_ad(bs_year, bs_month, 1)
		end = nd.bs_to_ad(bs_year, bs_month, length)
		return getdate(start), getdate(end), length

	start_day = custom_period_start_day(settings)
	start = getdate(nd.bs_to_ad(bs_year, bs_month, start_day))
	nxt_year, nxt_month = (bs_year + 1, 1) if bs_month == 12 else (bs_year, bs_month + 1)
	nxt_start = nd.bs_to_ad(nxt_year, nxt_month, start_day)
	if not nxt_start:
		return start, None, 0
	end = add_days(getdate(nxt_start), -1)
	return start, end, (end - start).days + 1


def period_containing(date, settings=None):
	"""(from_date, to_date, days) for the payroll period that includes `date`.

	For Custom Day Range with start day 29, a date on BS day 15 of month M falls in
	the period that opened on day 29 of month M-1, not month M's upcoming range.
	"""
	settings = settings if settings is not None else get_settings()
	date = getdate(date)
	bs_year, bs_month = bs_month_of(date)
	if not bs_year:
		return None, None, 0

	basis = settings.get("payroll_period_basis") or "Nepali Month"
	if basis == "Custom Day Range":
		try:
			bs = _nd().ad_to_bs(date)
			bs_day = cint(bs.get("day") if isinstance(bs, dict) else getattr(bs, "day", 0))
		except Exception:
			bs_day = 0
		start_day = custom_period_start_day(settings)
		if bs_day and bs_day < start_day:
			bs_year, bs_month = (bs_year - 1, 12) if bs_month == 1 else (bs_year, bs_month - 1)

	return resolve_bs_period(bs_year, bs_month, settings)


def previous_period(date, settings=None):
	"""(from_date, to_date, days) for the payroll period that ended before the one containing `date`."""
	settings = settings if settings is not None else get_settings()
	start, _end, _days = period_containing(date, settings)
	if not start:
		return None, None, 0
	return period_containing(add_days(getdate(start), -1), settings)


def get_settings():
	from nepal_hrms.custom_code.attendance_policy import get_hr_settings

	return get_hr_settings()


def bs_month_of(date):
	"""(bs_year, bs_month) the given AD date falls in."""
	try:
		bs = _nd().ad_to_bs(getdate(date))
		return cint(bs["year"]), cint(bs["month"])
	except Exception:
		return 0, 0


def is_period_start_date(date, settings=None):
	"""True when `date` is the opening day of its payroll period."""
	settings = settings if settings is not None else get_settings()
	start, _end, _days = period_containing(date, settings)
	return bool(start) and getdate(date) == getdate(start)


def get_period_override(start_date, company=None, created_on=None):
	"""Active override covering start_date, or None.

	`created_on` is the salary slip's creation date -- an override only applies to
	slips created on or after its `applies_from`, so publishing one never restates
	pay that has already been calculated.
	"""
	if not frappe.db.exists("DocType", "Nepal Payroll Period Override"):
		return None

	start_date = getdate(start_date)
	created_on = getdate(created_on or frappe.utils.today())

	filters = {
		"from_date": ["<=", start_date],
		"to_date": [">=", start_date],
		"applies_from": ["<=", created_on],
	}
	rows = frappe.get_all(
		"Nepal Payroll Period Override",
		filters=filters,
		fields=["name", "company", "total_days_override", "applies_from", "reason"],
		order_by="applies_from desc",
	)
	if not rows:
		return None
	# Company-specific beats the blank-company catch-all.
	for r in rows:
		if company and r.company == company:
			return r
	for r in rows:
		if not r.company:
			return r
	return None


def resolve_daily_divisor(start_date, end_date, working_days=None, company=None, created_on=None):
	"""Days to divide a monthly figure by. Returns (divisor, explanation)."""
	settings = get_settings()

	override = get_period_override(start_date, company=company, created_on=created_on)
	if override and cint(override.total_days_override) > 0:
		return flt(cint(override.total_days_override)), _("period override {0}").format(override.name)

	basis = settings.get("daily_rate_basis") or BASIS_FIXED

	if basis == BASIS_PERIOD and start_date and end_date:
		days = (getdate(end_date) - getdate(start_date)).days + 1
		if days > 0:
			return flt(days), _("days in payroll period")

	if basis == BASIS_BS_MONTH and start_date:
		y, m = bs_month_of(start_date)
		days = bs_month_length(y, m) if y else 0
		if days > 0:
			return flt(days), _("days in BS month")

	if basis == BASIS_WORKING and flt(working_days) > 0:
		return flt(working_days), _("working days in period")

	# Fixed Days, and the fallback whenever a dynamic basis cannot be resolved.
	fixed = cint(settings.get("daily_rate_fixed_days") or 30) or 30
	return flt(fixed), _("fixed {0} days").format(fixed)


@frappe.whitelist()
def preview_daily_divisor(start_date, end_date=None, company=None):
	"""Desk helper: show which divisor a period would use and why."""
	frappe.has_permission("Salary Slip", "read", throw=True)
	divisor, why = resolve_daily_divisor(start_date, end_date, company=company)
	return {"divisor": divisor, "basis": why}
