# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""One-click Nepal payroll setup, driven from Nepal HRMS Settings.

Creates the salary components, four salary structures, and the income tax slab,
then applies the account mapping held in settings.

Four structures, because two axes matter:

  * SSF vs PF/Gratuity -- which retirement scheme the company is registered under
  * Wages vs Salary    -- purely an accounting split. Wage workers post to the
                          wages expense account, salaried staff to the salary
                          expense account. The arithmetic is identical.

Idempotent: components and structures that already exist are updated in place,
never duplicated. Structures created outside this setup are never touched.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from nepal_hrms.custom_code.payroll.salary_component import create_salary_component

# Structure naming. Explicit over clever: scheme first, then the accounting split.
SCHEMES = {
	"SSF": "Nepal Payroll - SSF",
	"PF": "Nepal Payroll - PF & Gratuity",
}
VARIANTS = ("Salary", "Wages")

# purpose -> which components draw their account from it
EXPENSE_PURPOSE = {"Salary": "Salary Expense", "Wages": "Wages Expense"}


def _settings():
	return frappe.get_single("Nepal HRMS Settings")


def _ot_formula(multiplier):
	"""Overtime = hours x hourly basic x multiplier (Labour Act s.31 sets 1.5x)."""
	return (
		f"custom_overtime_hours * (custom_basic_remuneration / 30 / 8) * {flt(multiplier)}"
	)


def _variant_components(variant, scheme, ot_multiplier):
	"""Components that carry a Wages/Salary expense account."""
	v = variant
	comps = [
		{"name": f"Basic Salary - {v}", "type": "Earning", "formula": "custom_basic_salary",
		 "abbr": f"basic_salary_{v.lower()}",
		 "description": "आधारभूत तलब from the Salary Structure Assignment breakdown."},
		{"name": f"Dearness Allowance - {v}", "type": "Earning", "formula": "custom_dearness_allowance",
		 "abbr": f"dearness_allowance_{v.lower()}",
		 "description": "महँगी भत्ता. Part of the statutory minimum wage; excluded from the SSF/PF base."},
		{"name": f"Grade - {v}", "type": "Earning", "formula": "custom_grade_amount",
		 "abbr": f"grade_{v.lower()}", "description": "ग्रेड. Annual increment."},
		{"name": f"Other Allowance - {v}", "type": "Earning", "formula": "nsa_other_allowance",
		 "abbr": f"other_allowance_{v.lower()}",
		 "description": "From the Other Allowances table on the assignment."},
		{"name": f"Overtime - {v}", "type": "Earning", "formula": _ot_formula(ot_multiplier),
		 "abbr": f"overtime_{v.lower()}",
		 "description": "Hours x hourly basic x the multiplier in Nepal HRMS Settings."},
		{"name": f"Earning Adjustment - {v}", "type": "Earning", "formula": None,
		 "abbr": f"earning_adjustment_{v.lower()}", "description": "Manual one-off addition."},
		{"name": f"Leave and Late Deduction - {v}", "type": "Deduction",
		 "formula": LEAVE_LATE_FORMULA, "abbr": f"leave_late_deduction_{v.lower()}",
		 "description": "Late/early/OOO half-days, LWP, and unapproved absence."},
		{"name": f"Deduction Adjustment - {v}", "type": "Deduction", "formula": None,
		 "abbr": f"deduction_adjustment_{v.lower()}", "exempted_from_income_tax": 0,
		 "description": "Manual one-off deduction. Not pre-tax."},
	]
	if scheme == "SSF":
		comps.append({
			"name": f"Employer's Contribution SSF - {v}", "type": "Earning",
			"formula": "custom_basic_remuneration * 0.20",
			"abbr": f"employer_ssf_{v.lower()}",
			"description": "Employer 20% of basic remuneration, added to gross then deducted back.",
		})
	else:
		comps += [
			{"name": f"Provident Fund Employer - {v}", "type": "Earning",
			 "formula": "custom_basic_remuneration * 0.10",
			 "abbr": f"pf_employer_{v.lower()}", "description": "Employer PF 10% of basic remuneration."},
			{"name": f"Gratuity - {v}", "type": "Earning",
			 "formula": "custom_basic_remuneration * 0.0833",
			 "abbr": f"gratuity_{v.lower()}", "description": "Gratuity 8.33% of basic remuneration."},
		]
	return comps


