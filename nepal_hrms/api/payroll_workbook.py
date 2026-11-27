# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Calculation Workbook: a Payroll Entry's slips as live Excel formulas.

Each slip is one row that rebuilds the ERP's arithmetic: the Salary Structure's
own formulas and conditions (translated by excel_formula), the leave and late
deduction, its allocation out of earned salary, SSF / PF scaling, totals, and
the annual tax down to this month's TDS. Changing a yellow input recalculates
the row.

What the ERP finds by looking things up -- attendance day counts, policy
escapes, earlier months of the fiscal year -- arrives as an input holding the
ERP's figure. The tax projection's earlier-months inputs are worked back from
the slip, so every row matches the ERP when downloaded and the Check columns
show anything that does not.

The Salary & Tax Sheet stays the static record; this file is for working out
"what if".
"""

import json
import re
from collections import OrderedDict

import frappe
from frappe import _
from frappe.utils import cint, flt

from nepal_hrms.api.payroll_exports import NP_MONEY_FORMAT, _save, component_root
from nepal_hrms.api.salary_tax_sheet import (
	_load,
	_payroll_period,
	_slabs_by_employee,
	_tax,
	paid_before,
	slab_breakdown,
)
from nepal_hrms.custom_code.payroll.excel_formula import Untranslatable, to_excel
from nepal_hrms.custom_code.payroll.retirement_tax import (
	ANNUAL_RETIREMENT_LIMIT,
	RETIREMENT_DEDUCTION_COMPONENTS,
)
from nepal_hrms.overrides.salary_slip import (
	ASSIGNMENT_BASE,
	ATTENDANCE_DEDUCTION_COMPONENTS,
	BASIC_EARNING_COMPONENTS,
	CONTRIBUTION_DEDUCTIONS,
	DA_EARNING_COMPONENTS,
	DEFAULT_BASIC_BASE,
	EMPLOYER_CONTRIBUTION_EARNINGS,
	GRADE_EARNING_COMPONENTS,
	GROSS_BASE,
	OTHER_ALLOWANCE_COMPONENTS,
	SSF_CONTRIBUTIONS,
	_amount_from_assignment,
	_check_setting,
	_is_attendance_deduction,
	_matches_component,
	_taken_from_earnings,
)

# Column groups, in sheet order: (key, title, header fill, cell fill)
GROUPS = [
	("emp", _("Employee"), "5D6D7E", "F2F4F4"),
	("days", _("Days (from attendance)"), "B7950B", "FFF9C4"),
	("in", _("Salary inputs"), "B7950B", "FFF9C4"),
	("asg", _("Assignment totals"), "7F8C8D", "F4F6F6"),
	("att", _("Leave & late deduction"), "7F8C8D", "F4F6F6"),
	("fix", _("Contract amounts (full month)"), "2E86C1", "EBF5FB"),
	("es", _("Taken out of earned salary"), "7F8C8D", "F4F6F6"),
	("earn", _("Earnings"), "1E8449", "E9F7EF"),
	("ded", _("Deductions"), "B03A2E", "FDEDEC"),
	("tot", _("Net Pay"), "1F4E79", "D6EAF8"),
	("tax", _("Tax (annual)"), "6C3483", "F4ECF7"),
	("chk", _("Check against the ERP"), "566573", "F8F9F9"),
]
GROUP = {g[0]: g for g in GROUPS}
INPUT_FILL = "FFF9C4"
STATIC_FILL = "FAD7A0"  # a formula the workbook could not translate

GROUP_ROW, HEAD_ROW = 5, 6
REF = re.compile(r"\[\[(.+?)\]\]")

# Formula variables that are a day count: variable -> (slip field, label).
# Absent days read the genuine-absence figure, as compute_nepal_hr_variables
# narrows absent_days to it.
DAY_VARS = {
	"total_working_days": ("total_working_days", _("Working Days")),
	"payment_days": ("payment_days", _("Payment Days")),
	"leave_without_pay": ("leave_without_pay", _("LWP Days")),
	"lwp_days": ("leave_without_pay", _("LWP Days")),
	"absent_days": ("custom_unapproved_absent_days", _("Absent Days")),
	"unapproved_absent_days": ("custom_unapproved_absent_days", _("Absent Days")),
	"penalty_days": ("custom_penalty_days", _("Penalty Days (½P / 1P)")),
	"gross_lwp_days": ("custom_gross_lwp_days", _("LWP Days on Gross")),
	"late_entry_half_days": ("custom_late_entry_half_days", _("Late Entry Half-days")),
	"early_exit_half_days": ("custom_early_exit_half_days", _("Early Exit Half-days")),
	"out_of_office_half_days": ("custom_out_of_office_half_days", _("Out of Office Half-days")),
	"late_entry_full_days": ("custom_late_entry_full_days", _("Late Entry Full Days")),
	"early_exit_full_days": ("custom_early_exit_full_days", _("Early Exit Full Days")),
}
ATT_VARS = {
	"leave_late_deduction_total": "att:total",
	"late_deduction_rate": "att:rate_half",
	"lwp_deduction_rate": "att:rate_lwp",
	"gross_lwp_rate": "att:rate_gross",
	"unapproved_absent_rate": "att:rate_absent",
	"penalty_deduction_rate": "att:rate_penalty",
}
ASSIGNMENT_TOTALS = ("custom_total_allowances", "custom_basic_remuneration", "custom_total_fixed_remuneration", "base")
SETTINGS_CEILING = "Settings!$B$4"
SETTINGS_GRADE = "Settings!$B$5"
SETTINGS_DA = "Settings!$B$6"


# --------------------------------------------------------------------------
# Grid: columns registered on the fly, cells holding values or formulas


class Grid:
	def __init__(self):
		self.columns = OrderedDict()  # key -> dict(group, label, fmt, sum)
		self.rows = []

	def column(self, key, group, label, fmt="money", total=None):
		if key not in self.columns:
			self.columns[key] = frappe._dict(
				group=group, label=label, fmt=fmt, total=(fmt == "money") if total is None else total
			)
		return f"[[{key}]]"

	def ordered(self):
		order = {g[0]: i for i, g in enumerate(GROUPS)}
		keys = list(self.columns)
		return sorted(keys, key=lambda k: (order[self.columns[k].group], keys.index(k)))


class Row:
	"""One slip's cells. A value is an input; a string starting with '=' a formula."""

	def __init__(self, grid):
		self.grid = grid
		self.cells = {}
		self.notes = {}
		self.static = set()

	def input(self, key, group, label, value, fmt="money"):
		self.grid.column(key, group, label, fmt)
		if key not in self.cells:
			self.cells[key] = value
		return f"[[{key}]]"

	def formula(self, key, group, label, expr, fmt="money", total=None):
		self.grid.column(key, group, label, fmt, total)
		self.cells[key] = "=" + expr
		return f"[[{key}]]"

	def fallback(self, key, group, label, value, why):
		self.grid.column(key, group, label)
		self.cells[key] = flt(value, 2)
		self.static.add(key)
		self.notes[key] = why
		return f"[[{key}]]"


