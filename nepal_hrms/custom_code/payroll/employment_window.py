# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Days of a payroll period that fall outside the employee's employment.

Policy: a period that starts before the joining date or runs past the relieving
date counts those days as absences. HRMS instead shortens the period
(actual_start_date / actual_end_date), which only trims payment_days -- fixed
earnings do not depend on them, so the days were paid in full. The Salary Slip
and the Monthly Attendance Sheet BS both read this, so they agree on the count.
"""

from datetime import timedelta

from frappe.utils import getdate


def dates_outside_employment(start_date, end_date, joining_date=None, relieving_date=None):
	"""Calendar dates in [start_date, end_date] before joining or after relieving.

	Holidays are included; callers drop them the way their own count does. Uses
	the same windows as HRMS: a joining date after the period start, a relieving
	date before the period end.
	"""
	start, end = getdate(start_date), getdate(end_date)
	dates = []
	if joining_date:
		joining = getdate(joining_date)
		if start < joining <= end:
			dates.extend(_span(start, joining - timedelta(days=1)))
	if relieving_date:
		relieving = getdate(relieving_date)
		if start <= relieving < end:
			dates.extend(_span(relieving + timedelta(days=1), end))
	return dates


def payroll_window(
	start_date, end_date, period_start, period_end, joining_date=None, relieving_date=None
):
	"""(start, end) of the payroll period a slip cut short by employment belongs to.

	A late joiner's slip is sometimes dated from the joining day, or a leaver's to
	the relieving day. HRMS then counts over that stub, so the daily divisor and
	total working days fall short of everyone else's in the period and the days
	outside employment are never charged. The slip goes back to the whole period
	only on a side employment explains; a slip that does not sit inside one period,
	or starts late for any other reason, keeps its own dates.
	"""
	start, end = getdate(start_date), getdate(end_date)
	if not (period_start and period_end):
		return start, end
	period_start, period_end = getdate(period_start), getdate(period_end)
	if not (period_start <= start <= end <= period_end):
		return start, end
	if joining_date and start > period_start and getdate(joining_date) >= start:
		start = period_start
	if relieving_date and end < period_end and getdate(relieving_date) <= end:
		end = period_end
	return start, end


def _span(first, last):
	return [first + timedelta(days=i) for i in range((last - first).days + 1)]
