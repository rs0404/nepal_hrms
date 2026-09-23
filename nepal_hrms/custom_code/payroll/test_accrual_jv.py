"""When the Payroll Entry should offer to raise the accrual JV again.

The risk in re-raising is double-posting, so the rule has to be exact: offer it
only while no live accrual JV holds the run, and only while there are submitted
slips no journal entry has claimed.
"""

from unittest import TestCase

from nepal_hrms.custom_code.payroll.accrual_jv import partition_advance_entries, summarize

DRAFT, SUBMITTED, CANCELLED = 0, 1, 2


def je(name, docstatus):
	return {"name": name, "docstatus": docstatus}


class TestSummarize(TestCase):
	def test_never_accrued_offers_the_button(self):
		status = summarize([], SUBMITTED, pending_slips=31)
		self.assertTrue(status["can_create"])
		self.assertEqual(status["posted"], [])
		self.assertEqual(status["cancelled"], [])

	def test_cancelled_accrual_offers_the_button(self):
		status = summarize([je("ACC-JV-1", CANCELLED)], SUBMITTED, pending_slips=31)
		self.assertTrue(status["can_create"])
		self.assertEqual(status["cancelled"], ["ACC-JV-1"])

	def test_live_accrual_withholds_the_button(self):
		status = summarize([je("ACC-JV-1", SUBMITTED)], SUBMITTED, pending_slips=0)
		self.assertFalse(status["can_create"])
		self.assertEqual(status["posted"], ["ACC-JV-1"])

	def test_a_live_accrual_wins_over_a_cancelled_one(self):
		# Cancelled once, re-raised, and the replacement is live: nothing to do.
		entries = [je("ACC-JV-2", SUBMITTED), je("ACC-JV-1", CANCELLED)]
		self.assertFalse(summarize(entries, SUBMITTED, pending_slips=0)["can_create"])

	def test_no_unaccrued_slips_withholds_the_button(self):
		# Slips still linked to some journal entry, so there is nothing to post.
		status = summarize([je("ACC-JV-1", CANCELLED)], SUBMITTED, pending_slips=0)
		self.assertFalse(status["can_create"])

	def test_draft_payroll_entry_withholds_the_button(self):
		self.assertFalse(summarize([], DRAFT, pending_slips=31)["can_create"])

	def test_cancelled_payroll_entry_withholds_the_button(self):
		self.assertFalse(summarize([], CANCELLED, pending_slips=31)["can_create"])

	def test_pending_count_is_reported_for_the_confirmation(self):
		self.assertEqual(summarize([], SUBMITTED, pending_slips=31)["pending_slips"], 31)


class TestPartitionAdvanceEntries(TestCase):
	"""Rows raised from an Employee Advance keep stock's handling; rows that only
	need a party on a Receivable account are emitted separately, because stock
	hard-codes reference_type="Employee Advance" on everything it posts."""

	LINKED = {"employee": "EMP-1", "amount": 5000, "reference_name": "HR-EAD-2026-00001"}
	UNLINKED = {"employee": "EMP-2", "amount": 5000, "reference_name": None}

	def test_splits_by_whether_an_advance_is_referenced(self):
		linked, unlinked = partition_advance_entries([self.LINKED, self.UNLINKED])
		self.assertEqual(linked, [self.LINKED])
		self.assertEqual(unlinked, [self.UNLINKED])

	def test_a_missing_reference_key_counts_as_unlinked(self):
		entry = {"employee": "EMP-3", "amount": 100}
		self.assertEqual(partition_advance_entries([entry]), ([], [entry]))

	def test_nothing_is_dropped(self):
		entries = [self.LINKED, self.UNLINKED, {"employee": "EMP-4"}]
		linked, unlinked = partition_advance_entries(entries)
		self.assertEqual(len(linked) + len(unlinked), len(entries))

	def test_empty(self):
		self.assertEqual(partition_advance_entries([]), ([], []))