def _sum(refs):
	return "SUM(" + ",".join(refs) + ")" if refs else "0"


# --------------------------------------------------------------------------
# One slip


class SlipModel:
	def __init__(self, ctx, s, grid):
		self.ctx, self.s, self.row = ctx, s, Row(grid)
		self.doc = frappe.get_doc("Salary Slip", s.name)
		# A slip without a structure keeps every row as an input from the slip.
		self.structure = (
			ctx.structure(self.doc.salary_structure)
			if self.doc.salary_structure
			else frappe._dict(earnings=[], deductions=[])
		)
		self.data = self._eval_data()
		# The eval data's "name" is the slip's; the assignment's is kept apart.
		self.assignment_name = (getattr(self.doc, "_salary_structure_assignment", None) or {}).get("name")
		self.abbr_key = {}
		self.keys = {}
		self.slip_rows = {}

	def _eval_data(self):
		doc = self.doc
		try:
			data, _default = doc.get_data_for_eval()
		except Exception:
			data = frappe._dict(doc.as_dict())
		if hasattr(doc, "_inject_salary_allowances"):
			doc._inject_salary_allowances(data)
		# The CIT the slip deducted is the starting figure: the election snapshot
		# when there is one, else whatever an older slip's row came to.
		cit_rows = [d for d in doc.deductions if d.salary_component == "CIT"]
		if cit_rows:
			cit = sum(flt(d.default_amount) or flt(d.amount) for d in cit_rows)
		else:
			cit = doc.get("custom_cit_contribution_amount")
			if cit is None:
				from nepal_hrms.custom_code.payroll.retirement_tax import get_cit_contribution

				cit = get_cit_contribution(doc.employee, doc.start_date).monthly_amount
		data["cit_contribution"] = flt(cit)
		return data

	# ---- variables --------------------------------------------------------

	def day(self, var):
		field, label = DAY_VARS[var]
		value = self.doc.get(field)
		if value is None and field == "custom_unapproved_absent_days":
			value = self.doc.absent_days
		return self.row.input(f"days:{field}", "days", label, flt(value), "days")

	def resolve(self, name):
		if name in self.abbr_key:
			return f"[[fix:{self.abbr_key[name]}]]"
		if name in self.ctx.all_abbrs:
			return "0"
		if name in DAY_VARS:
			return self.day(name)
		if name in ATT_VARS:
			self.attendance()
			return f"[[{ATT_VARS[name]}]]"
		if name == "total_other_allowances" and self.has_breakdown():
			return self.assignment("custom_total_allowances")
		if name in ASSIGNMENT_TOTALS and self.has_breakdown():
			return self.assignment(name)
		value = self.data.get(name)
		if isinstance(value, bool):
			value = int(value)
		if value is None:
			value = 0
		if not isinstance(value, (int, float, str)):
			raise Untranslatable(f"{name} is not a number")
		return self.row.input(f"in:{name}", "in", name, value, "money" if not isinstance(value, str) else "text")

	def has_breakdown(self):
		return bool(flt(self.data.get("custom_basic_salary")))

	def assignment(self, field):
		"""The assignment's totals as formulas over its breakdown, as sync_salary_breakdown sums them."""
		key = f"asg:{field}"
		if key in self.row.cells:
			return f"[[{key}]]"
		basic = self.resolve("custom_basic_salary")
		da = self.resolve("custom_dearness_allowance")
		grade = self.resolve("custom_grade_amount")
		if field == "custom_total_allowances":
			from nepal_hrms.custom_code.payroll.salary_breakdown import ALLOWANCE_PREFIX, get_allowance_rows

			refs = []
			for r in get_allowance_rows(self.assignment_name):
				abbr = (r.abbr or "").strip() or frappe.scrub(r.salary_component or "")
				if abbr and f"{ALLOWANCE_PREFIX}{abbr}" in self.data:
					ref = self.resolve(f"{ALLOWANCE_PREFIX}{abbr}")
					if ref not in refs:
						refs.append(ref)
			return self.row.formula(key, "asg", _("Total Allowances"), f"ROUND({_sum(refs)},2)")
		if field == "custom_basic_remuneration":
			return self.row.formula(
				key, "asg", _("Basic Remuneration (SSF base)"),
				f"ROUND({basic}+IF({SETTINGS_GRADE}=1,{grade},0)+IF({SETTINGS_DA}=1,{da},0),2)",
			)
		allowances = self.assignment("custom_total_allowances")
		label = _("Base (Total Salary)") if field == "base" else _("Total Fixed Remuneration")
		return self.row.formula(key, "asg", label, f"ROUND({basic}+{da}+{grade}+{allowances},2)")

	# ---- leave & late -----------------------------------------------------

	def attendance(self):
		"""Rates and amounts as compute_nepal_hr_variables works them, over the stored day counts."""
		if "att:total" in self.row.cells:
			return "[[att:total]]"
		ctx, row = self.ctx, self.row

		basic_rem = (
			self.resolve("custom_basic_remuneration")
			if flt(self.data.get("custom_basic_remuneration")) or self.has_breakdown()
			else f"ROUND({self.resolve('base')}*{flt(ctx.settings.get('default_basic_percent') or 60)}/100,2)"
		)
		total_fixed = (
			self.resolve("custom_total_fixed_remuneration")
			if flt(self.data.get("custom_total_fixed_remuneration")) or self.has_breakdown()
			else self.resolve("base")
		)
		basic = self.resolve("custom_basic_salary") if flt(self.data.get("custom_basic_salary")) else basic_rem
		da = self.resolve("custom_dearness_allowance") if self.data.get("custom_dearness_allowance") is not None else "0"
		grade = self.resolve("custom_grade_amount") if self.data.get("custom_grade_amount") is not None else "0"
		assignment_base = self.resolve("base") if flt(self.data.get("base")) else total_fixed
		bases = {
			"Basic Salary Only": basic,
			"Basic Salary + Grade": f"({basic}+{grade})",
			"Basic Salary + Dearness Allowance": f"({basic}+{da})",
			"Basic Salary + Grade + Dearness Allowance": f"({basic}+{grade}+{da})",
			DEFAULT_BASIC_BASE: basic_rem,
			GROSS_BASE: total_fixed,
			ASSIGNMENT_BASE: assignment_base,
		}

		def base(selection):
			return bases.get(selection, basic_rem)

		escapes = self.escapes()
		half_name = ctx.settings.get("half_day_deduction_base") or DEFAULT_BASIC_BASE
		lwp_name = ctx.settings.get("lwp_deduction_base") or DEFAULT_BASIC_BASE
		absent_name = ctx.settings.get("unapproved_absence_deduction_base") or GROSS_BASE
		penalty_name = ctx.settings.get("penalty_deduction_base") or half_name
		if cint(escapes.get("escape_absent_gross")):
			absent_name = DEFAULT_BASIC_BASE if absent_name == GROSS_BASE else absent_name
			penalty_name = DEFAULT_BASIC_BASE if penalty_name == GROSS_BASE else penalty_name

		divisor = row.input("days:divisor", "days", _("Daily Divisor"), self.divisor(), "days")
		per_day = lambda expr: f"IF({divisor}=0,0,{expr}/{divisor})"  # noqa: E731
		half = row.formula("att:rate_half", "att", _("Half-day Rate"), per_day(base(half_name)) + "*0.5", "rate")
		lwp = row.formula("att:rate_lwp", "att", _("LWP Rate ({0})").format(lwp_name), per_day(base(lwp_name)), "rate")
		gross = row.formula("att:rate_gross", "att", _("LWP Rate on Gross"), per_day(total_fixed), "rate")
		absent = row.formula("att:rate_absent", "att", _("Absent Rate ({0})").format(absent_name), per_day(base(absent_name)), "rate")
		penalty = row.formula("att:rate_penalty", "att", _("Penalty Rate ({0})").format(penalty_name), per_day(base(penalty_name)), "rate")

		half_days = "(" + "+".join(
			self.day(v) for v in ("late_entry_half_days", "early_exit_half_days", "out_of_office_half_days")
		) + ")"
		lwp_days, gross_days = self.day("lwp_days"), self.day("gross_lwp_days")
		amounts = [
			row.formula("att:half", "att", _("Late / Early / OOO"), f"ROUND({half_days}*{half},2)"),
			row.formula(
				"att:lwp", "att", _("LWP"),
				f"ROUND({gross_days}*{gross}+MAX({lwp_days}-{gross_days},0)*{lwp},2)",
			),
			row.formula("att:absent", "att", _("Unapproved Absence"), f"ROUND({self.day('absent_days')}*{absent},2)"),
			row.formula("att:penalty", "att", _("½P / 1P Penalties"), f"ROUND({self.day('penalty_days')}*{penalty},2)"),
		]
		return row.formula("att:total", "att", _("Leave & Late Total"), f"ROUND({'+'.join(amounts)},2)")

	def divisor(self):
		used = flt(self.doc.get("custom_daily_divisor_used"))
		if used:
			return used
		try:
			stored = json.loads(self.doc.get("custom_attendance_breakdown_data") or "{}")
		except ValueError:
			stored = {}
		return flt(stored.get("daily_divisor")) or flt(self.doc.total_working_days)

	def escapes(self):
		if not hasattr(self, "_escapes"):
			try:
				from nepal_hrms.custom_code.payroll.bs_period import effective_start_date
				from nepal_hrms.custom_code.policy_escape import get_policy_escapes_for_period

				self._escapes = get_policy_escapes_for_period(
					self.doc.employee, effective_start_date(self.doc), self.doc.end_date
				)
			except Exception:
				self._escapes = frappe._dict()
		return self._escapes

	# ---- components -------------------------------------------------------

	def build(self):
		doc, row = self.doc, self.row
		for d in doc.earnings + doc.deductions:
			self.slip_rows.setdefault((d.parentfield, d.salary_component), d)

		struct = [(r, "earnings") for r in self.structure.earnings] + [
			(r, "deductions") for r in self.structure.deductions
		]
		struct = [(r, pf) for r, pf in struct if not cint(r.get("is_flexible_benefit"))]
		names = {r.salary_component for r, _pf in struct}
		extra = [
			(d, d.parentfield) for d in doc.earnings + doc.deductions if d.salary_component not in names
		]
		roots = [component_root(r.salary_component) for r, _pf in struct + extra]
		for r, pf in struct + extra:
			root = component_root(r.salary_component)
			self.keys[(pf, r.salary_component)] = root if roots.count(root) == 1 else r.salary_component
		for r, pf in struct:
			# TDS is worked out after everything else; a formula naming it reads 0.
			if r.abbr and not cint(r.variable_based_on_taxable_salary):
				self.abbr_key[r.abbr] = self.keys[(pf, r.salary_component)]

		components = []
		for r, pf in struct:
			components.append(self.contract(r, pf))
		for d, pf in extra:
			key = self.keys[(pf, d.salary_component)]
			self.row.input(
				f"fix:{key}", "fix", key + " " + _("(from slip)"),
				flt(d.default_amount) or flt(d.amount) - flt(d.additional_amount),
			)
			components.append(frappe._dict(
				name=d.salary_component, pf=pf, key=key, tds=cint(d.variable_based_on_taxable_salary),
				counted=not (cint(d.statistical_component) or cint(d.do_not_include_in_total)),
				prorate=0, taxable=cint(d.is_tax_applicable),
			))
		self.components = components
		self.earned_salary()
		self.finals()
		self.tax()
		self.totals_and_checks()
		return row

	def contract(self, r, pf):
		"""The structure row's full-month amount: condition and formula, rounded like HRMS."""
		key = self.keys[(pf, r.salary_component)]
		label = key
		slip_row = self.slip_rows.get((pf, r.salary_component))
		info = frappe._dict(
			name=r.salary_component, pf=pf, key=key, tds=cint(r.variable_based_on_taxable_salary),
			counted=not (cint(r.statistical_component) or cint(r.do_not_include_in_total)),
			prorate=cint(r.depends_on_payment_days),
			taxable=cint(frappe.get_cached_value("Salary Component", r.salary_component, "is_tax_applicable")),
		)
		if info.tds:
			return info
		try:
			if r.salary_component == "CIT":
				amount, condition = self.resolve("cit_contribution"), None
			else:
				condition = r.condition
				if _amount_from_assignment(r.salary_component):
					from nepal_hrms.custom_code.payroll.salary_breakdown import get_assignment_amount

					amount = self.row.input(
						f"in:assignment:{key}", "in", _("{0} (assignment)").format(key),
						get_assignment_amount(self.assignment_name, r.salary_component),
					)
				elif cint(r.amount_based_on_formula) and (r.formula or "").strip():
					amount = to_excel(r.formula, self.resolve)
				else:
					amount = repr(flt(r.amount))
			expr = f"ROUND({amount},2)"
			if (condition or "").strip():
				expr = f"IF({to_excel(condition, self.resolve)},{expr},0)"
			self.row.formula(f"fix:{key}", "fix", label, expr)
		except Untranslatable as e:
			erp = flt(slip_row.default_amount) if slip_row else 0.0
			self.row.fallback(
				f"fix:{key}", "fix", label, erp,
				_("Written as the ERP's figure: {0}.\nFormula: {1}\nCondition: {2}").format(
					e, r.formula or "-", r.condition or "-"
				),
			)
		return info

	def additional(self, c):
		d = self.slip_rows.get((c.pf, c.name))
		if not d:
			return None
		amount = flt(d.amount) if d.additional_salary and not flt(d.default_amount) else flt(d.additional_amount)
		if not amount:
			return None
		return self.row.input(f"in:additional:{c.key}", "in", _("{0} (additional salary)").format(c.key), amount)

	def earned_salary(self):
		"""allocate_attendance_deduction and the SSF / PF ratio, as formulas."""
		ctx = self.ctx
		self.mode = cint(ctx.earned_mode) and any(
			_is_attendance_deduction(r.salary_component) for r in self.structure.deductions
		)
		self.earned = {}
		if not self.mode:
			return
		allowance_names = ctx.allowance_components(self.assignment_name)
		# a: allowances, c: rest of the SSF base (Basic), g: Grade, taken last.
		pool_a, pool_c, pool_g, contributing = [], [], [], []
		for c in self.components:
			if c.pf != "earnings" or c.tds:
				continue
			name = c.name
			is_grade = False
			if _matches_component(name, BASIC_EARNING_COMPONENTS):
				contributes = True
			elif _matches_component(name, DA_EARNING_COMPONENTS):
				contributes = ctx.include_da
			elif _matches_component(name, GRADE_EARNING_COMPONENTS):
				contributes, is_grade = ctx.include_grade, True
			elif name in allowance_names or _matches_component(name, OTHER_ALLOWANCE_COMPONENTS):
				contributes = False
			else:
				continue
			(pool_g if is_grade else pool_c if contributes else pool_a).append(c)
			if contributes:
				contributing.append(c)

		row, total = self.row, self.attendance()
		fixed = lambda c: f"[[fix:{c.key}]]"  # noqa: E731
		if ctx.proportional:
			pool = _sum([fixed(c) for c in pool_a + pool_c + pool_g])
			take = row.formula("es:take", "es", _("Taken from earnings"), f"MIN({total},{pool})")
			groups = [(pool_a + pool_c + pool_g, pool, take)]
			taken = take
		else:
			a, c_, g = (_sum([fixed(c) for c in p]) for p in (pool_a, pool_c, pool_g))
			take_a = row.formula("es:take_a", "es", _("Taken from allowances"), f"MIN({total},{a})")
			take_c = row.formula("es:take_c", "es", _("Taken from Basic"), f"MIN({total}-{take_a},{c_})")
			take_g = row.formula("es:take_g", "es", _("Taken from Grade"), f"MIN({total}-{take_a}-{take_c},{g})")
			groups = [(pool_a, a, take_a), (pool_c, c_, take_c), (pool_g, g, take_g)]
			taken = f"{take_a}+{take_c}+{take_g}"
		for members, pool, take in groups:
			for c in members:
				self.earned[c.key] = f"IF({pool}=0,{fixed(c)},ROUND({fixed(c)}-{take}*{fixed(c)}/{pool},2))"
		row.formula("es:unapplied", "es", _("Left as a deduction"), f"ROUND({total}-({taken}),2)")
		fixed_base = _sum([fixed(c) for c in contributing])
		earned_base = "+".join(f"({self.earned[c.key]})" for c in contributing) or "0"
		row.formula("es:ratio", "es", _("Earned ÷ fixed SSF base"), f"IF({fixed_base}=0,1,({earned_base})/{fixed_base})", "rate")

	def finals(self):
		row = self.row
		ssf_escape = cint(self.escapes().get("escape_ssf_earned_scaling"))
		first_attendance = True
		for c in self.components:
			group = "earn" if c.pf == "earnings" else "ded"
			if c.tds:
				c.final = row.formula(f"{group}:{c.key}", group, c.key, "[[tax:tds]]")
				c.counted = True
				continue
			fixed = f"[[fix:{c.key}]]"
			additional = self.additional(c)
			plus = f"+{additional}" if additional else ""
			scaled = _matches_component(c.name, EMPLOYER_CONTRIBUTION_EARNINGS + CONTRIBUTION_DEDUCTIONS)
			if self.mode and c.key in self.earned:
				expr = self.earned[c.key] + plus
			elif self.mode and scaled:
				ratio = "1" if ssf_escape and _matches_component(c.name, SSF_CONTRIBUTIONS) else "[[es:ratio]]"
				expr = f"ROUND({fixed}*{ratio},2){plus}"
			elif self.mode and c.pf == "deductions" and _is_attendance_deduction(c.name):
				# Only what earnings could not absorb is still deducted.
				expr = "[[es:unapplied]]" if first_attendance else "0"
				first_attendance = False
			elif c.prorate:
				wd, pd = self.day("total_working_days"), self.day("payment_days")
				expr = f"IF(TRUNC({wd})=0,{fixed},ROUND({fixed}*{pd}/TRUNC({wd}),2)){plus}"
			else:
				expr = fixed + plus
			if (
				c.pf == "deductions"
				and _taken_from_earnings(c.name)
				and not _matches_component(c.name, ATTENDANCE_DEDUCTION_COMPONENTS)
			):
				c.counted = False
			c.final = row.formula(f"{group}:{c.key}", group, c.key + ("" if c.counted else " " + _("(not in total)")), expr)

	# ---- tax --------------------------------------------------------------

	def tax(self):
		"""Annual tax as stock HRMS + retirement_tax project it, then this month's TDS.

		Earlier months, other income and the ERP's month-by-month future projection
		are one input each, worked back so the row equals the slip when downloaded:
		this month moves with its actual amounts, the rest of the year with the
		contract amounts, as HRMS projects future months on full-month figures.
		"""
		row, s, ctx = self.row, self.s, self.ctx
		if not any(c.tds for c in self.components):
			return
		t = _tax(s, 0)
		remaining = t.remaining or ctx.remaining_months(self.doc)
		slab_name, slab_rows = ctx.slabs.get(s.employee, (None, []))
		allow_exemption = ctx.slab_cell(slab_name, "allow")

		taxable = [c for c in self.components if c.pf == "earnings" and c.taxable and not c.tds]
		retire = [c for c in self.components if c.pf == "deductions" and c.name in RETIREMENT_DEDUCTION_COMPONENTS]

		def actual_and_fixed(members):
			now = fixed = 0.0
			for c in members:
				d = self.slip_rows.get((c.pf, c.name))
				if d:
					now += flt(d.amount)
					fixed += flt(d.default_amount) or flt(d.amount) - flt(d.additional_amount)
			return now, fixed

		income_now, income_fixed = actual_and_fixed(taxable)
		retire_now, retire_fixed = actual_and_fixed(retire)
		left = max(remaining - 1, 0)

		R = row.input("tax:remaining", "tax", _("Months Left (incl. this)"), remaining, "days")
		now = row.formula("tax:income_now", "tax", _("Taxable Earnings This Month"), _sum([c.final for c in taxable]))
		full = row.formula("tax:income_full", "tax", _("Taxable Earnings, Full Month"), _sum([f"[[fix:{c.key}]]" for c in taxable]))
		earlier = row.input(
			"tax:income_rest", "tax", _("Earlier Months & Other Income (ERP)"),
			flt(t.assessable - income_now - income_fixed * left, 2),
		)
		assessable = row.formula(
			"tax:assessable", "tax", _("Assessable Income"), f"ROUND({earlier}+{now}+{full}*MAX({R}-1,0),2)"
		)
		r_now = row.formula("tax:retire_now", "tax", _("SSF / PF / CIT This Month"), _sum([c.final for c in retire]))
		r_full = row.formula("tax:retire_full", "tax", _("SSF / PF / CIT, Full Month"), _sum([f"[[fix:{c.key}]]" for c in retire]))
		r_earlier = row.input(
			"tax:retire_rest", "tax", _("Earlier & Future Retirement Adj. (ERP)"),
			flt(t.retirement - retire_now - retire_fixed * left, 2),
		)
		retirement = row.formula(
			"tax:retirement", "tax", _("Retirement Contribution (year)"),
			f"ROUND({r_earlier}+{r_now}+{r_full}*MAX({R}-1,0),2)",
		)
		third = row.formula("tax:one_third", "tax", _("1/3 of Income"), f"ROUND({assessable}/3,2)")
		allowed = row.formula(
			"tax:allowed", "tax", _("Allowed Retirement Deduction"),
			f"IF({allow_exemption}=1,ROUND(MAX(MIN({retirement},{third},{SETTINGS_CEILING}),0),2),0)",
		)
		other = row.input(
			"tax:other", "tax", _("Other Exemptions (ERP)"), flt(t.assessable - t.allowed - t.taxable, 2)
		)
		taxable_income = row.formula(
			"tax:taxable", "tax", _("Taxable Income"), f"MAX(ROUND({assessable}-{allowed}-{other},2),0)"
		)

		bands = []
		for i, slab in enumerate(slab_rows, start=1):
			if (slab.get("condition") or "").strip():
				continue
			low, high, rate = (ctx.slab_cell(slab_name, f"{col}{i}") for col in ("from", "to", "rate"))
			band = (
				f"IF({taxable_income}<{low},0,IF(OR({high}=0,{taxable_income}<{high}),"
				f"{taxable_income}-{low}+1,{high}-{low}+1))"
			)
			bands.append(row.formula(f"tax:band{i}", "tax", _("Slab {0} Tax").format(i), f"ROUND({band}*{rate}/100,2)"))
		relief = ctx.slab_cell(slab_name, "relief")
		slab_tax = f"IF({taxable_income}>{relief},{_sum(bands)},0)"

		_rows, worked = slab_breakdown(t.taxable, slab_rows)
		relief_value = ctx.slab_relief.get(slab_name, 0.0)
		worked = worked if t.taxable > relief_value else 0.0
		adjustment = flt(t.annual_tax - worked, 2)
		adj = row.input("tax:adjust", "tax", _("ERP Adjustment to Slab Tax"), adjustment)
		if abs(adjustment) > 1:
			row.notes["tax:adjust"] = _(
				"The ERP's annual tax differs from the slab table by this much (marginal relief, a conditional slab or other taxes and charges). It is carried as a fixed amount."
			)
			row.static.add("tax:adjust")
		annual = row.formula("tax:annual", "tax", _("Annual Tax"), f"ROUND({slab_tax}+{adj},2)")
		paid = row.input("tax:paid", "tax", _("TDS Paid Till Last Month"), paid_before(self.doc, self.tds_erp()))
		row.formula("tax:tds", "tax", _("TDS This Month"), f"IF({R}>0,MAX(ROUND(({annual}-{paid})/{R},2),0),0)")

	def tds_erp(self):
		return sum(
			flt(self.slip_rows[(c.pf, c.name)].amount)
			for c in self.components
			if c.tds and (c.pf, c.name) in self.slip_rows
		)

	def totals_and_checks(self):
		row, s = self.row, self.s
		earn = [c.final for c in self.components if c.pf == "earnings" and c.counted]
		ded = [c.final for c in self.components if c.pf == "deductions" and c.counted]
		gross = row.formula("tot:gross", "tot", _("Gross Pay"), _sum(earn))
		total = row.formula("tot:ded", "tot", _("Total Deductions"), _sum(ded))
		loan = flt(self.doc.get("total_loan_repayment"))
		less_loan = "-" + row.input("in:total_loan_repayment", "in", _("Loan Repayment"), loan) if loan else ""
		net = row.formula("tot:net", "tot", _("Net Pay"), f"{gross}-{total}{less_loan}")

		tds_erp = self.tds_erp()
		checks = [
			("gross", _("Gross"), gross, s.gross_pay),
			("ded", _("Deductions"), total, s.total_deduction),
			("net", _("Net Pay"), net, s.net_pay),
		]
		if "tax:tds" in row.cells:
			checks.append(("taxable", _("Taxable Income"), "[[tax:taxable]]", s.annual_taxable_amount))
			checks.append(("tds", _("TDS"), "[[tax:tds]]", tds_erp))
		for key, label, ref, erp in checks:
			erp_ref = row.input(f"chk:{key}", "chk", _("ERP {0}").format(label), flt(erp, 2))
			row.formula(f"chk:{key}_diff", "chk", _("{0} Difference").format(label), f"ROUND({ref}-{erp_ref},2)", total=False)


