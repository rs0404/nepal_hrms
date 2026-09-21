"""The continuous-LWP streak is what the employee took, not how it was filed."""

from datetime import date
from unittest import TestCase

from nepal_hrms.overrides.salary_slip import (
	longest_lwp_streak,
	lwp_days_in_qualifying_streaks,
	lwp_should_use_gross,
)


class TestLongestLwpStreak(TestCase):
	def test_days_filed_as_separate_applications_still_form_one_run(self):
		"""Saurav: 07-23, 07-24, 07-25..27, 07-28 -- four applications, six days."""
		days = [date(2026, 7, d) for d in (17, 23, 24, 25, 26, 27, 28)]
		self.assertEqual(longest_lwp_streak(days), 6)

	def test_a_gap_breaks_the_run(self):
		days = [date(2026, 7, d) for d in (1, 2, 4, 5, 6)]
		self.assertEqual(longest_lwp_streak(days), 3)

	def test_a_single_day_is_a_run_of_one(self):
		self.assertEqual(longest_lwp_streak([date(2026, 7, 17)]), 1)

	def test_no_lwp_is_zero(self):
		self.assertEqual(longest_lwp_streak([]), 0)
		self.assertEqual(longest_lwp_streak(None), 0)

	def test_duplicates_and_disorder_do_not_inflate_the_run(self):
		days = [date(2026, 7, 24), date(2026, 7, 23), date(2026, 7, 24)]
		self.assertEqual(longest_lwp_streak(days), 2)


class TestGrossRuleUsesTheStreak(TestCase):
	def _gross(self, streak, threshold=5):
		return lwp_should_use_gross(
			enable_continuous=1,
			max_continuous_lwp=streak,
			continuous_threshold=threshold,
			enable_period_leave=0,
			period_leave_days=0,
			period_threshold=5,
			escape_lwp_gross=0,
		)

	def test_a_six_day_run_meets_a_five_day_threshold(self):
		use_gross, is_continuous, _ = self._gross(6)
		self.assertTrue(use_gross)
		self.assertTrue(is_continuous)

	def test_the_threshold_itself_qualifies(self):
		self.assertTrue(self._gross(5)[0])

	def test_a_shorter_run_does_not(self):
		"""The longest single application was 3 days -- what used to be measured."""
		self.assertFalse(self._gross(3)[0])

	def test_a_policy_escape_overrides_the_rule(self):
		use_gross, is_continuous, is_period = lwp_should_use_gross(
			enable_continuous=1,
			max_continuous_lwp=10,
			continuous_threshold=5,
			enable_period_leave=1,
			period_leave_days=20,
			period_threshold=5,
			escape_lwp_gross=1,
		)
		self.assertFalse(use_gross)
		self.assertEqual((is_continuous, is_period), (0, 0))


class TestQualifyingStreakDays(TestCase):
	"""Only the qualifying stretch earns the gross rate."""

	SAURAV = [date(2026, 7, d) for d in (16, 17, 23, 24, 25, 26, 27, 28)]
	PERIOD = (date(2026, 7, 13), date(2026, 8, 13))

	_DEFAULT = object()

	def _days(self, dates=_DEFAULT, threshold=5, period=None):
		start, end = period or self.PERIOD
		return lwp_days_in_qualifying_streaks(
			self.SAURAV if dates is self._DEFAULT else dates, threshold, start, end
		)

	def test_only_the_six_day_run_qualifies(self):
		"""07-23..07-28 qualifies; 07-16 and 07-17 are an ordinary two-day pair."""
		self.assertEqual(self._days(), 6)

	def test_nothing_qualifies_below_the_threshold(self):
		self.assertEqual(self._days(threshold=7), 0)

	def test_two_qualifying_runs_both_count(self):
		days = [date(2026, 7, d) for d in (14, 15, 16, 17, 18, 23, 24, 25, 26, 27)]
		self.assertEqual(self._days(days), 10)

	def test_days_outside_the_period_are_not_charged(self):
		"""A run straddling the period boundary only bills the days inside it."""
		self.assertEqual(
			self._days(period=(date(2026, 7, 26), date(2026, 8, 13))), 3
		)

	def test_the_run_still_qualifies_on_its_full_length(self):
		"""Clipping decides what is billed, never whether the rule fires."""
		self.assertEqual(longest_lwp_streak(self.SAURAV), 6)

	def test_empty_input_is_zero(self):
		self.assertEqual(self._days([]), 0)
		self.assertEqual(self._days(None), 0)
