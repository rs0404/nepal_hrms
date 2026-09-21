from unittest import TestCase

from frappe.utils import flt

from nepal_hrms.overrides.salary_slip import (
	_manual_absent_override_enabled,
	_total_unpaid_days,
	apply_manual_absent_days,
)


class TestManualAbsentDays(TestCase):
	def test_manual_override_flag_from_custom_field(self):
		doc = type(
			"Doc",
			(),
			{
				"flags": type("F", (), {})(),
				"meta": type("M", (), {"has_field": lambda _s, _f: True})(),
				"get": lambda _s, k, d=None: 1 if k == "custom_absent_days_manual" else d,
			},
		)()
		self.assertTrue(_manual_absent_override_enabled(doc))

	def test_increase_absent_reduces_payment_days(self):
		doc = type("Doc", (), {"payment_days": 28.0, "absent_days": 0.0})()
		apply_manual_absent_days(doc, manual_absent=1.0, calculated_absent=0.5)
		self.assertEqual(flt(doc.absent_days), 1.0)
		self.assertEqual(flt(doc.payment_days), 27.5)

	def test_decrease_absent_increases_payment_days(self):
		doc = type("Doc", (), {"payment_days": 27.0, "absent_days": 0.0})()
		apply_manual_absent_days(doc, manual_absent=0.0, calculated_absent=0.5)
		self.assertEqual(flt(doc.absent_days), 0.0)
		self.assertEqual(flt(doc.payment_days), 27.5)


class TestTotalUnpaidDays(TestCase):
	"""The full bucket is read from its own field, never from the narrowed one."""

	def _doc(self, has_field, stored, absent_days):
		return type(
			"Doc",
			(),
			{
				"meta": type("M", (), {"has_field": lambda _s, _f: has_field})(),
				"absent_days": absent_days,
				"get": lambda _s, _k, _d=None: stored,
			},
		)()

	def test_stored_total_wins_over_the_narrowed_absent_days(self):
		self.assertEqual(_total_unpaid_days(self._doc(True, 2.0, 1.0)), 2.0)

	def test_stored_zero_falls_back_to_absent_days(self):
		"""Slips saved before the field existed carry the bucket on absent_days."""
		self.assertEqual(_total_unpaid_days(self._doc(True, 0.0, 1.5)), 1.5)

	def test_missing_field_falls_back_to_absent_days(self):
		self.assertEqual(_total_unpaid_days(self._doc(False, None, 3.0)), 3.0)
