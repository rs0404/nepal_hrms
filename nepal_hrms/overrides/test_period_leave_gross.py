from unittest import TestCase

from nepal_hrms.overrides.salary_slip import (
	lwp_should_use_gross,
	period_leave_days_for_gross_rule,
)


class TestPeriodLeaveGrossLwp(TestCase):
	def test_counts_lwp_and_absent_days(self):
		self.assertEqual(period_leave_days_for_gross_rule(5.0, 2.5), 7.5)
		self.assertEqual(period_leave_days_for_gross_rule(5.0, 0), 5.0)
		self.assertEqual(period_leave_days_for_gross_rule(0, 0), 0.0)

	def test_disabled_rule_does_not_use_gross(self):
		use_gross, continuous, period = lwp_should_use_gross(
			enable_continuous=0,
			max_continuous_lwp=10,
			continuous_threshold=5,
			enable_period_leave=0,
			period_leave_days=10,
			period_threshold=5,
			escape_lwp_gross=0,
		)
		self.assertFalse(use_gross)
		self.assertEqual(continuous, 0)
		self.assertEqual(period, 0)

	def test_more_than_threshold_uses_gross(self):
		use_gross, continuous, period = lwp_should_use_gross(
			enable_continuous=0,
			max_continuous_lwp=1,
			continuous_threshold=5,
			enable_period_leave=1,
			period_leave_days=6,
			period_threshold=5,
			escape_lwp_gross=0,
		)
		self.assertTrue(use_gross)
		self.assertEqual(continuous, 0)
		self.assertEqual(period, 1)

	def test_equal_to_threshold_does_not_use_gross(self):
		use_gross, continuous, period = lwp_should_use_gross(
			enable_continuous=0,
			max_continuous_lwp=0,
			continuous_threshold=5,
			enable_period_leave=1,
			period_leave_days=5,
			period_threshold=5,
			escape_lwp_gross=0,
		)
		self.assertFalse(use_gross)
		self.assertEqual(period, 0)

	def test_escape_blocks_period_and_continuous(self):
		use_gross, continuous, period = lwp_should_use_gross(
			enable_continuous=1,
			max_continuous_lwp=10,
			continuous_threshold=5,
			enable_period_leave=1,
			period_leave_days=10,
			period_threshold=5,
			escape_lwp_gross=1,
		)
		self.assertFalse(use_gross)
		self.assertEqual(continuous, 0)
		self.assertEqual(period, 0)

	def test_continuous_rule_still_applies(self):
		use_gross, continuous, period = lwp_should_use_gross(
			enable_continuous=1,
			max_continuous_lwp=5,
			continuous_threshold=5,
			enable_period_leave=0,
			period_leave_days=1,
			period_threshold=5,
			escape_lwp_gross=0,
		)
		self.assertTrue(use_gross)
		self.assertEqual(continuous, 1)
		self.assertEqual(period, 0)
