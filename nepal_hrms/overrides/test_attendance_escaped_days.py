"""Escape Attendance-Based Deduction: pay follows leave alone.

HRMS takes LWP *and* the attendance bucket out of payment_days. The escape has
to give back exactly the attendance share and no more, or an escaped employee
either keeps paying for absence or stops paying for leave.
"""

from unittest import TestCase
from unittest.mock import patch

import frappe
from frappe.utils import flt

from nepal_hrms.overrides.salary_slip import CustomSalarySlip


def _slip(payment_days, absent_days, lwp=0.0, total_working_days=30.0, has_field=True):
	return type(
		"Doc",
		(),
		{
			"employee": "HR-EMP-0001",
			"start_date": "2026-08-17",
			"end_date": "2026-09-16",
			"payment_days": payment_days,
			"absent_days": absent_days,
			"leave_without_pay": lwp,
			"total_working_days": total_working_days,
			"custom_total_unpaid_days": absent_days,
			"meta": type("M", (), {"has_field": lambda _s, _f: has_field})(),
		},
	)()


def _escapes(**flags):
	base = {
		"escape_sandwich": 0,
		"escape_late_early": 0,
		"escape_continuous_lwp_gross": 0,
		"escape_absent_gross": 0,
		"escape_applications": 0,
		"escape_attendance_deduction": 0,
	}
	base.update(flags)
	return frappe._dict(base)


class TestRestoreAttendanceEscapedDays(TestCase):
	def _run(self, doc, escapes):
		with patch(
			"nepal_hrms.custom_code.policy_escape.get_policy_escapes_for_period",
			return_value=escapes,
		):
			CustomSalarySlip._restore_attendance_escaped_days(doc)

	def test_absent_days_are_given_back_to_payment_days(self):
		doc = _slip(payment_days=27.0, absent_days=3.0)
		self._run(doc, _escapes(escape_attendance_deduction=1))
		self.assertEqual(flt(doc.payment_days), 30.0)
		self.assertEqual(flt(doc.absent_days), 0.0)
		self.assertEqual(flt(doc.custom_total_unpaid_days), 0.0)

	def test_lwp_keeps_its_reduction(self):
		"""25 = 30 working - 2 LWP - 3 absent. Only the 3 come back."""
		doc = _slip(payment_days=25.0, absent_days=3.0, lwp=2.0)
		self._run(doc, _escapes(escape_attendance_deduction=1))
		self.assertEqual(flt(doc.payment_days), 28.0)
		self.assertEqual(flt(doc.absent_days), 0.0)

	def test_half_days_come_back_too(self):
		doc = _slip(payment_days=29.5, absent_days=0.5)
		self._run(doc, _escapes(escape_attendance_deduction=1))
		self.assertEqual(flt(doc.payment_days), 30.0)

	def test_restore_never_exceeds_working_days_less_lwp(self):
		"""A disagreement between the two figures must not mint paid days."""
		doc = _slip(payment_days=28.0, absent_days=9.0, lwp=2.0)
		self._run(doc, _escapes(escape_attendance_deduction=1))
		self.assertEqual(flt(doc.payment_days), 28.0)

	def test_other_escapes_leave_attendance_alone(self):
		doc = _slip(payment_days=27.0, absent_days=3.0)
		self._run(doc, _escapes(escape_absent_gross=1, escape_sandwich=1))
		self.assertEqual(flt(doc.payment_days), 27.0)
		self.assertEqual(flt(doc.absent_days), 3.0)

	def test_no_escape_is_a_no_op(self):
		doc = _slip(payment_days=27.0, absent_days=3.0)
		self._run(doc, _escapes())
		self.assertEqual(flt(doc.payment_days), 27.0)
		self.assertEqual(flt(doc.absent_days), 3.0)

	def test_clean_attendance_month_still_clears_nothing_it_should_not(self):
		doc = _slip(payment_days=28.0, absent_days=0.0, lwp=2.0)
		self._run(doc, _escapes(escape_attendance_deduction=1))
		self.assertEqual(flt(doc.payment_days), 28.0)

	def test_employee_missing_is_a_no_op(self):
		doc = _slip(payment_days=27.0, absent_days=3.0)
		doc.employee = None
		self._run(doc, _escapes(escape_attendance_deduction=1))
		self.assertEqual(flt(doc.payment_days), 27.0)
