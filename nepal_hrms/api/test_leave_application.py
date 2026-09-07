# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

from nepal_hrms.api.leave_application import (
	build_frequent_leave_type_list,
	group_contiguous_dates,
	has_available_leave,
	normalize_leave_ranges,
	should_block_combined_leave,
	skip_leave_balance_check,
)
from frappe.tests.utils import FrappeTestCase


class TestFrequentLeaveTypes(FrappeTestCase):
	def test_build_keeps_configured_order_and_remaining(self):
		rows = build_frequent_leave_type_list(
			["Casual Leave", "Missing Type", "Annual Leave", "Leave Without Pay"],
			{
				"Casual Leave": {"remaining_leaves": 5},
				"Annual Leave": {"remaining_leaves": 12.5},
			},
			["Leave Without Pay"],
		)
		self.assertEqual(
			[row["leave_type"] for row in rows],
			["Casual Leave", "Annual Leave", "Leave Without Pay"],
		)
		self.assertEqual(rows[0]["remaining"], 5)
		self.assertEqual(rows[0]["pending"], 0)
		self.assertEqual(rows[0]["is_lwp"], 0)
		self.assertEqual(rows[1]["remaining"], 12.5)
		self.assertIsNone(rows[2]["remaining"])
		self.assertEqual(rows[2]["is_lwp"], 1)

	def test_build_deducts_pending_leaves(self):
		rows = build_frequent_leave_type_list(
			["Casual Leave"],
			{"Casual Leave": {"remaining_leaves": 5, "leaves_pending_approval": 2}},
			[],
		)
		self.assertEqual(rows[0]["remaining"], 3)
		self.assertEqual(rows[0]["pending"], 2)

	def test_build_pending_does_not_go_negative(self):
		rows = build_frequent_leave_type_list(
			["Casual Leave"],
			{"Casual Leave": {"remaining_leaves": 1, "leaves_pending_approval": 4}},
			[],
		)
		self.assertEqual(rows[0]["remaining"], 0)
		self.assertEqual(rows[0]["pending"], 4)

	def test_build_empty_when_nothing_configured(self):
		self.assertEqual(build_frequent_leave_type_list([], {"Casual Leave": {"remaining_leaves": 1}}, []), [])

	def test_has_available_leave(self):
		self.assertTrue(has_available_leave(3))
		self.assertTrue(has_available_leave(0.5))
		self.assertFalse(has_available_leave(0))
		self.assertFalse(has_available_leave(None))
		self.assertTrue(has_available_leave(None, is_lwp=True))
		self.assertTrue(has_available_leave(0, is_lwp=True))


class TestLeaveRanges(FrappeTestCase):
	def test_contiguous_weekdays_merge(self):
		self.assertEqual(
			group_contiguous_dates(["2026-09-07", "2026-09-08", "2026-09-09"]),
			[{"from_date": "2026-09-07", "to_date": "2026-09-09"}],
		)

	def test_gap_splits_into_separate_ranges(self):
		self.assertEqual(
			group_contiguous_dates(["2026-09-07", "2026-09-09"]),
			[
				{"from_date": "2026-09-07", "to_date": "2026-09-07"},
				{"from_date": "2026-09-09", "to_date": "2026-09-09"},
			],
		)

	def test_friday_and_monday_stay_separate(self):
		self.assertEqual(
			group_contiguous_dates(["2026-09-04", "2026-09-07"]),
			[
				{"from_date": "2026-09-04", "to_date": "2026-09-04"},
				{"from_date": "2026-09-07", "to_date": "2026-09-07"},
			],
		)

	def test_normalize_merges_adjacent_ranges(self):
		self.assertEqual(
			normalize_leave_ranges(
				[
					{"from_date": "2026-09-07", "to_date": "2026-09-08"},
					{"from_date": "2026-09-09", "to_date": "2026-09-09"},
				]
			),
			[{"from_date": "2026-09-07", "to_date": "2026-09-09"}],
		)

	def test_normalize_keeps_gapped_ranges(self):
		self.assertEqual(
			normalize_leave_ranges(
				[
					{"from_date": "2026-09-07", "to_date": "2026-09-07"},
					{"from_date": "2026-09-09", "to_date": "2026-09-10"},
				]
			),
			[
				{"from_date": "2026-09-07", "to_date": "2026-09-07"},
				{"from_date": "2026-09-09", "to_date": "2026-09-10"},
			],
		)


class TestCombinedLeaveBalance(FrappeTestCase):
	def test_blocks_when_combined_days_exceed_remaining(self):
		self.assertTrue(should_block_combined_leave(5, 3))
		self.assertTrue(should_block_combined_leave(1, 0))
		self.assertTrue(should_block_combined_leave(3.5, 3))

	def test_allows_when_combined_days_fit(self):
		self.assertFalse(should_block_combined_leave(3, 3))
		self.assertFalse(should_block_combined_leave(1, 3))
		self.assertFalse(should_block_combined_leave(0.5, 1))

	def test_skips_lwp_and_allow_negative(self):
		self.assertFalse(should_block_combined_leave(5, 3, is_lwp=True))
		self.assertFalse(should_block_combined_leave(5, 3, allow_negative=True))

	def test_blocks_when_pending_drafts_consume_remaining(self):
		# 3 remaining, 7 already Open, new 1-day application
		available = max(0, 3 - 7)
		self.assertTrue(should_block_combined_leave(1, available))

	def test_allows_when_pending_drafts_still_leave_room(self):
		# 3 remaining, 2 already Open, new 1-day application
		available = max(0, 3 - 2)
		self.assertFalse(should_block_combined_leave(1, available))

	def test_skips_leave_without_pay_type(self):
		import frappe

		if not frappe.db.exists("Leave Type", "Leave Without Pay"):
			return
		self.assertTrue(skip_leave_balance_check("Leave Without Pay"))
		if frappe.db.exists("Leave Type", "Annual/Home Leave"):
			self.assertFalse(skip_leave_balance_check("Annual/Home Leave"))
