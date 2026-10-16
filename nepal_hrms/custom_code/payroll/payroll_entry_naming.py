# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Name a Payroll Entry after the BS period it pays.

"HR-PRUN-2026-00015" says nothing about which month it is. A monthly run is
named for the BS month it ends in -- the month its slips, bank file remarks and
attendance sheet already go by -- so the entry reads like the payroll it is:

    Monthly      Shrawan 2083 Monthly
    Bimonthly    Shrawan-Bhadra 2083 Bimonthly
    Weekly       Shrawan 1-7 2083 Weekly
    Fortnightly  Shrawan 29-Bhadra 12 2083 Fortnightly
    Daily        Shrawan 5 2083 Daily

A run restricted to one salary structure carries its Salary / Wages variant
("Shrawan 2083 Monthly Wages"). A second entry for the same period -- a re-run
after a cancellation, say -- gets "-2", "-3"; amendments keep Frappe's own
suffix. Existing entries keep their names.
"""

import frappe
from frappe.utils import getdate

BS_MONTHS = (
	"Baisakh", "Jestha", "Ashadh", "Shrawan", "Bhadra", "Ashwin",
	"Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra",
)


def _month(bs):
	return BS_MONTHS[int(bs["month"]) - 1]


def payroll_entry_title(frequency, start_bs, end_bs, variant=None):
	"""The readable part of the name, from BS {year, month, day} dates."""
	frequency = frequency or "Monthly"
	same_month = (start_bs["year"], start_bs["month"]) == (end_bs["year"], end_bs["month"])

	if frequency == "Monthly":
		period = f"{_month(end_bs)} {end_bs['year']}"
	elif frequency == "Bimonthly":
		if start_bs["year"] == end_bs["year"]:
			period = f"{_month(start_bs)}-{_month(end_bs)} {end_bs['year']}"
		else:
			period = f"{_month(start_bs)} {start_bs['year']}-{_month(end_bs)} {end_bs['year']}"
	elif frequency == "Daily" or (start_bs == end_bs):
		period = f"{_month(end_bs)} {int(end_bs['day'])} {end_bs['year']}"
	elif same_month:
		period = f"{_month(start_bs)} {int(start_bs['day'])}-{int(end_bs['day'])} {end_bs['year']}"
	elif start_bs["year"] == end_bs["year"]:
		period = (
			f"{_month(start_bs)} {int(start_bs['day'])}-{_month(end_bs)} {int(end_bs['day'])} "
			f"{end_bs['year']}"
		)
	else:
		period = (
			f"{_month(start_bs)} {int(start_bs['day'])} {start_bs['year']}-"
			f"{_month(end_bs)} {int(end_bs['day'])} {end_bs['year']}"
		)

	return " ".join(part for part in (period, frequency, variant) if part)


def next_free_name(base, exists):
	"""base, then base-2, base-3 ... -- the first that exists() says is free."""
	if not exists(base):
		return base
	n = 2
	while exists(f"{base}-{n}"):
		n += 1
	return f"{base}-{n}"


def _bs(ad_date):
	import nepal_compliance.nepali_date_utils.nepali_date as nepali_date

	nepali_date._ensure_loaded()
	return nepali_date.ad_to_bs(getdate(ad_date))


def name_payroll_entry(doc):
	"""Set doc.name from its period; leave it unset if the dates are not there yet."""
	if not (doc.get("start_date") and doc.get("end_date")):
		return
	try:
		start_bs, end_bs = _bs(doc.start_date), _bs(doc.end_date)
	except Exception:
		# No BS calendar for these dates: fall back to the naming series.
		return

	from nepal_hrms.custom_code.payroll.component_variant import structure_variant

	variant = structure_variant(doc.get("custom_salary_structure")) if doc.get("custom_salary_structure") else None
	base = payroll_entry_title(doc.get("payroll_frequency"), start_bs, end_bs, variant)
	doc.name = next_free_name(base, lambda name: frappe.db.exists("Payroll Entry", name))
