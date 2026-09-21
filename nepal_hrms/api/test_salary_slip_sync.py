from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import MagicMock, patch

from frappe.utils import flt

from nepal_hrms.api.salary_slip_sync import _snapshot, sync_slip
from nepal_hrms.overrides.salary_slip import apply_manual_absent_days


class _Slip:
	"""Minimal stand-in for a draft Salary Slip."""

	def __init__(self, absent_days=0.0, payment_days=24.0, net_pay=21311.33):
		self.name = "SS-TEST-0001"
		self.employee = "EMP-001"
		self.employee_name = "Test Employee"
		self.docstatus = 0
		self.start_date = "2026-07-17"
		self.end_date = "2026-08-13"
		self.absent_days = absent_days
		self.payment_days = payment_days
		self.leave_without_pay = 0.0
		self.net_pay = net_pay
		self.custom_absent_days_manual = 0
		self.custom_total_unpaid_days = 0.0
		self.custom_penalty_days = 0.0
		self.custom_unapproved_absent_days = 0.0
		self.custom_paid_leave_days = 0.0
		self.flags = MagicMock()
		self.flags.absent_days_from_attendance = 0
		self.meta = MagicMock()
		self.meta.has_field.return_value = True
		self.saved = False

	def get(self, field, default=None):
		return getattr(self, field, default)

	@contextmanager
	def _bs_extended_period(self):
		# Real slips may widen the period to the BS tail; the stub has one period.
		yield

	def get_holidays_for_employee(self, _s, _e):
		return []

	def calculate_lwp_ppl_and_absent_days_based_on_attendance(self, *_a, **_k):
		return 0, 0.0

	def get_half_absent_days(self, *_a, **_k):
		# One C&R penalty day: a Half Day whose other half is Absent.
		return 2.0

	def get_working_days_details(self, lwp=None):
		# Leave-based payroll never rewrites absent_days; the sync's value stands.
		self.net_pay = 20665.88

	def calculate_net_pay(self):
		pass

	def save(self):
		self.saved = True


class TestSalarySlipAttendanceSync(TestCase):
	def _sync(self, slip, save=False):
		with patch(
			"nepal_hrms.api.salary_slip_sync.frappe.get_single",
			return_value=MagicMock(
				daily_wages_fraction_for_half_day=0.5,
				consider_marked_attendance_on_holidays=0,
			),
		):
			return sync_slip(slip, save=save)

	def test_pulls_absent_days_from_attendance(self):
		"""Two half-absent days at the configured 0.5 fraction make one absent day."""
		slip = _Slip()
		row = self._sync(slip)
		self.assertEqual(flt(slip.absent_days), 1.0)
		self.assertEqual(row["attendance_absent_days"], 1.0)
		self.assertTrue(row["changed"])
		self.assertEqual(row["before"]["absent_days"], 0.0)
		self.assertEqual(row["after"]["absent_days"], 1.0)

	def test_hands_over_the_full_bucket_so_penalties_survive_a_resave(self):
		"""absent_days narrows to genuine absence; the total has its own field."""
		slip = _Slip()
		self._sync(slip)
		self.assertEqual(flt(slip.custom_total_unpaid_days), 1.0)

	def test_marks_the_slip_so_the_figure_survives_a_resave(self):
		slip = _Slip()
		self._sync(slip)
		self.assertEqual(slip.custom_absent_days_manual, 1)
		self.assertEqual(slip.flags.use_manual_absent_days, 1)
		self.assertEqual(slip.flags.absent_days_from_attendance, 1)

	def test_no_change_means_no_write(self):
		slip = _Slip(absent_days=1.0, net_pay=20665.88)
		row = self._sync(slip, save=True)
		self.assertFalse(row["changed"])
		self.assertFalse(slip.saved)

	def test_changed_slip_is_saved(self):
		slip = _Slip()
		row = self._sync(slip, save=True)
		self.assertTrue(row["changed"])
		self.assertTrue(slip.saved)

	def test_snapshot_covers_the_reported_figures(self):
		"""The preview reads penalty and absence separately, as the BS sheet does."""
		self.assertEqual(
			sorted(_snapshot(_Slip())),
			[
				"absent_days",
				"custom_paid_leave_days",
				"custom_penalty_days",
				"custom_unapproved_absent_days",
				"leave_without_pay",
				"net_pay",
				"payment_days",
			],
		)

	def test_attendance_sync_suppresses_the_manual_edit_notice(self):
		doc = type(
			"Doc",
			(),
			{
				"payment_days": 24.0,
				"absent_days": 0.0,
				"flags": type("F", (), {"absent_days_from_attendance": 1})(),
			},
		)()
		with patch("nepal_hrms.overrides.salary_slip.frappe.msgprint") as msgprint:
			apply_manual_absent_days(doc, manual_absent=1.0, calculated_absent=0.0)
		msgprint.assert_not_called()
		self.assertEqual(flt(doc.payment_days), 23.0)

	def test_manual_edit_still_warns(self):
		doc = type("Doc", (), {"payment_days": 24.0, "absent_days": 0.0})()
		with patch("nepal_hrms.overrides.salary_slip.frappe.msgprint") as msgprint:
			apply_manual_absent_days(doc, manual_absent=1.0, calculated_absent=0.0)
		msgprint.assert_called_once()
