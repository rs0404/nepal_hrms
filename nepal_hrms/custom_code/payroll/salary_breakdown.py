# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Nepal salary breakdown on Salary Structure Assignment.

The invariant this module maintains is:

    base == basic_salary + dearness_allowance + grade + sum(allowances)

`base` stays the single number that stock HRMS tooling understands (Bulk Salary
Structure Assignment writes only `base` and `variable`, and its signature is
fixed), so the sync runs in whichever direction the user worked:

* breakdown filled  -> base is recomputed from it
* only base filled  -> the breakdown is derived from base using the configured
  basic percentage, remainder parked on the Other Allowance component

Basic remuneration (the SSF / PF / gratuity / festival / overtime base) is
deliberately *not* the same as base: by default it is basic + grade. Dearness
Allowance is part of the statutory minimum wage but not of basic remuneration.
Both are toggles in Nepal HRMS Settings.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

OTHER_ALLOWANCE_COMPONENT = "Other Allowance"


def _settings():
	from nepal_hrms.custom_code.attendance_policy import get_hr_settings

	return get_hr_settings()


def get_daily_divisor(settings=None, fallback_working_days=None):
	"""Deprecated shim. Use period.resolve_daily_divisor(), which knows the
	payroll period and any per-period override."""
	settings = settings if settings is not None else _settings()
	fixed = cint(settings.get("daily_rate_fixed_days") or 30) or 30
	return flt(fallback_working_days) if settings.get("daily_rate_basis") == "Working Days in Period" and flt(fallback_working_days) else flt(fixed)


def compute_basic_remuneration(basic, dearness_allowance, grade, settings=None):
	"""Contribution base for SSF / PF / Gratuity."""
	settings = settings if settings is not None else _settings()
	total = flt(basic)
	if cint(settings.get("include_grade_in_ssf_base") if settings.get("include_grade_in_ssf_base") is not None else 1):
		total += flt(grade)
	if cint(settings.get("include_da_in_ssf_base") or 0):
		total += flt(dearness_allowance)
	return flt(total, 2)


def _allowance_total(doc):
	return flt(sum(flt(r.amount) for r in (doc.get("custom_allowances") or [])), 2)


def _has_breakdown(doc):
	return bool(
		flt(doc.get("custom_basic_salary"))
		or flt(doc.get("custom_dearness_allowance"))
		or flt(doc.get("custom_grade_amount"))
		or (doc.get("custom_allowances") or [])
	)


def _derive_from_base(doc, settings):
	"""Only `base` was given (typically Bulk Salary Structure Assignment)."""
	base = flt(doc.base)
	if base <= 0:
		return

	percent = flt(settings.get("default_basic_percent") or 60)
	if percent <= 0 or percent > 100:
		percent = 60.0

	basic = flt(base * percent / 100.0, 2)
	doc.custom_basic_salary = basic
	doc.custom_dearness_allowance = 0
	doc.custom_grade_amount = 0

	remainder = flt(base - basic, 2)
	if remainder <= 0:
		return

	# Park the remainder on a real component so the invariant holds and the
	# number stays visible. If the component is missing, fold it into basic
	# rather than silently losing it.
	if frappe.db.exists("Salary Component", OTHER_ALLOWANCE_COMPONENT):
		doc.append(
			"custom_allowances",
			{"salary_component": OTHER_ALLOWANCE_COMPONENT, "amount": remainder},
		)
	else:
		doc.custom_basic_salary = base


def validate_minimum_wage(doc, settings=None):
	"""Labour Act minimum remuneration floor. Rates are revised biennially, so
	they live in Nepal HRMS Settings rather than in code."""
	settings = settings if settings is not None else _settings()
	if not cint(settings.get("enforce_minimum_wage") or 0):
		return

	basic = flt(doc.get("custom_basic_salary"))
	da = flt(doc.get("custom_dearness_allowance"))
	if basic <= 0 and da <= 0:
		return  # nothing entered yet; not our error to raise

	min_total = flt(settings.get("minimum_monthly_remuneration") or 0)
	min_basic = flt(settings.get("minimum_monthly_basic") or 0)

	if min_total and (basic + da) < min_total:
		frappe.throw(
			_(
				"Basic Salary + Dearness Allowance ({0}) is below the statutory minimum monthly remuneration ({1})."
			).format(frappe.format_value(basic + da, {"fieldtype": "Currency"}),
					 frappe.format_value(min_total, {"fieldtype": "Currency"})),
			title=_("Minimum Wage"),
		)

	if min_basic and basic < min_basic:
		frappe.throw(
			_("Basic Salary ({0}) is below the statutory minimum basic ({1}).").format(
				frappe.format_value(basic, {"fieldtype": "Currency"}),
				frappe.format_value(min_basic, {"fieldtype": "Currency"}),
			),
			title=_("Minimum Wage"),
		)


