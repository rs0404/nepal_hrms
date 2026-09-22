"""An Additional Salary must not name the opposite component variant.

The twins pay identical amounts, so the only thing a mismatch breaks is the
expense account -- which nobody sees until the accrual JE is booked. The rules
that matter here are the two name parsers and the "not the opposite variant"
formulation that keeps shared liability components available to everyone.
"""

from unittest import TestCase

from nepal_hrms.custom_code.payroll.component_variant import (
	component_variant,
	opposite_variant,
	structure_variant,
	twin_component,
)


class TestStructureVariant(TestCase):
	def test_reads_the_variant_out_of_a_nepal_structure(self):
		self.assertEqual(
			structure_variant("Nepal Payroll - SSF - Salary - Yarsa Tech Pvt. Ltd."), "Salary"
		)
		self.assertEqual(
			structure_variant("Nepal Payroll - PF & Gratuity - Wages - Yarsa Tech Pvt. Ltd."), "Wages"
		)

	def test_a_structure_built_outside_setup_opts_out(self):
		self.assertIsNone(structure_variant("Consultant Retainer"))
		self.assertIsNone(structure_variant(None))

	def test_the_marker_is_not_matched_at_the_tail(self):
		# " - Salary" ending a structure name is not the variant marker; the
		# company suffix always follows it.
		self.assertIsNone(structure_variant("Nepal Payroll - SSF - Salary"))


class TestComponentVariant(TestCase):
	def test_variant_components(self):
		self.assertEqual(component_variant("Overtime - Salary"), "Salary")
		self.assertEqual(component_variant("Advance Deduction - Wages"), "Wages")

	def test_shared_components_carry_no_variant(self):
		for shared in ("TDS", "CIT", "Insurance", "Employee's Contribution SSF"):
			self.assertIsNone(component_variant(shared))

	def test_a_suffix_that_only_looks_like_one(self):
		self.assertIsNone(component_variant("Basic Salary - Wages A/C"))


class TestTwin(TestCase):
	def test_names_the_other_variant(self):
		self.assertEqual(twin_component("Overtime - Wages", "Salary"), "Overtime - Salary")
		self.assertEqual(
			twin_component("Miscellaneous Allowance - Wages", "Salary"),
			"Miscellaneous Allowance - Salary",
		)

	def test_no_twin_when_already_correct(self):
		self.assertIsNone(twin_component("Overtime - Salary", "Salary"))

	def test_no_twin_for_a_shared_component(self):
		self.assertIsNone(twin_component("TDS", "Salary"))

	def test_opposite(self):
		self.assertEqual(opposite_variant("Salary"), "Wages")
		self.assertEqual(opposite_variant("Wages"), "Salary")


class TestFilterFormulation(TestCase):
	"""The link filter is `name not like '% - <opposite>'`. Everything the
	picker should keep must survive that, and only the twins should fall out."""

	SALARY = "Salary"
	COMPONENTS = [
		"Overtime - Salary",
		"Overtime - Wages",
		"Advance Deduction - Salary",
		"Advance Deduction - Wages",
		"TDS",
		"CIT",
		"Insurance",
		"Employee's Contribution SSF",
	]

	def _visible(self, variant):
		opposite = f" - {opposite_variant(variant)}"
		return [c for c in self.COMPONENTS if not c.endswith(opposite)]

	def test_salary_employee_sees_salary_and_shared_only(self):
		self.assertEqual(
			self._visible(self.SALARY),
			[
				"Overtime - Salary",
				"Advance Deduction - Salary",
				"TDS",
				"CIT",
				"Insurance",
				"Employee's Contribution SSF",
			],
		)

	def test_wages_employee_sees_wages_and_shared_only(self):
		self.assertEqual(
			self._visible("Wages"),
			[
				"Overtime - Wages",
				"Advance Deduction - Wages",
				"TDS",
				"CIT",
				"Insurance",
				"Employee's Contribution SSF",
			],
		)
