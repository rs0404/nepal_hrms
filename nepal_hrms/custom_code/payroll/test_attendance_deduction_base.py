from frappe.tests.utils import FrappeTestCase

from nepal_hrms.overrides.salary_slip import (
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

	def test_unknown_selection_preserves_legacy_basic_base(self):
		self.assertEqual(self.resolve(""), 51_000)
