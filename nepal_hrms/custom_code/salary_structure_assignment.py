# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def _settings_default_formula():
	from nepal_hrms.custom_code.attendance_policy import get_hr_settings

	formula = (get_hr_settings().get("default_leave_encashment_formula") or "").strip()
	if formula:
		return formula
	# Singles only store saved values; fall back to the DocType field default.
	try:
		df = frappe.get_meta("Nepal HRMS Settings").get_field("default_leave_encashment_formula")
		return (df.default or "").strip() if df else ""
	except Exception:
		return ""


def resolve_leave_encashment_formula(doc):
	"""Assignment → Structure → Nepal HRMS Settings (eval fallback only)."""
	formula = (doc.get("custom_leave_encashment_formula") or "").strip()
	if formula:
		return formula

	if doc.salary_structure:
		formula = (
			frappe.db.get_value(
				"Salary Structure", doc.salary_structure, "custom_leave_encashment_formula"
			)
			or ""
		).strip()
		if formula:
			return formula

	return _settings_default_formula()


def build_leave_encashment_context(doc):
	"""Safe-eval locals for Leave Encashment Per Day formulas."""
	base = flt(doc.base)
	context = {
		"base": base,
		"revised_salary": base,
		# Assignment breakdown (synced before this validate runs)
		"custom_basic_salary": flt(doc.get("custom_basic_salary")),
		"custom_dearness_allowance": flt(doc.get("custom_dearness_allowance")),
		"custom_grade_amount": flt(doc.get("custom_grade_amount")),
		"custom_basic_remuneration": flt(doc.get("custom_basic_remuneration")),
		"custom_total_allowances": flt(doc.get("custom_total_allowances")),
		"custom_total_fixed_remuneration": flt(doc.get("custom_total_fixed_remuneration")),
	}
	# Short aliases used in help text / common formulas
	context.update(
		{
			"basic_salary": context["custom_basic_salary"],
			"dearness_allowance": context["custom_dearness_allowance"],
			"grade_amount": context["custom_grade_amount"],
			"grade": context["custom_grade_amount"],
			"basic_remuneration": context["custom_basic_remuneration"],
			"total_allowances": context["custom_total_allowances"],
			"total_fixed_remuneration": context["custom_total_fixed_remuneration"],
		}
	)

	try:
		from nepal_hrms.custom_code.payroll.salary_breakdown import (
			ALLOWANCE_PREFIX,
			OTHER_ALLOWANCE_FORMULA_KEY,
			_is_other_allowance_component,
			get_allowance_map,
		)

		# Prefer in-memory child rows (covers new docs and unsaved edits).
		rows = doc.get("custom_allowances") or []
		if rows:
			total = 0.0
			for row in rows:
				key = (row.abbr or "").strip() or frappe.scrub(row.salary_component or "")
				if not key:
					continue
				amount = flt(row.amount)
				prefixed = f"{ALLOWANCE_PREFIX}{key}"
				context[prefixed] = flt(context.get(prefixed, 0)) + amount
				total += amount
				if _is_other_allowance_component(row.salary_component):
					context[OTHER_ALLOWANCE_FORMULA_KEY] = (
						flt(context.get(OTHER_ALLOWANCE_FORMULA_KEY, 0)) + amount
					)
			context.setdefault(OTHER_ALLOWANCE_FORMULA_KEY, 0.0)
			context["total_other_allowances"] = flt(total, 2)
		elif not doc.is_new() and doc.name:
			context.update(get_allowance_map(doc.name))

		if "total_other_allowances" in context:
			context["custom_total_allowances"] = context["total_other_allowances"]
			context["total_allowances"] = context["total_other_allowances"]
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Leave encashment allowance context failed")

	if doc.salary_structure:
		details = frappe.get_all(
			"Salary Detail",
			filters={"parent": doc.salary_structure},
			fields=["abbr", "formula", "amount"],
		)
		# Multi-pass so dependent structure formulas can resolve
		for _ in range(3):
			for d in details:
				abbr = (d.abbr or "").strip()
				if not abbr or abbr in context:
					continue
				try:
					if d.formula:
						context[abbr] = frappe.safe_eval(d.formula, None, context)
					else:
						context[abbr] = flt(d.amount)
				except Exception:
					pass

	return context


def validate_leave_encashment(doc, method=None):
	formula = resolve_leave_encashment_formula(doc)
	if not formula:
		return

	context = build_leave_encashment_context(doc)
	try:
		encashment_value = frappe.safe_eval(formula, None, context)
		doc.leave_encashment_amount_per_day = flt(encashment_value)
	except Exception as e:
		frappe.throw(
			_("Invalid Leave Encashment Formula: {0}").format(str(e)),
			title=_("Leave Encashment Formula"),
		)