# Shared components post to liability accounts, so they need no Wages/Salary split.
def _shared_components(scheme):
	comps = [
		{"name": "TDS", "type": "Deduction", "formula": None, "abbr": "tds",
		 "variable_based_on_taxable_salary": 1, "exempted_from_income_tax": 0,
		 "purpose": "TDS Payable",
		 "description": "Income tax withheld, computed from the Income Tax Slab."},
		{"name": "CIT", "type": "Deduction", "formula": "cit_contribution", "abbr": "cit",
		 "purpose": "CIT Payable",
		 "description": "Citizen Investment Trust. Amount comes from the employee's effective-dated CIT election and counts toward the retirement contribution ceiling."},
		{"name": "Insurance", "type": "Deduction", "formula": None, "abbr": "insurance",
		 "purpose": "Insurance Payable",
		 "description": "Life/health premium. Deductible only up to the statutory cap."},
	]
	if scheme == "SSF":
		comps += [
			{"name": "Employee's Contribution SSF", "type": "Deduction",
			 "formula": "custom_basic_remuneration * 0.11", "abbr": "employee_ssf",
			 "purpose": "SSF Payable", "description": "Employee 11% of basic remuneration."},
			{"name": "Employer's Contribution SSF Deduction", "type": "Deduction",
			 "formula": "custom_basic_remuneration * 0.20", "abbr": "employer_ssf_ded",
			 "purpose": "SSF Payable",
			 "description": "Contra for the employer 20% added to gross."},
		]
	else:
		comps += [
			{"name": "Provident Fund Employee", "type": "Deduction",
			 "formula": "custom_basic_remuneration * 0.10", "abbr": "pf_employee",
			 "purpose": "Provident Fund Payable", "description": "Employee PF 10%."},
			{"name": "Provident Fund Employer Deduction", "type": "Deduction",
			 "formula": "custom_basic_remuneration * 0.10", "abbr": "pf_employer_ded",
			 "purpose": "Provident Fund Payable", "description": "Contra for employer PF."},
			{"name": "Gratuity Deduction", "type": "Deduction",
			 "formula": "custom_basic_remuneration * 0.0833", "abbr": "gratuity_ded",
			 "purpose": "Gratuity Payable", "description": "Contra for gratuity."},
		]
	return comps


LEAVE_LATE_FORMULA = (
	"(late_entry_half_days + early_exit_half_days + out_of_office_half_days) * late_deduction_rate "
	"+ lwp_days * lwp_deduction_rate "
	"+ unapproved_absent_days * unapproved_absent_rate"
)


def _account_map(settings):
	"""{(company, purpose): account} from the settings table."""
	out = {}
	for row in settings.get("payroll_accounts") or []:
		if row.company and row.purpose and row.account:
			out[(row.company, row.purpose)] = row.account
	return out


def _apply_account(component_name, purpose, accounts):
	"""Write Salary Component Account rows for every company mapped to this purpose."""
	applied = 0
	doc = None
	for (company, mapped_purpose), account in accounts.items():
		if mapped_purpose != purpose:
			continue
		doc = doc or frappe.get_doc("Salary Component", component_name)
		existing = next((a for a in doc.accounts if a.company == company), None)
		if existing:
			if existing.account != account:
				existing.account = account
				applied += 1
		else:
			doc.append("accounts", {"company": company, "account": account})
			applied += 1
	if doc and applied:
		doc.save(ignore_permissions=True)
	return applied


def _ensure_components(scheme, ot_multiplier, accounts):
	"""Create/update every component for a scheme. Returns names by variant."""
	created = {}
	for variant in VARIANTS:
		names = []
		for spec in _variant_components(variant, scheme, ot_multiplier):
			name = _upsert(spec)
			names.append(name)
			_apply_account(name, EXPENSE_PURPOSE[variant], accounts)
		created[variant] = names

	for spec in _shared_components(scheme):
		name = _upsert(spec)
		if spec.get("purpose"):
			_apply_account(name, spec["purpose"], accounts)
		for variant in VARIANTS:
			created[variant].append(name)
	return created


