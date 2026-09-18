from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.overrides.salary_slip import get_pool_penalty_days


class _Meta:
	def __init__(self, has_penalty_field=True):
		self.has_penalty_field = has_penalty_field

	def has_field(self, fieldname):
		return self.has_penalty_field


class TestPoolPenaltyDays(TestCase):
	"""½P / 1P are Attendance rows, so HRMS counts them inside absent_days.

	Payroll has to read them back off Attendance to charge them on their own base.
	"""

	def call(self, rows, has_field=True, half_day_fraction=0.5):
		with patch.object(frappe, "get_meta", return_value=_Meta(has_field)), patch.object(
			frappe.db, "get_single_value", return_value=half_day_fraction
		), patch.object(
			frappe, "get_all", return_value=[frappe._dict(r) for r in rows]
		) as get_all:
			result = get_pool_penalty_days("EMP-1", "2025-09-01", "2025-09-30")
		return result, get_all

	def test_half_counts_half_a_day_and_full_counts_one(self):
		(days, dates), _ = self.call(
			[
				{"attendance_date": "2025-09-03", "custom_cnr_pool_penalty": "half"},
				{"attendance_date": "2025-09-10", "custom_cnr_pool_penalty": "full"},
				{"attendance_date": "2025-09-17", "custom_cnr_pool_penalty": "half"},
			]
		)
		self.assertEqual(days, 2.0)
		self.assertEqual([d["units"] for d in dates], [0.5, 1.0, 0.5])
		self.assertEqual([d["kind"] for d in dates], ["half", "full", "half"])
		self.assertEqual(dates[0]["date"], "2025-09-03")

	def test_no_penalty_rows_is_zero_with_no_dates(self):
		(days, dates), _ = self.call([])
		self.assertEqual(days, 0.0)
		self.assertEqual(dates, [])

	def test_half_penalty_follows_the_payroll_half_day_fraction(self):
		# HRMS added 0.75 to absent_days for this row, so the split has to remove
		# 0.75 -- not a flat 0.5 -- or the residue is charged as a real absence.
		(days, dates), _ = self.call(
			[{"attendance_date": "2025-09-03", "custom_cnr_pool_penalty": "half"}],
			half_day_fraction=0.75,
		)
		self.assertEqual(days, 0.75)
		self.assertEqual(dates[0]["units"], 0.75)

	def test_missing_custom_field_does_not_query(self):
		(days, dates), get_all = self.call([], has_field=False)
		self.assertEqual((days, dates), (0.0, []))
		get_all.assert_not_called()