def sync_salary_breakdown(doc, method=None):
	"""Salary Structure Assignment validate hook."""
	if not doc.meta.has_field("custom_basic_salary"):
		return  # custom fields not installed yet

	settings = _settings()

	validate_allowance_rows(doc)

	if _has_breakdown(doc):
		allowances = _allowance_total(doc)
		total = flt(
			flt(doc.custom_basic_salary)
			+ flt(doc.custom_dearness_allowance)
			+ flt(doc.custom_grade_amount)
			+ allowances,
			2,
		)
		doc.base = total
	else:
		_derive_from_base(doc, settings)
		allowances = _allowance_total(doc)

	doc.custom_total_allowances = allowances
	doc.custom_basic_remuneration = compute_basic_remuneration(
		doc.custom_basic_salary, doc.custom_dearness_allowance, doc.custom_grade_amount, settings
	)
	doc.custom_total_fixed_remuneration = flt(
		flt(doc.custom_basic_salary)
		+ flt(doc.custom_dearness_allowance)
		+ flt(doc.custom_grade_amount)
		+ allowances,
		2,
	)

	validate_minimum_wage(doc, settings)


ALLOWANCE_PREFIX = "nsa_"
# Canonical formula key used by setup.py / salary_component.py for every
# "Other Allowance - {Salary|Wages}" earning row. Assignment child rows may
# carry a different abbr (legacy "Other Allowance" is other_allowance_6;
# the variant component is other_allowance_wages), so those amounts must
# also be aliased here or eval raises NameError.
OTHER_ALLOWANCE_FORMULA_KEY = f"{ALLOWANCE_PREFIX}other_allowance"


def _is_other_allowance_component(name):
	name = (name or "").strip()
	return name == OTHER_ALLOWANCE_COMPONENT or name.startswith("Other Allowance - ")


