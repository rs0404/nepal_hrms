"""Payroll setup runs for the companies and structures picked in the dialog.

Before anything is created, the dialog asks which mapping rows the picked
structures still lack, so a component is never created without an account
unless the user chose to.
"""

from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.custom_code.payroll import setup

SSF_SALARY = "Nepal Payroll - SSF - Salary"
PF_WAGES = "Nepal Payroll - PF & Gratuity - Wages"
CO = "Test Co"


class TestResolveStructures(TestCase):
	def test_nothing_picked_means_all_four(self):
		self.assertEqual(
			setup._resolve_structures(None),
			{"SSF": ["Salary", "Wages"], "PF": ["Salary", "Wages"]},
		)

	def test_ssf_only(self):
		self.assertEqual(
			setup._resolve_structures([SSF_SALARY, "Nepal Payroll - SSF - Wages"]),
			{"SSF": ["Salary", "Wages"]},
		)

	def test_accepts_the_json_string_frappe_call_sends(self):
		self.assertEqual(
			setup._resolve_structures(frappe.as_json([PF_WAGES, SSF_SALARY])),
			{"SSF": ["Salary"], "PF": ["Wages"]},
		)

	def test_unknown_structure_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			setup._resolve_structures(["Nepal Payroll - Contract - Salary"])


class TestComponentPlan(TestCase):
	def test_only_the_picked_variant_is_planned(self):
		names = [spec["name"] for spec, _p, _v in setup._component_plan("SSF", ["Salary"], 1.5)]
		self.assertIn("Basic Salary - Salary", names)
		self.assertNotIn("Basic Salary - Wages", names)
		self.assertIn("Employee's Contribution SSF", names)
		self.assertNotIn("Provident Fund Employee", names)

	def test_every_component_has_a_purpose(self):
		for spec, purposes, _v in setup._component_plan("PF", ["Salary", "Wages"], 1.5):
			self.assertTrue(purposes, spec["name"])


class TestUnmappedPurposes(TestCase):
	def _unmapped(self, accounts, existing=()):
		def exists(doctype, filters=None, *args, **kwargs):
			if doctype == "Salary Component Account":
				return (filters["parent"], filters["company"]) in existing
			return True

		with (
			patch.object(setup, "_account_map", return_value=accounts),
			patch.object(setup, "_settings", return_value=frappe._dict()),
			patch.object(setup.frappe, "only_for"),
			patch.object(setup.frappe.db, "exists", side_effect=exists),
		):
			return setup.get_unmapped_purposes([CO], [SSF_SALARY])

	def test_nothing_mapped_asks_for_each_purpose_once(self):
		missing = self._unmapped({})
		purposes = [m["purpose"] for m in missing]
		self.assertEqual(len(purposes), len(set(purposes)))
		self.assertEqual(
			set(purposes),
			{"Salary Expense", "TDS Payable", "CIT Payable", "Insurance Payable", "SSF Payable"},
		)
		self.assertTrue(all(m["company"] == CO for m in missing))

	def test_wages_purposes_are_not_asked_for_a_salary_only_run(self):
		purposes = {m["purpose"] for m in self._unmapped({})}
		self.assertNotIn("Wages Expense", purposes)

	def test_employer_contribution_is_covered_by_its_specific_purpose(self):
		accounts = {
			(CO, p): "X"
			for p in ("TDS Payable", "CIT Payable", "Insurance Payable", "SSF Payable")
		}
		accounts[(CO, "Employer SSF Expense (Salary)")] = "Employer SSF"
		missing = self._unmapped(accounts)
		# The employer SSF earning is covered; everything else on the wage bill is not.
		self.assertEqual(missing, [{"company": CO, "purpose": "Salary Expense"}])

	def test_component_that_already_has_an_account_is_covered(self):
		accounts = {(CO, "Salary Expense"): "Salaries"}
		existing = {
			(name, CO)
			for name in ("TDS", "CIT", "Insurance", "Employee's Contribution SSF",
			             "Employer's Contribution SSF Deduction")
		}
		self.assertEqual(self._unmapped(accounts, existing), [])
