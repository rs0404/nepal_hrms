# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Every tax exemption on a slip besides the retirement deduction, line by line.

HRMS takes these off annual income in totals only, so the slip's TDS breakdown
went from "Allowed Retirement Deduction" straight to "Annual Taxable Amount"
and anything else exempted was invisible:

- other tax-exempt deductions: components marked Exempted from Income Tax that
  are not retirement contributions (Insurance, for one), projected for the
  year the way HRMS projects them;
- the Employee Tax Exemption Declaration -- or the Proof Submission when the
  slip deducts tax for unsubmitted proof -- by sub-category, with the cap the
  declaration applied;
- the tax slab's standard exemption.

Each line is {label, amount, note, source}; the lines plus the allowed
retirement deduction add up to what HRMS subtracted.
"""

from math import ceil

import frappe
from frappe import _
from frappe.utils import cint, flt

from nepal_hrms.custom_code.payroll.retirement_tax import RETIREMENT_DEDUCTION_COMPONENTS


def _line(label, amount, note="", source=""):
	return {"label": label, "amount": flt(amount, 2), "note": note, "source": source}


def _is_other_exempt(component):
	from nepal_hrms.overrides.salary_slip import _skips_tax_projection

	return component not in RETIREMENT_DEDUCTION_COMPONENTS and not _skips_tax_projection(component)


def _previous_exempt_deductions(doc):
	"""{component: amount} from this employee's submitted slips earlier in the year."""
	period = getattr(doc, "payroll_period", None)
	if not period or not doc.start_date:
		return {}
	rows = frappe.db.sql(
		"""
		select sd.salary_component, sum(sd.amount)
		from `tabSalary Slip` ss
		join `tabSalary Detail` sd on sd.parent = ss.name and sd.parenttype = 'Salary Slip'
		where ss.docstatus = 1 and ss.employee = %s
			and ss.start_date >= %s and ss.end_date < %s
			and sd.parentfield = 'deductions' and sd.exempted_from_income_tax = 1
		group by sd.salary_component
		""",
		(doc.employee, period.start_date, doc.start_date),
	)
	return {component: flt(amount) for component, amount in rows}


def exempt_deduction_lines(doc):
	"""Annual amount of each non-retirement exempt deduction: paid + this + projected."""
	totals = {}
	for component, amount in _previous_exempt_deductions(doc).items():
		if _is_other_exempt(component):
			totals[component] = totals.get(component, 0.0) + amount
	for row in doc.get("deductions") or []:
		if cint(row.exempted_from_income_tax) and _is_other_exempt(row.salary_component):
			totals[row.salary_component] = totals.get(row.salary_component, 0.0) + flt(row.amount)

	structure = getattr(doc, "_salary_structure_doc", None)
	months_after = max(ceil(flt(getattr(doc, "remaining_sub_periods", 0))) - 1, 0)
	for row in (structure.get("deductions") if structure else None) or []:
		if not (cint(row.exempted_from_income_tax) and _is_other_exempt(row.salary_component)):
			continue
		if cint(row.amount_based_on_formula):
			future = sum(flt(doc.get_amount_from_formula(row, sub)) for sub in range(1, months_after + 1))
		else:
			future = flt(row.amount) * months_after
		totals[row.salary_component] = totals.get(row.salary_component, 0.0) + future

	return [
		_line(component, amount, _("exempt deduction for the year: paid, this month and projected"), "deduction")
		for component, amount in sorted(totals.items())
		if flt(amount, 2)
	]


def declaration_lines(doc):
	"""The declared (or proven) exemptions HRMS used, by sub-category."""
	slab = getattr(doc, "tax_slab", None)
	period = getattr(doc, "payroll_period", None)
	if not (slab and cint(slab.allow_tax_exemption) and period):
		return []

	filters = {"employee": doc.employee, "payroll_period": period.name, "docstatus": 1}
	if cint(doc.get("deduct_tax_for_unsubmitted_tax_exemption_proof")):
		doctype, child, used_field, kind = (
			"Employee Tax Exemption Proof Submission", "Employee Tax Exemption Proof Submission Detail",
			"exemption_amount", _("proof submitted"),
		)
	else:
		doctype, child, used_field, kind = (
			"Employee Tax Exemption Declaration", "Employee Tax Exemption Declaration Category",
			"total_exemption_amount", _("declared"),
		)
	parent = frappe.db.get_value(doctype, filters, ["name", used_field], as_dict=True)
	if not parent:
		return []

	fields = ["exemption_sub_category", "amount"]
	if frappe.get_meta(child).has_field("max_amount"):
		fields.append("max_amount")
	rows = frappe.get_all(child, filters={"parent": parent.name, "parenttype": doctype}, fields=fields, order_by="idx")
	lines = []
	for row in rows:
		cap = flt(row.get("max_amount"))
		amount = min(flt(row.amount), cap) if cap else flt(row.amount)
		note = kind
		if cap and flt(row.amount) > cap:
			note = _("{0} {1}, limited to {2}").format(
				kind, frappe.utils.fmt_money(row.amount), frappe.utils.fmt_money(cap)
			)
		lines.append(_line(row.exemption_sub_category, amount, note, "declaration"))

	# The category caps can bring the total below the rows; HRMS uses the total.
	used = flt(parent.get(used_field))
	listed = sum(line["amount"] for line in lines)
	if used and abs(used - listed) > 1:
		lines.append(_line(_("Category limit adjustment"), used - listed, _("so the lines match the {0} total").format(kind), "declaration"))
	return lines


def other_exemption_lines(doc, allowed_retirement=0.0):
	"""All non-retirement exemptions, reconciled to what HRMS actually subtracted."""
	lines = exempt_deduction_lines(doc) + declaration_lines(doc)
	slab = getattr(doc, "tax_slab", None)
	standard = flt(slab.standard_tax_exemption_amount) if slab and cint(slab.allow_tax_exemption) else 0.0
	if standard:
		lines.append(_line(_("Standard exemption"), standard, _("from the tax slab"), "standard"))

	# Whatever HRMS took off beyond retirement and what is listed: shown, never lost.
	subtracted = (
		flt(doc.get("deductions_before_tax_calculation"))
		+ flt(doc.get("tax_exemption_declaration"))
		+ flt(doc.get("standard_tax_exemption_amount"))
	)
	unexplained = flt(subtracted - flt(allowed_retirement) - sum(line["amount"] for line in lines), 2)
	if abs(unexplained) > 1:
		lines.append(_line(_("Other exemptions"), unexplained, _("subtracted by payroll but not itemised"), "other"))
	return lines
