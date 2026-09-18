from unittest import TestCase

from frappe.utils import flt

from nepal_hrms.overrides.salary_slip import (
	_manual_absent_override_enabled,
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
