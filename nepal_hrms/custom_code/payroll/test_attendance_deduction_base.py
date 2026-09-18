from frappe.tests.utils import FrappeTestCase

from nepal_hrms.overrides.salary_slip import (
	ASSIGNMENT_BASE,
	DEFAULT_BASIC_BASE,
	GROSS_BASE,
	_get_attendance_deduction_base,
)


class TestAttendanceDeductionBase(FrappeTestCase):
	def setUp(self):
		self.amounts = {
			"basic_salary": 50_000,
			"dearness_allowance": 2_000,
			"grade": 1_000,
			"basic_remuneration": 51_000,
			"total_fixed": 80_000,
		}

	def resolve(self, selection):
		return _get_attendance_deduction_base(selection, **self.amounts)

	def test_component_presets(self):
		self.assertEqual(self.resolve("Basic Salary Only"), 50_000)
		self.assertEqual(self.resolve("Basic Salary + Grade"), 51_000)
		self.assertEqual(self.resolve("Basic Salary + Dearness Allowance"), 52_000)
		self.assertEqual(
			self.resolve("Basic Salary + Grade + Dearness Allowance"), 53_000
		)

	def test_aggregate_presets(self):
		self.assertEqual(self.resolve(DEFAULT_BASIC_BASE), 51_000)
		self.assertEqual(self.resolve(GROSS_BASE), 80_000)

	def test_assignment_base_reads_the_assignment_total(self):
		# Deliberately different from total_fixed: Gross Pay on the slip also carries
		# the employer's SSF / PF / gratuity earning, which must never widen a
		# deduction base.
		self.assertEqual(
			_get_attendance_deduction_base(
				ASSIGNMENT_BASE, **self.amounts, assignment_base=75_000
			),
			75_000,
		)

	def test_assignment_base_falls_back_when_assignment_has_no_base(self):
		self.assertEqual(self.resolve(ASSIGNMENT_BASE), 80_000)

	def test_unknown_selection_preserves_legacy_basic_base(self):
		self.assertEqual(self.resolve(""), 51_000)
