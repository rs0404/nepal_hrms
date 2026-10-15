__version__ = "1.0.1"

# Monkey patch Frappe HR's get_period_factor for Nepali calendar months
try:
	import hrms.payroll.doctype.payroll_period.payroll_period
	from hrms.payroll.doctype.payroll_period.payroll_period import (
		get_period_factor as original_get_period_factor,
	)

	def patched_get_period_factor(*args, **kwargs):
		factor = original_get_period_factor(*args, **kwargs)
		if isinstance(factor, tuple) and len(factor) == 2:
			try:
				from frappe.utils import date_diff, getdate

				start_date = args[1]
				payroll_frequency = args[3]
				payroll_period = args[4]

				joining_date = kwargs.get("joining_date")
				relieving_date = kwargs.get("relieving_date")

				period_start, period_end = payroll_period.start_date, payroll_period.end_date

				if not joining_date and not relieving_date:
					import frappe

					joining_date, relieving_date = frappe.get_cached_value(
						"Employee", args[0], ["date_of_joining", "relieving_date"]
					)

				if getdate(joining_date) > getdate(period_start):
					period_start = joining_date

				if relieving_date and getdate(relieving_date) < getdate(period_end):
					period_end = relieving_date

				if payroll_frequency == "Monthly" and not kwargs.get("depends_on_payment_days"):
					total_sub_periods = round(
						(date_diff(payroll_period.end_date, payroll_period.start_date) + 1) / 30.4167
					)
					# The slip being made is itself a period, so at least one remains.
					# Rounding alone gave 0 for an employee relieved within the first
					# half of the slip's month: income tax divided by it, and the
					# year's projection went negative.
					remaining_sub_periods = max(
						round((date_diff(period_end, start_date) + 1) / 30.4167), 1
					)
					return (total_sub_periods, remaining_sub_periods)
			except Exception:
				pass
			total_sub_periods, remaining_sub_periods = (
				round(f) if isinstance(f, (int, float)) else f for f in factor
			)
			if isinstance(remaining_sub_periods, (int, float)):
				remaining_sub_periods = max(remaining_sub_periods, 1)
			return (total_sub_periods, remaining_sub_periods)

		if isinstance(factor, (int, float)):
			return round(factor)
		return factor

	hrms.payroll.doctype.payroll_period.payroll_period.get_period_factor = patched_get_period_factor
except ImportError:
	pass
