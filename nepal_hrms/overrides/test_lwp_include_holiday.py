"""A holiday inside an LWP stretch counts when the Leave Type says it should."""

from datetime import date
from unittest import TestCase
from unittest.mock import patch

from nepal_hrms.overrides.salary_slip import CustomSalarySlip


class _Slip(CustomSalarySlip):
	"""Real subclass -- the method calls super(). Class attributes shadow
	actual_end_date, which is a read-only property on SalarySlip."""

	start_date = date(2026, 7, 17)
	end_date = date(2026, 8, 13)
	actual_end_date = date(2026, 8, 13)

	def __init__(self):
		pass


class TestLwpIncludesHolidays(TestCase):
	"""HRMS strips holidays from the day list before its include_holiday test."""

	WORKING = [date(2026, 7, 24), date(2026, 7, 26)]   # 07-25 stripped as a Saturday
	HOLIDAYS = [date(2026, 7, 25), date(2026, 8, 1)]

	def _days_handed_to_hrms(self, holidays=None, working=None):
		captured = {}

		def _super(self, holidays, working_days_list, fraction):
			captured["days"] = list(working_days_list)
			return 0

		with patch.object(
			CustomSalarySlip.__bases__[0],
			"calculate_lwp_or_ppl_based_on_leave_application",
			_super,
		):
			CustomSalarySlip.calculate_lwp_or_ppl_based_on_leave_application(
				_Slip(),
				self.HOLIDAYS if holidays is None else holidays,
				self.WORKING if working is None else working,
				0.5,
			)
		return captured["days"]

	def test_holidays_in_the_period_are_handed_back(self):
		self.assertEqual(
			self._days_handed_to_hrms(),
			[date(2026, 7, 24), date(2026, 7, 25), date(2026, 7, 26), date(2026, 8, 1)],
		)

	def test_the_list_stays_in_date_order(self):
		days = self._days_handed_to_hrms()
		self.assertEqual(days, sorted(days))

	def test_a_holiday_outside_the_period_is_not_added(self):
		days = self._days_handed_to_hrms(holidays=[date(2026, 9, 5)])
		self.assertEqual(days, self.WORKING)

	def test_a_holiday_already_present_is_not_duplicated(self):
		days = self._days_handed_to_hrms(working=[date(2026, 7, 25)])
		self.assertEqual(days, [date(2026, 7, 25), date(2026, 8, 1)])

	def test_no_holidays_leaves_the_list_alone(self):
		self.assertEqual(self._days_handed_to_hrms(holidays=[]), self.WORKING)
