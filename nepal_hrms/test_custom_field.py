from unittest import TestCase

from nepal_hrms.custom_field import _move_fields_after


class TestSalarySlipFieldOrder(TestCase):
	def test_moves_lwp_and_overtime_under_absent_days(self):
		order = [
			"payment_days_tab",
			"total_working_days",
			"unmarked_days",
			"leave_without_pay",
			"custom_overtime_hours",
			"column_break_geio",
			"absent_days",
			"payment_days",
		]
		moved = _move_fields_after(
			order,
			("leave_without_pay", "custom_overtime_hours"),
			"absent_days",
		)
		self.assertEqual(
			moved,
			[
				"payment_days_tab",
				"total_working_days",
				"unmarked_days",
				"column_break_geio",
				"absent_days",
				"leave_without_pay",
				"custom_overtime_hours",
				"payment_days",
			],
		)

	def test_leaves_order_when_absent_days_missing(self):
		order = ["leave_without_pay", "custom_overtime_hours", "payment_days"]
		self.assertEqual(
			_move_fields_after(order, ("leave_without_pay", "custom_overtime_hours"), "absent_days"),
			order,
		)
