"""Extend the fiscal year's opening payroll period back into the closing year.

Payroll periods run on a BS day cycle that need not align to the BS month: a slip
ending on day 28 belongs to a cycle that began on day 29 of the month before. The
fiscal year's first slip is the one that cannot express that, because there is no
earlier slip in the year to carry those leading days -- so they reach no slip at
all while the Monthly Attendance Sheet BS still reports them.

Nothing here is hardcoded. The cycle's first day comes from the slip's own end
date, and the month the year opens in comes from the Payroll Period or Fiscal Year
record covering the slip.
"""

from __future__ import annotations

import frappe
from frappe.utils import cint, getdate

import nepal_compliance.nepali_date_utils.nepali_date as nepali_date


def _settings_default():
	try:
		return cint(
			frappe.db.get_single_value(
				"Nepal HRMS Settings", "extend_payroll_to_previous_bs_month_tail"
			)
		)
	except Exception:
		return 0


def extension_enabled(doc=None):
	"""One company-wide rule. Which periods it touches is decided by the calendar."""
	return bool(_settings_default())


def _bs(ad_date):
	nepali_date._ensure_loaded()
	return nepali_date.ad_to_bs(getdate(ad_date))


def cycle_start_day(end_date):
	"""BS day a payroll cycle begins on, read off the day this one ends.

	A period ending on day 28 belongs to a 29-to-28 cycle. A period ending on the
	last day of its BS month is aligned to the month itself and has no leading
	days, so there is nothing to extend.
	"""
	bs = _bs(end_date)
	day = cint(bs["day"])
	try:
		if day >= nepali_date.days_in_bs_month(cint(bs["year"]), cint(bs["month"])):
			return None
	except Exception:
		return None
	return day + 1


def year_opening_bs_month(doc):
	"""BS month the payroll year opens in, from the records that define it."""
	company = getattr(doc, "company", None)
	span = {"start_date": ["<=", doc.end_date], "end_date": [">=", doc.start_date]}

	filters = dict(span)
	if company:
		filters["company"] = company
	rows = frappe.get_all("Payroll Period", filters=filters, fields=["start_date"], limit=1)
	if not rows and company:
		rows = frappe.get_all("Payroll Period", filters=span, fields=["start_date"], limit=1)
	if not rows:
		rows = frappe.get_all(
			"Fiscal Year",
			filters={
				"year_start_date": ["<=", doc.end_date],
				"year_end_date": [">=", doc.start_date],
			},
			fields=["year_start_date as start_date"],
			limit=1,
		)
	if not rows:
		return None
	return cint(_bs(rows[0].start_date)["month"])


def previous_bs_month_tail_start(doc):
	"""AD date the opening period should really start from, or None to leave it be.

	None when the slip does not open its payroll year, when it already begins on the
	cycle's first day, or when the calendar cannot place the date.
	"""
	start = getdate(doc.start_date)
	bs_start = _bs(start)

	tail_day = cycle_start_day(doc.end_date)
	if not tail_day or cint(bs_start["day"]) >= tail_day:
		# Already entered as the full cycle, or a custom period to leave alone.
		return None
	if cint(bs_start["day"]) != 1:
		return None

	opening_month = year_opening_bs_month(doc)
	if opening_month is None or cint(bs_start["month"]) != opening_month:
		# A mid-year period's leading days belong to the slip before it.
		return None

	year = cint(bs_start["year"])
	month = cint(bs_start["month"]) - 1
	if month < 1:
		year, month = year - 1, 12

	try:
		if nepali_date.days_in_bs_month(year, month) < tail_day:
			return None
		return nepali_date.bs_to_ad(year, month, tail_day)
	except Exception:
		# Outside the loaded calendar: leave the period exactly as entered.
		return None


def effective_start_date(doc):
	"""The date this slip's attendance figures should be counted from."""
	start = getdate(doc.start_date)
	if not extension_enabled(doc):
		return start
	return previous_bs_month_tail_start(doc) or start
