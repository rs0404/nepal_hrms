"""Employer contributions can draw their own expense account.

SSF, employer PF and gratuity are the company's cost, not part of what the
employee earns, so a site may want them off the wage bill. Each looks for its
own purpose, then the generic one, then the variant expense account -- and a
site that maps none of them must keep posting exactly where it always did.
"""

from unittest import TestCase

from nepal_hrms.custom_code.payroll.setup import (
	EMPLOYER_EXPENSE_PURPOSE,
	GENERIC_EMPLOYER_PURPOSE,
	VARIANTS,
	_expense_purposes,
)

CO = "Test Co"


def _resolve(component, variant, accounts):
	"""The account _apply_account would pick for CO, without touching the DB."""
	for purpose in _expense_purposes(component, variant):
		if (CO, purpose) in accounts:
			return accounts[(CO, purpose)]
	return None


class TestOrdinaryComponents(TestCase):
	"""Anything that is not an employer contribution still follows the variant."""

	def test_basic_salary_uses_the_variant_expense(self):
		self.assertEqual(_expense_purposes("Basic Salary - Salary", "Salary"), ("Salary Expense",))
		self.assertEqual(_expense_purposes("Basic Salary - Wages", "Wages"), ("Wages Expense",))

	def test_overtime_is_not_an_employer_contribution(self):
		self.assertEqual(_expense_purposes("Overtime - Wages", "Wages"), ("Wages Expense",))

	def test_a_name_ending_in_salary_is_not_mangled(self):
		"""'Basic Salary - Salary' must strip only the variant suffix."""
		self.assertEqual(_expense_purposes("Basic Salary - Salary", "Salary"), ("Salary Expense",))


class TestEmployerContributions(TestCase):
	def test_every_employer_contribution_has_a_variant_purpose(self):
		for base, purpose in EMPLOYER_EXPENSE_PURPOSE.items():
			for variant in VARIANTS:
				chain = _expense_purposes(f"{base} - {variant}", variant)
				self.assertEqual(chain[0], f"{purpose} ({variant})")
				self.assertEqual(chain[1], GENERIC_EMPLOYER_PURPOSE)
				self.assertEqual(chain[2], f"{variant} Expense")

	def test_ssf_salary_and_wages_are_distinct_purposes(self):
		salary = _expense_purposes("Employer's Contribution SSF - Salary", "Salary")[0]
		wages = _expense_purposes("Employer's Contribution SSF - Wages", "Wages")[0]
		self.assertNotEqual(salary, wages)
		self.assertEqual(salary, "Employer SSF Expense (Salary)")
		self.assertEqual(wages, "Employer SSF Expense (Wages)")

	def test_pf_employer_and_gratuity_are_covered(self):
		self.assertEqual(
			_expense_purposes("Provident Fund Employer - Salary", "Salary")[0],
			"Provident Fund Employer Expense (Salary)",
		)
		self.assertEqual(
			_expense_purposes("Gratuity - Wages", "Wages")[0], "Gratuity Expense (Wages)"
		)

	def test_employee_ssf_deduction_is_untouched(self):
		"""The contra is a liability and keeps its own purpose; only earnings are here."""
		self.assertEqual(
			_expense_purposes("Employer's Contribution SSF Deduction", "Salary"),
			("Salary Expense",),
		)


class TestResolutionOrder(TestCase):
	SSF = "Employer's Contribution SSF - Salary"

	def test_unmapped_falls_back_to_the_wage_bill(self):
		"""The guarantee: mapping nothing new must not move an existing posting."""
		self.assertEqual(
			_resolve(self.SSF, "Salary", {(CO, "Salary Expense"): "5100 - Salaries"}),
			"5100 - Salaries",
		)

	def test_generic_purpose_beats_the_wage_bill(self):
		self.assertEqual(
			_resolve(self.SSF, "Salary", {
				(CO, "Salary Expense"): "5100 - Salaries",
				(CO, GENERIC_EMPLOYER_PURPOSE): "5200 - Employer Contributions",
			}),
			"5200 - Employer Contributions",
		)

	def test_specific_purpose_beats_the_generic_one(self):
		self.assertEqual(
			_resolve(self.SSF, "Salary", {
				(CO, "Salary Expense"): "5100 - Salaries",
				(CO, GENERIC_EMPLOYER_PURPOSE): "5200 - Employer Contributions",
				(CO, "Employer SSF Expense (Salary)"): "5210 - Employer SSF",
			}),
			"5210 - Employer SSF",
		)

	def test_the_wages_mapping_does_not_leak_into_salary(self):
		self.assertEqual(
			_resolve(self.SSF, "Salary", {
				(CO, "Salary Expense"): "5100 - Salaries",
				(CO, "Employer SSF Expense (Wages)"): "5211 - Employer SSF Wages",
			}),
			"5100 - Salaries",
		)

	def test_nothing_mapped_at_all_yields_no_account(self):
		self.assertIsNone(_resolve(self.SSF, "Salary", {}))


class TestPayrollAccountDocType(TestCase):
	"""The dropdown and the grid have to keep up with the code.

	A purpose the code looks for but the Select does not offer can never be
	mapped, and the grid silently drops any column that overflows its budget --
	both fail quietly, which is why they are pinned here.
	"""

	@staticmethod
	def _doctype():
		import json
		import os

		path = os.path.join(
			os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
			"nepal_hrms",
			"doctype",
			"nepal_payroll_account",
			"nepal_payroll_account.json",
		)
		with open(path, encoding="utf-8") as f:
			return json.load(f)

	def _field(self, fieldname):
		return next(f for f in self._doctype()["fields"] if f["fieldname"] == fieldname)

	def _options(self):
		return set(self._field("purpose")["options"].split("\n"))

	def test_grid_shows_every_listed_column(self):
		"""frappe grid.js starts the tally at 1 and drops the field that passes 11.

		It returns out of the loop, so the overflowing column and everything
		after it disappear -- which is how Account went missing from the grid.
		"""
		total = 1
		for field in self._doctype()["fields"]:
			if field.get("in_list_view"):
				total += field["columns"]
		self.assertLessEqual(
			total, 11, "grid column budget exceeded; a column will be dropped silently"
		)

	def test_account_is_in_the_grid(self):
		self.assertTrue(self._field("account").get("in_list_view"))

	def test_every_employer_purpose_is_offered(self):
		options = self._options()
		for base, purpose in EMPLOYER_EXPENSE_PURPOSE.items():
			for variant in VARIANTS:
				self.assertIn(f"{purpose} ({variant})", options, f"{base} / {variant}")

	def test_the_generic_and_fallback_purposes_are_offered(self):
		options = self._options()
		self.assertIn(GENERIC_EMPLOYER_PURPOSE, options)
		for variant in VARIANTS:
			self.assertIn(f"{variant} Expense", options)

	def test_no_purpose_the_code_resolves_is_missing(self):
		"""Walk every chain the resolver can produce and check the dropdown offers it."""
		options = self._options()
		names = [f"{base} - {v}" for base in EMPLOYER_EXPENSE_PURPOSE for v in VARIANTS]
		names += [f"Basic Salary - {v}" for v in VARIANTS]
		for name in names:
			variant = name.rsplit(" - ", 1)[1]
			for purpose in _expense_purposes(name, variant):
				self.assertIn(purpose, options, f"{name} resolves to unmappable {purpose!r}")
