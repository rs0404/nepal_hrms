"""A new slip starts from Attendance, without anyone pressing the button."""

from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import MagicMock, patch

from frappe.utils import flt

from nepal_hrms.api.salary_slip_sync import seed_absence_from_attendance
from nepal_hrms.overrides.salary_slip import CustomSalarySlip


class _Slip:
	def __init__(self):
		self.employee = "EMP-001"
		self.start_date = "2026-08-14"
		self.end_date = "2026-09-13"
		self.absent_days = 0.0
		self.custom_total_unpaid_days = 0.0
		self.custom_absent_days_manual = 0
		self.flags = MagicMock()
		self.meta = MagicMock()
		self.meta.has_field.return_value = True

	def get(self, field, default=None):
		return getattr(self, field, default)

	@contextmanager
	def _bs_extended_period(self):
		yield

	def get_holidays_for_employee(self, _s, _e):
		return []

	def calculate_lwp_ppl_and_absent_days_based_on_attendance(self, *_a, **_k):
		return 0, 1.0

	def get_half_absent_days(self, *_a, **_k):
		return 1.0


class TestSeedAbsence(TestCase):
	def _seed(self, slip):
		with patch(
			"nepal_hrms.api.salary_slip_sync.frappe.get_single",
			return_value=MagicMock(
				daily_wages_fraction_for_half_day=0.5,
				consider_marked_attendance_on_holidays=0,
			),
		):
			return seed_absence_from_attendance(slip)

	def test_it_puts_the_attendance_figure_on_the_slip(self):
		"""One full absence plus one half-absent day at the 0.5 fraction."""
		slip = _Slip()
		self.assertEqual(self._seed(slip), 1.5)
		self.assertEqual(flt(slip.absent_days), 1.5)

	def test_it_hands_over_the_full_bucket(self):
		slip = _Slip()
		self._seed(slip)
		self.assertEqual(flt(slip.custom_total_unpaid_days), 1.5)

	def test_it_marks_the_figure_as_coming_from_attendance(self):
		slip = _Slip()
		self._seed(slip)
		self.assertEqual(slip.flags.absent_days_from_attendance, 1)
		self.assertEqual(slip.flags.use_manual_absent_days, 1)


class TestSeedOnlyOnCreate(TestCase):
	"""Once a slip exists its figures are the payroll officer's to keep."""

	def _run(self, is_new, skip=0):
		slip = MagicMock()
		slip.is_new.return_value = is_new
		slip.flags.skip_attendance_seed = skip
		slip.employee, slip.start_date, slip.end_date = "EMP-001", "2026-08-14", "2026-09-13"
		with patch(
			"nepal_hrms.api.salary_slip_sync.seed_absence_from_attendance"
		) as seed:
			CustomSalarySlip._seed_absence_from_attendance(slip)
		return seed.called

	def test_a_new_slip_is_seeded(self):
		self.assertTrue(self._run(True))

	def test_an_existing_slip_is_left_alone(self):
		self.assertFalse(self._run(False))

	def test_the_flag_opts_a_slip_out(self):
		self.assertFalse(self._run(True, skip=1))

	def test_an_incomplete_slip_is_skipped(self):
		slip = MagicMock()
		slip.is_new.return_value = True
		slip.flags.skip_attendance_seed = 0
		slip.employee, slip.start_date, slip.end_date = None, None, None
		with patch("nepal_hrms.api.salary_slip_sync.seed_absence_from_attendance") as seed:
			CustomSalarySlip._seed_absence_from_attendance(slip)
		self.assertFalse(seed.called)

	def test_a_failure_never_blocks_payroll(self):
		slip = MagicMock()
		slip.is_new.return_value = True
		slip.flags.skip_attendance_seed = 0
		slip.employee, slip.start_date, slip.end_date = "EMP-001", "2026-08-14", "2026-09-13"
		with patch(
			"nepal_hrms.api.salary_slip_sync.seed_absence_from_attendance",
			side_effect=Exception("attendance table is on fire"),
		), patch("nepal_hrms.overrides.salary_slip.frappe.log_error") as log:
			CustomSalarySlip._seed_absence_from_attendance(slip)
		self.assertTrue(log.called)