def get_allowance_map(salary_structure_assignment):
	"""{nsa_<abbr>: amount} for the child rows, for injection into formula context.

	SalarySlip already pulls every SSA *field* into the eval data (it selects
	"*"), but not child tables, so only these need adding.

	Keys are prefixed because get_component_abbr_map() already seeds the bare
	abbr of every Salary Component to 0 -- an unprefixed "other_allowance" would
	collide with the Other Allowance component's own abbr. Formulas therefore
	reference e.g. `nsa_other_allowance`. `total_other_allowances` is also
	provided for the sum.
	"""
	if not salary_structure_assignment:
		return {OTHER_ALLOWANCE_FORMULA_KEY: 0.0, "total_other_allowances": 0.0}
	try:
		rows = frappe.get_all(
			"Nepal Salary Allowance",
			filters={"parent": salary_structure_assignment, "parenttype": "Salary Structure Assignment"},
			fields=["abbr", "salary_component", "amount"],
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Nepal salary allowance lookup failed")
		return {OTHER_ALLOWANCE_FORMULA_KEY: 0.0, "total_other_allowances": 0.0}

	out = {}
	total = 0.0
	for r in rows:
		key = (r.abbr or "").strip() or frappe.scrub(r.salary_component or "")
		if not key:
			continue
		key = f"{ALLOWANCE_PREFIX}{key}"
		amount = flt(r.amount)
		out[key] = flt(out.get(key, 0)) + amount
		total += amount
		if _is_other_allowance_component(r.salary_component):
			out[OTHER_ALLOWANCE_FORMULA_KEY] = flt(out.get(OTHER_ALLOWANCE_FORMULA_KEY, 0)) + amount
	out.setdefault(OTHER_ALLOWANCE_FORMULA_KEY, 0.0)
	out["total_other_allowances"] = flt(total, 2)
	return out


# ---------------------------------------------------------------------------
# User-defined allowances
#
# Any Salary Component can be used as an allowance -- no schema change is needed
# to add one. The component's *abbr* is the stable formula key (`nsa_<abbr>`),
# deliberately separate from its label: renaming the component through the Desk
# updates every link by rename cascade while the abbr, and therefore every
# formula, stays intact. Renaming is safe; editing an abbr in use is not.
# ---------------------------------------------------------------------------


def _structure_earning_components(salary_structure):
	if not salary_structure:
		return set()
	rows = frappe.get_all(
		"Salary Detail",
		filters={
			"parent": salary_structure,
			"parenttype": "Salary Structure",
			"parentfield": "earnings",
		},
		pluck="salary_component",
	)
	return {r for r in rows if r}


def validate_allowance_rows(doc):
	"""Keep abbrs populated and catch allowances that would never be paid."""
	rows = doc.get("custom_allowances") or []
	if not rows:
		return

	structure_components = _structure_earning_components(doc.get("salary_structure"))
	seen = {}
	missing_from_structure = []

	for row in rows:
		if not row.salary_component:
			continue

		comp = frappe.db.get_value(
			"Salary Component",
			row.salary_component,
			["salary_component_abbr", "type"],
			as_dict=True,
		) or frappe._dict()

		if (comp.get("type") or "") != "Earning":
			frappe.throw(
				_("Allowance row {0}: {1} is not an Earning component.").format(
					row.idx, frappe.bold(row.salary_component)
				),
				title=_("Invalid Allowance"),
			)

		# The abbr is the formula key. Never leave it blank and never let a stale
		# value survive, or `nsa_<abbr>` stops resolving after a rename.
		if not comp.get("salary_component_abbr"):
			frappe.throw(
				_(
					"Salary Component {0} has no abbreviation. Set one before using it as an allowance -- it is the formula key."
				).format(frappe.bold(row.salary_component)),
				title=_("Missing Abbreviation"),
			)
		row.abbr = comp.get("salary_component_abbr")

		if row.abbr in seen and seen[row.abbr] != row.salary_component:
			frappe.throw(
				_("Allowance rows {0} and {1} share the abbreviation {2}.").format(
					seen[row.abbr], row.salary_component, frappe.bold(row.abbr)
				),
				title=_("Duplicate Abbreviation"),
			)
		seen[row.abbr] = row.salary_component

		if structure_components and row.salary_component not in structure_components:
			missing_from_structure.append(row.salary_component)

	if missing_from_structure:
		# The amount still counts toward base (so deduction rates stay right) but
		# no earning line is produced -- the employee would not actually be paid it.
		frappe.msgprint(
			_(
				"These allowances are not in Salary Structure {0}, so they will raise Base but will not be paid: {1}"
			).format(
				frappe.bold(doc.get("salary_structure")),
				", ".join(frappe.bold(c) for c in missing_from_structure),
			),
			title=_("Allowance Not On Structure"),
			indicator="orange",
		)


@frappe.whitelist()
def create_allowance_component(label, abbr=None, is_tax_applicable=1, add_to_structures=None):
	"""Create a correctly wired Nepal allowance component from a free-form label.

	The label is whatever the user wants to see on the payslip; the abbr is the
	stable formula key. Returns the component name.
	"""
	frappe.has_permission("Salary Component", "create", throw=True)

	label = (label or "").strip()
	if not label:
		frappe.throw(_("Allowance name is required"))

	if frappe.db.exists("Salary Component", label):
		frappe.throw(_("Salary Component {0} already exists.").format(frappe.bold(label)))

	abbr = (abbr or "").strip() or frappe.scrub(label)
	clash = frappe.db.get_value("Salary Component", {"salary_component_abbr": abbr}, "name")
	if clash:
		frappe.throw(
			_("Abbreviation {0} is already used by {1}. Choose another.").format(
				frappe.bold(abbr), frappe.bold(clash)
			)
		)

	doc = frappe.get_doc(
		{
			"doctype": "Salary Component",
			"salary_component": label,
			"salary_component_abbr": abbr,
			"type": "Earning",
			"amount_based_on_formula": 1,
			"formula": f"{ALLOWANCE_PREFIX}{abbr}",
			# Absence is handled wholly by the Leave and Late Deduction component;
			# prorating here as well would deduct twice for the same day.
			"depends_on_payment_days": 0,
			"is_tax_applicable": cint(is_tax_applicable),
			"remove_if_zero_valued": 1,
			"exempted_from_income_tax": 0,
			"description": _("Nepal allowance. Amount comes from the Salary Structure Assignment breakdown."),
		}
	)
	doc.insert(ignore_permissions=True)

	if add_to_structures:
		if isinstance(add_to_structures, str):
			add_to_structures = frappe.parse_json(add_to_structures)
		for structure in add_to_structures or []:
			add_component_to_structure(structure, doc.name)

	return doc.name


def add_component_to_structure(salary_structure, salary_component):
	"""Append an earning row to a Salary Structure if it is not already there."""
	if not frappe.db.exists("Salary Structure", salary_structure):
		return False
	if frappe.db.exists(
		"Salary Detail",
		{
			"parent": salary_structure,
			"parenttype": "Salary Structure",
			"parentfield": "earnings",
			"salary_component": salary_component,
		},
	):
		return False

	comp = frappe.db.get_value(
		"Salary Component",
		salary_component,
		["salary_component_abbr", "formula", "amount_based_on_formula"],
		as_dict=True,
	)
	structure = frappe.get_doc("Salary Structure", salary_structure)
	structure.append(
		"earnings",
		{
			"salary_component": salary_component,
			"abbr": comp.get("salary_component_abbr"),
			"formula": comp.get("formula"),
			"amount_based_on_formula": cint(comp.get("amount_based_on_formula")),
		},
	)
	structure.save(ignore_permissions=True)
	return True