def _upsert(spec):
	"""Create or update one Salary Component from a spec dict."""
	payload = {
		"name": spec["name"],
		"salary_component": spec["name"],
		"salary_component_abbr": spec["abbr"],
		"type": spec["type"],
		"formula": spec.get("formula"),
		"amount_based_on_formula": 1 if spec.get("formula") else 0,
		# Absence is handled entirely by the Leave and Late Deduction component;
		# prorating here as well would deduct twice for the same day.
		"depends_on_payment_days": 0,
		"remove_if_zero_valued": 1,
		"description": spec.get("description"),
		"variable_based_on_taxable_salary": cint(spec.get("variable_based_on_taxable_salary", 0)),
	}
	# is_income_tax_component marks *the* tax component. create_salary_component()
	# defaults it to 1 for everything, which would mislabel every deduction.
	payload["is_income_tax_component"] = cint(spec.get("variable_based_on_taxable_salary", 0))

	if spec["type"] == "Earning":
		payload["is_tax_applicable"] = 1
		# Earnings do not use exempted_from_income_tax at all (hrms applies it only
		# to deductions), but leave it off so the flag never reads as meaningful.
		payload["exempted_from_income_tax"] = 0
	else:
		# Deduction-only flag: subtracts the amount from taxable earnings. Genuine
		# pre-tax deductions (retirement, insurance) get it; ad-hoc ones must not,
		# or any amount typed into an adjustment would silently cut taxable income.
		payload["exempted_from_income_tax"] = cint(spec.get("exempted_from_income_tax", 1))
		payload["is_tax_applicable"] = 0
	create_salary_component(payload)
	return spec["name"]


def _ensure_structure(name, company, currency, components):
	"""Create or refresh one Salary Structure. Never touches structures we did not make."""
	comps = [
		frappe.db.get_value(
			"Salary Component", c,
			["name", "type", "formula", "amount_based_on_formula", "salary_component_abbr"],
			as_dict=True,
		)
		for c in components
	]
	comps = [c for c in comps if c]

	if frappe.db.exists("Salary Structure", name):
		doc = frappe.get_doc("Salary Structure", name)
		if doc.docstatus == 1:
			# Submitted: leave it alone rather than failing the whole setup run.
			return name, "skipped (submitted)"
		doc.set("earnings", [])
		doc.set("deductions", [])
		action = "updated"
	else:
		doc = frappe.new_doc("Salary Structure")
		doc.name = name
		action = "created"

	doc.company = company
	doc.currency = currency
	doc.payroll_frequency = "Monthly"
	doc.is_active = "Yes"
	doc.is_default = "No"

	for c in comps:
		doc.append(
			"earnings" if c.type == "Earning" else "deductions",
			{
				"salary_component": c.name,
				"abbr": c.salary_component_abbr,
				"formula": c.formula,
				"amount_based_on_formula": cint(c.amount_based_on_formula),
			},
		)
	doc.save(ignore_permissions=True)
	return name, action


# The slab is cloned from an existing record on the site so the rates stay under
# the payroll team's control rather than being hardcoded here. The fallback below
# mirrors "Income Tax Slab 2083/84" verbatim and is only used on a fresh site.
#
# NOTE: that record's top band reads 2%, which sits below every band under it.
# It is reproduced exactly as instructed -- if it was meant to be 29%, fix the
# source record and re-run Setup.
SOURCE_SLAB = "Income Tax Slab 2083/84"
FALLBACK_SLABS = [
	{"from_amount": 1, "to_amount": 1000000, "percent_deduction": 0},
	{"from_amount": 1000001, "to_amount": 1500000, "percent_deduction": 10},
	{"from_amount": 1500001, "to_amount": 2500000, "percent_deduction": 20},
	{"from_amount": 2500001, "to_amount": 4000001, "percent_deduction": 27},
	{"from_amount": 4000001, "to_amount": 0, "percent_deduction": 2},
]