# --------------------------------------------------------------------------
# Workbook


class Context(frappe._dict):
	pass


def _department_name(department):
	"""The name without the " - ABBR" company suffix ERPNext adds to the ID."""
	if not department:
		return department
	return frappe.get_cached_value("Department", department, "department_name") or department


def _context(pe, slips):
	from nepal_hrms.custom_code.attendance_policy import get_hr_settings
	from nepal_hrms.custom_code.payroll.salary_breakdown import get_allowance_rows

	settings = get_hr_settings()
	ctx = Context(
		pe=pe,
		settings=settings,
		earned_mode=_check_setting(settings, "calculate_attendance_deductions_through_earned_salary", default=1),
		proportional=_check_setting(settings, "proportionally_reduce_earnings_for_attendance_deductions", default=0),
		include_grade=bool(_check_setting(settings, "include_grade_in_ssf_base", default=1)),
		include_da=bool(_check_setting(settings, "include_da_in_ssf_base", default=0)),
		all_abbrs=set(frappe.get_all("Salary Component", pluck="salary_component_abbr")),
		slabs=_slabs_by_employee(slips),
		period=_payroll_period(pe),
		slab_cells={},
		slab_relief={},
	)
	structures, allowances = {}, {}

	def structure(name):
		if name not in structures:
			structures[name] = frappe.get_cached_doc("Salary Structure", name)
		return structures[name]

	def allowance_components(assignment):
		if assignment not in allowances:
			allowances[assignment] = {r.salary_component for r in get_allowance_rows(assignment) if r.salary_component}
		return allowances[assignment]

	def remaining_months(doc):
		from hrms.payroll.doctype.payroll_period.payroll_period import get_period_factor

		if not ctx.period:
			return 1
		try:
			_total, remaining = get_period_factor(
				doc.employee, doc.start_date, doc.end_date, doc.payroll_frequency,
				frappe.get_cached_doc("Payroll Period", ctx.period.name),
			)
			return max(cint(round(flt(remaining))), 1)
		except Exception:
			return 1

	def slab_cell(slab, what):
		return ctx.slab_cells.get((slab, what), "0")

	ctx.structure = structure
	ctx.allowance_components = allowance_components
	ctx.remaining_months = remaining_months
	ctx.slab_cell = slab_cell
	return ctx


