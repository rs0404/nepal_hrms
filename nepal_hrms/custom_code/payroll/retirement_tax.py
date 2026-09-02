# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""CIT elections and Nepal's approved-retirement deduction ceiling."""

from math import ceil

import frappe
from frappe.utils import add_months, flt, getdate


ANNUAL_RETIREMENT_LIMIT = 500_000.0
CIT_COMPONENT = "CIT"
RETIREMENT_DEDUCTION_COMPONENTS = (
	CIT_COMPONENT,
	"Employee's Contribution SSF",
	"Employer's Contribution SSF Deduction",
	"Provident Fund Employee",
	"Provident Fund Employer Deduction",
	"Gratuity Deduction",
)


def calculate_retirement_cap(actual_contributions, assessable_employment_income):
	"""Return the statutory lower of actual, one-third income, and NPR 500,000."""
	actual = max(flt(actual_contributions), 0.0)
	assessable = max(flt(assessable_employment_income), 0.0)
	one_third = flt(assessable / 3.0, 2)
	allowed = flt(min(actual, one_third, ANNUAL_RETIREMENT_LIMIT), 2)
	return frappe._dict(
		actual_contributions=flt(actual, 2),
		assessable_employment_income=flt(assessable, 2),
		one_third_limit=one_third,
		annual_limit=ANNUAL_RETIREMENT_LIMIT,
		allowed_deduction=allowed,
	)


def get_cit_contribution(employee, on_date):
	"""Latest submitted CIT election effective at the start of a payroll period."""
	if not employee or not on_date or not frappe.db.table_exists("Employee CIT Contribution"):
		return frappe._dict(name=None, effective_from=None, monthly_amount=0.0)

	row = frappe.db.get_value(
		"Employee CIT Contribution",
		{
			"employee": employee,
			"docstatus": 1,
			"effective_from": ("<=", getdate(on_date)),
		},
		["name", "effective_from", "monthly_amount"],
		order_by="effective_from desc, creation desc",
		as_dict=True,
	)
	if not row:
		return frappe._dict(name=None, effective_from=None, monthly_amount=0.0)
	row.monthly_amount = flt(row.monthly_amount)
	return row


def _sum_rows(rows):
	return flt(
		sum(
			flt(row.amount)
			for row in rows
			if row.salary_component in RETIREMENT_DEDUCTION_COMPONENTS
		),
		2,
	)


def _previous_contributions(doc):
	if not doc.payroll_period or not doc.start_date:
		return 0.0

	placeholders = ", ".join(["%s"] * len(RETIREMENT_DEDUCTION_COMPONENTS))
	result = frappe.db.sql(
		f"""
		SELECT COALESCE(SUM(sd.amount), 0)
		FROM `tabSalary Slip` ss
		INNER JOIN `tabSalary Detail` sd ON sd.parent = ss.name
		WHERE ss.docstatus = 1
			AND ss.employee = %s
			AND ss.start_date >= %s
			AND ss.end_date < %s
			AND sd.parentfield = 'deductions'
			AND sd.salary_component IN ({placeholders})
		""",
		(
			doc.employee,
			doc.payroll_period.start_date,
			doc.start_date,
			*RETIREMENT_DEDUCTION_COMPONENTS,
		),
	)
	return flt(result[0][0]) if result else 0.0


def _future_component_amount(doc, struct_row, sub_period):
	if struct_row.salary_component == CIT_COMPONENT:
		future_start = add_months(getdate(doc.start_date), sub_period)
		return flt(get_cit_contribution(doc.employee, future_start).monthly_amount)
	if struct_row.amount_based_on_formula and struct_row.formula:
		return flt(doc.get_amount_from_formula(struct_row, sub_period))
	return flt(struct_row.amount)


def _future_contributions(doc):
	remaining = max(ceil(flt(getattr(doc, "remaining_sub_periods", 0))), 1)
	rows = [
		row
		for row in doc._salary_structure_doc.get("deductions")
		if row.salary_component in RETIREMENT_DEDUCTION_COMPONENTS
	]
	total = 0.0
	for sub_period in range(1, remaining):
		total += sum(_future_component_amount(doc, row, sub_period) for row in rows)
	return flt(total, 2)


def _assessable_employment_income(doc):
	"""Projected taxable employment earnings before Section 63 deductions."""
	return flt(
		flt(getattr(doc, "previous_taxable_earnings_before_exemption", 0))
		+ flt(getattr(doc, "current_structured_taxable_earnings_before_exemption", 0))
		+ flt(getattr(doc, "future_structured_taxable_earnings_before_exemption", 0))
		+ flt(getattr(doc, "current_additional_earnings", 0))
		+ flt(getattr(doc, "unclaimed_taxable_benefits", 0)),
		2,
	)


def build_retirement_projection(doc):
	"""Build prior/current/future contribution totals and the statutory allowance."""
	previous = _previous_contributions(doc)
	current = _sum_rows(doc.get("deductions") or [])
	future = _future_contributions(doc)
	projected = flt(previous + current + future, 2)

	result = calculate_retirement_cap(projected, _assessable_employment_income(doc))
	result.update(
		previous_contributions=flt(previous, 2),
		current_contributions=flt(current, 2),
		future_contributions=flt(future, 2),
	)
	return result


def apply_retirement_cap_to_taxable_earnings(doc):
	"""Replace HRMS's uncapped retirement exemption with Nepal's capped amount."""
	if not getattr(doc, "tax_slab", None) or not doc.tax_slab.allow_tax_exemption:
		return None

	projection = build_retirement_projection(doc)
	remaining = max(round(flt(getattr(doc, "remaining_sub_periods", 0))), 1)
	previous = projection.previous_contributions
	current = projection.current_contributions

	# Stock HRMS subtracts the current full-period exemptions for every remaining
	# period. Add that retirement portion back, then subtract only Section 63's
	# allowed annual amount (which uses the actual effective-dated CIT schedule).
	retirement_subtracted_by_hrms = flt(previous + current * remaining, 2)
	correction = flt(retirement_subtracted_by_hrms - projection.allowed_deduction, 2)
	doc.total_taxable_earnings = flt(doc.total_taxable_earnings + correction, 2)
	doc.total_taxable_earnings_without_full_tax_addl_components = flt(
		doc.total_taxable_earnings_without_full_tax_addl_components + correction,
		2,
	)
	projection.retirement_subtracted_by_hrms = retirement_subtracted_by_hrms
	projection.taxable_correction = correction
	doc._nepal_retirement_tax = projection
	return projection


def capped_annual_deductions(doc, stock_annual_deductions):
	"""Use the capped retirement amount in HRMS's annual breakup display."""
	projection = getattr(doc, "_nepal_retirement_tax", None) or build_retirement_projection(doc)
	non_retirement = max(flt(stock_annual_deductions) - projection.actual_contributions, 0.0)
	return flt(non_retirement + projection.allowed_deduction, 2)