def _source_slab_rows():
	"""Slab rows to clone, preferring the live record over the fallback."""
	if not frappe.db.exists("Income Tax Slab", SOURCE_SLAB):
		return FALLBACK_SLABS, f"fallback (no {SOURCE_SLAB} on site)"
	rows = frappe.get_all(
		"Taxable Salary Slab",
		filters={"parent": SOURCE_SLAB, "parenttype": "Income Tax Slab"},
		fields=["from_amount", "to_amount", "percent_deduction", "condition"],
		order_by="idx asc",
	)
	if not rows:
		return FALLBACK_SLABS, f"fallback ({SOURCE_SLAB} has no rows)"
	return rows, f"cloned from {SOURCE_SLAB}"


def _ensure_tax_slab(company, currency, effective_from):
	"""One slab per company. Married and unmarried share it, per policy."""
	name = f"Nepal Income Tax Slab - {company}"
	rows, provenance = _source_slab_rows()

	if frappe.db.exists("Income Tax Slab", name):
		doc = frappe.get_doc("Income Tax Slab", name)
		if doc.docstatus == 1:
			# Submitted slabs are immutable; amending is a payroll decision.
			return name, "skipped (submitted)", provenance
		action = "updated"
	else:
		doc = frappe.new_doc("Income Tax Slab")
		doc.name = name
		action = "created"

	doc.company = company
	doc.currency = currency
	doc.effective_from = effective_from
	doc.allow_tax_exemption = 1
	doc.set("slabs", [])
	for r in rows:
		doc.append("slabs", {
			"from_amount": flt(r.get("from_amount")),
			"to_amount": flt(r.get("to_amount")),
			"percent_deduction": flt(r.get("percent_deduction")),
			"condition": r.get("condition") or None,
		})
	doc.save(ignore_permissions=True)
	return name, action, provenance


@frappe.whitelist()
def setup_nepal_payroll(company=None, effective_from=None):
	"""Button target on Nepal HRMS Settings. Idempotent."""
	frappe.only_for(("System Manager", "HR Manager"))

	settings = _settings()
	accounts = _account_map(settings)
	ot_multiplier = flt(settings.get("overtime_rate_multiplier") or 1.5)

	companies = [company] if company else frappe.get_all("Company", pluck="name")
	if not companies:
		frappe.throw(_("No Company found."))

	if not effective_from:
		# Shrawan 1 of the current BS year: the Nepali fiscal year start.
		effective_from = _current_fy_start()

	log = {"components": 0, "structures": [], "tax_slabs": [], "accounts_applied": 0,
	       "account_rows": len(accounts), "companies": companies}

	seen_components = set()
	for scheme, prefix in SCHEMES.items():
		created = _ensure_components(scheme, ot_multiplier, accounts)
		for variant in VARIANTS:
			seen_components.update(created[variant])
			for comp in companies:
				currency = frappe.db.get_value("Company", comp, "default_currency") or "NPR"
				sname = f"{prefix} - {variant} - {comp}"
				name, action = _ensure_structure(sname, comp, currency, created[variant])
				log["structures"].append({"name": name, "action": action})
	log["components"] = len(seen_components)

	for comp in companies:
		currency = frappe.db.get_value("Company", comp, "default_currency") or "NPR"
		name, action, provenance = _ensure_tax_slab(comp, currency, effective_from)
		log["tax_slabs"].append({"name": name, "action": action, "source": provenance})

	frappe.db.commit()
	return log


def _current_fy_start():
	"""AD date of Shrawan 1 in the current BS year."""
	try:
		import nepal_compliance.nepali_date_utils.nepali_date as nd

		nd._ensure_loaded()
		bs = nd.ad_to_bs(frappe.utils.getdate())
		year = bs["year"] if bs["month"] >= 4 else bs["year"] - 1
		return frappe.utils.getdate(nd.bs_to_ad(year, 4, 1))
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Could not resolve BS fiscal year start")
		return frappe.utils.getdate()