def build_payroll_workbook(pe, period_label):
	from openpyxl import Workbook

	slips, _details = _load(pe)
	if not slips:
		frappe.throw(_("This Payroll Entry has no salary slips yet."))

	ctx = _context(pe, slips)
	wb = Workbook()
	ws = wb.active
	ws.title = _("Payroll")
	settings_ws = wb.create_sheet(_("Settings"))
	_settings_sheet(settings_ws, ctx)

	grid = Grid()
	for s in slips:
		row = SlipModel(ctx, s, grid).build()
		grid.rows.append((s, row))

	_payroll_sheet(ws, ctx, grid, period_label)
	_legend_sheet(wb.create_sheet(_("How to read")))
	wb.calculation.fullCalcOnLoad = True
	return _save(wb)


def _styles():
	from openpyxl.styles import Border, Font, PatternFill, Side

	thin = Side(style="thin", color="BFC9CA")
	return frappe._dict(
		border=Border(top=thin, bottom=thin, left=thin, right=thin),
		white_bold=Font(bold=True, color="FFFFFF"),
		bold=Font(bold=True),
		muted=Font(italic=True, color="7F8C8D"),
		fill=lambda hex_: PatternFill("solid", fgColor=hex_),
		Font=Font,
	)


FORMATS = {"money": NP_MONEY_FORMAT, "days": "General", "rate": "#,##0.0000", "text": "@"}


