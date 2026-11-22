# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Salary Structure Assignment on HRMS 16.

HRMS 16 evaluates every Salary Structure formula on the assignment itself: on
save, to work out CTC and annual gross, and again for Job Offers and the CTC
break-up report. The assignment has no salary slip, so the names the Nepal
structures take from one -- the leave and late deduction, the CIT election, the
`nsa_` allowance amounts -- do not resolve there, and stock stops with
"name 'leave_late_deduction_total' is not defined". Without this class no
assignment on a Nepal structure can be saved.

Salary slips do not use these figures: CustomSalarySlip evaluates the structure
against the slip's own period (see _set_evaluated_components there).
"""

from frappe.utils import flt
from hrms.payroll.doctype.salary_structure_assignment.salary_structure_assignment import (
	SalaryStructureAssignment,
)


class CustomSalaryStructureAssignment(SalaryStructureAssignment):
	def validate(self):
		# Stock works out CTC and gross inside validate(), ahead of the validate
		# hook that fills the breakdown fields the formulas read. Settle the
		# breakdown first; the hook running again afterwards changes nothing.
		from nepal_hrms.custom_code.payroll.salary_breakdown import sync_salary_breakdown

		sync_salary_breakdown(self)
		super().validate()

	def _get_component_eval_context(self):
		data = super()._get_component_eval_context()
		data.update(nepal_formula_context(self))
		return data


def nepal_formula_context(assignment):
	"""What a Nepal formula may name beyond stock's context, for a full cycle.

	A full cycle has no leave, absence or penalty, so the attendance variables
	are neutral. CIT is the election in force when the assignment starts.
	"""
	from nepal_hrms.custom_code.payroll.retirement_tax import get_cit_contribution
	from nepal_hrms.custom_code.payroll.salary_breakdown import (
		_component_type,
		allowance_map_from_rows,
	)
	from nepal_hrms.overrides.salary_slip import neutral_nepal_hr_variables

	context = neutral_nepal_hr_variables()
	context.update(
		allowance_map_from_rows(
			[
				row
				for row in assignment.get("custom_allowances") or []
				if _component_type(row.salary_component) == "Earning"
			]
		)
	)
	context["cit_contribution"] = flt(
		get_cit_contribution(assignment.employee, assignment.from_date).monthly_amount
	)
	return context
