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


def _span(first, last):
	return [first + timedelta(days=i) for i in range((last - first).days + 1)]