def _settings_sheet(ws, ctx):
	from openpyxl.styles import Font

	st = _styles()
	ws["A1"] = _("Settings used by the Payroll sheet")
	ws["A1"].font = Font(bold=True, size=14, color="1F4E79")
	ws["A2"] = _("Yellow cells can be changed; the Payroll sheet recalculates.")
	ws["A2"].font = st.muted
	for r, label, value in (
		(4, _("Annual retirement deduction ceiling"), ANNUAL_RETIREMENT_LIMIT),
		(5, _("Grade in SSF base (1 = yes)"), int(ctx.include_grade)),
		(6, _("Dearness Allowance in SSF base (1 = yes)"), int(ctx.include_da)),
	):
		ws.cell(row=r, column=1, value=label)
		cell = ws.cell(row=r, column=2, value=value)
		cell.fill, cell.border = st.fill(INPUT_FILL), st.border
		cell.number_format = NP_MONEY_FORMAT if r == 4 else "0"
	ws.cell(row=7, column=1, value=_("Leave & late taken out of earned salary"))
	ws.cell(row=7, column=2, value=_("Yes") if ctx.earned_mode else _("No"))
	ws.cell(row=8, column=1, value=_("Allocation"))
	ws.cell(row=8, column=2, value=_("Proportional") if ctx.proportional else _("Allowances first, then Basic, then Grade"))

	r = 11
	slabs = OrderedDict()
	for name, rows in ctx.slabs.values():
		if name:
			slabs[name] = rows
	for name, rows in slabs.items():
		meta = frappe.db.get_value(
			"Income Tax Slab", name, ["tax_relief_limit", "allow_tax_exemption"], as_dict=True
		) or frappe._dict()
		ws.cell(row=r, column=1, value=_("Income Tax Slab: {0}").format(name)).font = st.bold
		r += 1
		for what, label, value, fmt in (
			("relief", _("Tax relief limit"), flt(meta.tax_relief_limit), NP_MONEY_FORMAT),
			("allow", _("Retirement exemption allowed (1 = yes)"), cint(meta.allow_tax_exemption), "0"),
		):
			ws.cell(row=r, column=1, value=label)
			cell = ws.cell(row=r, column=2, value=value)
			cell.fill, cell.border, cell.number_format = st.fill(INPUT_FILL), st.border, fmt
			ctx.slab_cells[(name, what)] = f"Settings!$B${r}"
			r += 1
		ctx.slab_relief[name] = flt(meta.tax_relief_limit)
		for c, label in enumerate((_("Slab"), _("From"), _("To (0 = no limit)"), _("Rate %"), _("Condition")), start=1):
			cell = ws.cell(row=r, column=c, value=label)
			cell.font, cell.fill = st.white_bold, st.fill("8E44AD")
		r += 1
		for i, slab in enumerate(rows, start=1):
			ws.cell(row=r, column=1, value=i)
			for c, (what, value) in enumerate(
				(("from", flt(slab.from_amount)), ("to", flt(slab.to_amount)), ("rate", flt(slab.percent_deduction))),
				start=2,
			):
				cell = ws.cell(row=r, column=c, value=value)
				cell.fill, cell.border = st.fill(INPUT_FILL), st.border
				cell.number_format = "0.##" if what == "rate" else NP_MONEY_FORMAT
				ctx.slab_cells[(name, f"{what}{i}")] = f"Settings!${'ABCD'[c - 1]}${r}"
			if (slab.get("condition") or "").strip():
				ws.cell(row=r, column=5, value=slab.condition).font = st.muted
			r += 1
		r += 1
	for col, width in (("A", 44), ("B", 18), ("C", 18), ("D", 10), ("E", 30)):
		ws.column_dimensions[col].width = width


def _payroll_sheet(ws, ctx, grid, period_label):
	from openpyxl.comments import Comment
	from openpyxl.formatting.rule import FormulaRule
	from openpyxl.styles import Alignment, Font
	from openpyxl.utils import get_column_letter

	st = _styles()
	pe = ctx.pe
	ws["A1"] = _("Payroll Calculation Workbook")
	ws["A1"].font = Font(bold=True, size=14, color="1F4E79")
	ws["A2"] = _("{0}  ·  Payroll Entry {1}  ·  {2} ({3} to {4})").format(
		pe.company, pe.name, period_label, pe.start_date, pe.end_date
	)
	ws["A2"].font = Font(italic=True, color="555555")
	ws["A3"] = _("Change a yellow cell and the row recalculates. Orange cells are ERP figures the workbook could not turn into a formula.")
	ws["A3"].font = st.muted

	fixed = [
		("emp:sn", _("S.N.")), ("emp:employee", _("Employee ID")),
		("emp:name", _("Employee Name")), ("emp:branch", _("Branch")),
		("emp:department", _("Department")), ("emp:structure", _("Salary Structure")),
	]
	keys = [k for k, _l in fixed] + grid.ordered()
	labels = dict(fixed)
	letter = {key: get_column_letter(i) for i, key in enumerate(keys, start=1)}

	# Headers, with one merged band per group.
	start = 1
	for i, key in enumerate(keys, start=1):
		group = "emp" if key.startswith("emp:") else grid.columns[key].group
		_k, _title, head, _light = GROUP[group]
		cell = ws.cell(row=HEAD_ROW, column=i, value=labels.get(key) or grid.columns[key].label)
		cell.font, cell.fill, cell.border = st.white_bold, st.fill(head), st.border
		cell.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
		next_group = None
		if i < len(keys):
			nk = keys[i]
			next_group = "emp" if nk.startswith("emp:") else grid.columns[nk].group
		if next_group != group:
			if i > start:
				ws.merge_cells(start_row=GROUP_ROW, start_column=start, end_row=GROUP_ROW, end_column=i)
			g = ws.cell(row=GROUP_ROW, column=start, value=GROUP[group][1])
			g.font, g.fill = st.white_bold, st.fill(head)
			g.alignment = Alignment(horizontal="center")
			start = i + 1

	def place(expr, r):
		return REF.sub(lambda m: f"{letter[m.group(1)]}{r}", expr)

	first = HEAD_ROW + 1
	for n, (s, row) in enumerate(grid.rows):
		r = first + n
		values = {
			"emp:sn": n + 1, "emp:employee": s.employee,
			"emp:name": s.employee_name, "emp:branch": s.branch,
			"emp:department": _department_name(s.department), "emp:structure": s.salary_structure,
		}
		for i, key in enumerate(keys, start=1):
			cell = ws.cell(row=r, column=i)
			cell.border = st.border
			if key in values:
				cell.value = values[key]
				cell.fill = st.fill(GROUP["emp"][3])
				continue
			col = grid.columns[key]
			cell.number_format = FORMATS[col.fmt]
			if key not in row.cells:
				cell.fill = st.fill("FFFFFF")
				continue
			value = row.cells[key]
			if isinstance(value, str) and value.startswith("="):
				cell.value = place(value, r)
				cell.fill = st.fill(GROUP[col.group][3])
			else:
				cell.value = value
				cell.fill = st.fill(
					STATIC_FILL if key in row.static
					else GROUP["chk"][3] if col.group == "chk"
					else INPUT_FILL
				)
			if key in row.notes:
				cell.comment = Comment(row.notes[key], "ERP")
				cell.fill = st.fill(STATIC_FILL)
			if key in ("tot:net", "tax:tds"):
				cell.font = Font(bold=True, color="1F4E79")

	last = first + len(grid.rows) - 1
	total_row = last + 1
	ws.cell(row=total_row, column=3, value=_("Total")).font = st.bold
	for i, key in enumerate(keys, start=1):
		cell = ws.cell(row=total_row, column=i)
		cell.font, cell.fill, cell.border = st.bold, st.fill("D5D8DC"), st.border
		if key in grid.columns and grid.columns[key].total:
			cell.value = f"=SUM({letter[key]}{first}:{letter[key]}{last})"
			cell.number_format = NP_MONEY_FORMAT

	red = st.fill("F5B7B1")
	for key in keys:
		if key.startswith("chk:") and key.endswith("_diff"):
			ref = f"{letter[key]}{first}:{letter[key]}{last}"
			ws.conditional_formatting.add(ref, FormulaRule(formula=[f"ABS({letter[key]}{first})>1"], fill=red))

	widths = {
		"emp:sn": 5, "emp:employee": 12, "emp:name": 24,
		"emp:branch": 16, "emp:department": 20, "emp:structure": 22,
	}
	for key in keys:
		ws.column_dimensions[letter[key]].width = widths.get(key, 13)
	ws.row_dimensions[HEAD_ROW].height = 60
	ws.freeze_panes = ws.cell(row=first, column=4)


def _legend_sheet(ws):
	from openpyxl.styles import Font

	st = _styles()
	ws["A1"] = _("How to read this workbook")
	ws["A1"].font = Font(bold=True, size=14, color="1F4E79")
	lines = [
		(INPUT_FILL, _("Yellow: an input. Change it and everything after it in the row recalculates.")),
		("EBF5FB", _("Blue: a component's full-month amount from its Salary Structure formula and condition.")),
		("E9F7EF", _("Green / red: what the slip pays and deducts this month, after leave and late.")),
		("F4ECF7", _("Purple: the annual tax projection and this month's TDS.")),
		(STATIC_FILL, _("Orange: an ERP figure the workbook could not turn into a formula; hover for why. It does not recalculate.")),
		("F5B7B1", _("Red in Check: the workbook and the ERP differ by more than 1.")),
	]
	r = 3
	for colour, text in lines:
		ws.cell(row=r, column=1).fill = st.fill(colour)
		ws.cell(row=r, column=2, value=text)
		r += 1
	r += 1
	notes = [
		_("Day counts come from attendance in the ERP. Changing one recalculates the money, not the attendance: Payment Days does not follow Absent Days, and the LWP-on-Gross rule is not re-checked."),
		_("Earlier months of the fiscal year are one input each (income, retirement contributions, TDS paid), worked back from the slip so the row matches the ERP. This month moves with its actual amounts; the rest of the year with the full-month contract amounts, as the ERP projects it."),
		_("Leave and late is split across earnings to the paisa in the ERP; the workbook rounds each share, so it can differ by a paisa."),
		_("The ERP projects CIT month by month from each employee's CIT elections; changing CIT here applies it to every remaining month."),
		_("The Settings sheet holds the retirement ceiling, the SSF-base switches and each Income Tax Slab; changes there apply to every row."),
		_("Draft slips may still change in the ERP."),
	]
	for text in notes:
		ws.cell(row=r, column=2, value="• " + text)
		r += 1
	ws.column_dimensions["A"].width = 4
	ws.column_dimensions["B"].width = 140
