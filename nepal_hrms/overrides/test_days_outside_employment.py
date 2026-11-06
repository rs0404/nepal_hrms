from datetime import date
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from frappe.utils import flt

from nepal_hrms.custom_code.payroll.employment_window import (
	dates_outside_employment,
	payroll_window as window,
)
from nepal_hrms.overrides.salary_slip import (
	CustomSalarySlip,
	days_outside_employment,
	payroll_window,
	slip_daily_divisor,
)

# Period 14 Sep - 14 Oct 2026 with its Sat/Sun weekly offs.
START, END = date(2026, 9, 14), date(2026, 10, 14)
WEEKENDS = [
	date(2026, 9, 19), date(2026, 9, 20), date(2026, 9, 26), date(2026, 9, 27),
	date(2026, 10, 3), date(2026, 10, 4), date(2026, 10, 10), date(2026, 10, 11),
]


class FakeSlip(SimpleNamespace):
	def __init__(self, has_field=True, **kwargs):
		defaults = dict(
			start_date=START,
			end_date=END,
			joining_date=date(2020, 1, 1),
			relieving_date=date(2026, 10, 9),
			absent_days=0.0,
			payment_days=0.0,
			custom_days_outside_employment=0.0,
		)
		defaults.update(kwargs)
		super().__init__(**defaults)
		self.meta = SimpleNamespace(has_field=lambda _f: has_field)

	def get(self, key, default=None):
		return getattr(self, key, default)

	def get_holidays_for_employee(self, start, end):
		start, end = date.fromisoformat(str(start)), date.fromisoformat(str(end))
		return [d for d in WEEKENDS if start <= d <= end]


def settings(payroll_based_on="Leave", include_holidays=0):
	values = {
		"payroll_based_on": payroll_based_on,
		"include_holidays_in_total_working_days": include_holidays,
	}
	return patch(
		"nepal_hrms.overrides.salary_slip.frappe.get_cached_value",
		side_effect=lambda _dt, _dn, field: values[field],
	)


class TestDatesOutsideEmployment(TestCase):
	def test_after_relieving(self):
		self.assertEqual(
			dates_outside_employment(START, END, relieving_date=date(2026, 10, 12)),
			[date(2026, 10, 13), date(2026, 10, 14)],
		)

	def test_before_joining(self):
		self.assertEqual(
			dates_outside_employment(START, END, joining_date=date(2026, 9, 16)),
			[date(2026, 9, 14), date(2026, 9, 15)],
		)

	def test_joined_and_relieved_in_the_same_period(self):
		dates = dates_outside_employment(
			START, END, joining_date=date(2026, 9, 15), relieving_date=date(2026, 10, 13)
		)
		self.assertEqual(dates, [date(2026, 9, 14), date(2026, 10, 14)])

	def test_dates_on_the_period_edges_leave_nothing(self):
		# Joining on the first day or relieving on the last is a full period, and
		# dates outside the period are not this function's business.
		for joining, relieving in (
			(START, END),
			(date(2020, 1, 1), date(2027, 1, 1)),
			(date(2026, 11, 1), None),
			(None, date(2026, 9, 1)),
		):
			self.assertEqual(dates_outside_employment(START, END, joining, relieving), [])


class TestDaysOutsideEmployment(TestCase):
	def test_counts_working_days_after_relieving(self):
		# 10-14 Oct is five days; the weekend leaves 12, 13 and 14 Oct.
		with settings():
			self.assertEqual(days_outside_employment(FakeSlip()), 3.0)

	def test_counts_working_days_before_joining(self):
		# 14 Sep - 22 Sep before a 23 Sep joining: nine days less the 19-20 weekend.
		slip = FakeSlip(joining_date=date(2026, 9, 23), relieving_date=None)
		with settings():
			self.assertEqual(days_outside_employment(slip), 7.0)

	def test_counts_calendar_days_when_holidays_are_working_days(self):
		with settings(include_holidays=1):
			self.assertEqual(days_outside_employment(FakeSlip()), 5.0)

	def test_employed_for_the_whole_period(self):
		with settings():
			self.assertEqual(days_outside_employment(FakeSlip(relieving_date=None)), 0.0)


class TestCountDaysOutsideEmploymentAsAbsent(TestCase):
	count = staticmethod(CustomSalarySlip._count_days_outside_employment_as_absent)

	def test_leave_mode_charges_as_absence_not_as_lost_payment_days(self):
		slip = FakeSlip(absent_days=1.0, payment_days=19.0)
		with settings("Leave"):
			change = self.count(slip)
		self.assertEqual(change, 3.0)
		self.assertEqual(flt(slip.absent_days), 4.0)
		self.assertEqual(flt(slip.payment_days), 22.0)
		self.assertEqual(slip.custom_days_outside_employment, 3.0)

	def test_leave_mode_resave_does_not_count_twice(self):
		# absent_days carries over between saves in Leave mode, already holding them.
		slip = FakeSlip(absent_days=4.0, payment_days=19.0, custom_days_outside_employment=3.0)
		with settings("Leave"):
			change = self.count(slip)
		self.assertEqual(change, 0.0)
		self.assertEqual(flt(slip.absent_days), 4.0)

	def test_leave_mode_relieving_date_moved_later(self):
		slip = FakeSlip(
			absent_days=4.0,
			custom_days_outside_employment=3.0,
			relieving_date=date(2026, 10, 12),
		)
		with settings("Leave"):
			change = self.count(slip)
		self.assertEqual(change, -1.0)
		self.assertEqual(flt(slip.absent_days), 3.0)

	def test_joining_and_relieving_add_up(self):
		slip = FakeSlip(joining_date=date(2026, 9, 16), payment_days=17.0)
		with settings("Leave"):
			change = self.count(slip)
		self.assertEqual(change, 5.0)
		self.assertEqual(flt(slip.payment_days), 22.0)

	def test_attendance_mode_adds_to_fresh_count_only(self):
		# HRMS recounts absent_days each save and already dropped the payment days.
		slip = FakeSlip(absent_days=2.0, payment_days=17.0, custom_days_outside_employment=3.0)
		with settings("Attendance"):
			change = self.count(slip)
		self.assertEqual(change, 0.0)
		self.assertEqual(flt(slip.absent_days), 5.0)
		self.assertEqual(flt(slip.payment_days), 17.0)

	def test_without_the_field_the_slip_is_left_alone(self):
		slip = FakeSlip(has_field=False, absent_days=1.0, payment_days=19.0)
		with settings("Leave"):
			change = self.count(slip)
		self.assertEqual(change, 0.0)
		self.assertEqual((flt(slip.absent_days), flt(slip.payment_days)), (1.0, 19.0))


JOINED = date(2026, 9, 23)
RELIEVED = date(2026, 10, 9)


def period(start=START, end=END):
	return patch(
		"nepal_hrms.custom_code.payroll.period.period_containing",
		return_value=(start, end, (end - start).days + 1),
	)


class TestPayrollWindow(TestCase):
	def test_slip_dated_from_the_joining_day_goes_back_to_the_period(self):
		self.assertEqual(window(JOINED, END, START, END, joining_date=JOINED), (START, END))

	def test_slip_dated_to_the_relieving_day_runs_to_the_period_end(self):
		self.assertEqual(
			window(START, RELIEVED, START, END, relieving_date=RELIEVED), (START, END)
		)

	def test_joined_and_relieved_inside_a_stub(self):
		self.assertEqual(
			window(JOINED, RELIEVED, START, END, JOINED, RELIEVED), (START, END)
		)

	def test_a_full_period_slip_is_left_alone(self):
		self.assertEqual(window(START, END, START, END, JOINED, RELIEVED), (START, END))

	def test_a_late_start_employment_does_not_explain_keeps_its_dates(self):
		# Joined long before: the slip was cut short for some other reason.
		self.assertEqual(
			window(JOINED, END, START, END, joining_date=date(2020, 1, 1)), (JOINED, END)
		)

	def test_a_slip_outside_one_period_keeps_its_dates(self):
		start = date(2026, 9, 1)
		self.assertEqual(window(start, END, START, END, joining_date=start), (start, END))

	def test_no_period_known(self):
		self.assertEqual(window(JOINED, END, None, None, joining_date=JOINED), (JOINED, END))


class TestPayrollWindowOfSlip(TestCase):
	def test_joiner_stub_resolves_to_the_period(self):
		slip = FakeSlip(start_date=JOINED, joining_date=JOINED, relieving_date=None)
		with period():
			self.assertEqual(payroll_window(slip), (START, END))

	def test_regular_employee_never_looks_up_the_period(self):
		slip = FakeSlip(relieving_date=None)
		with patch("nepal_hrms.custom_code.payroll.period.period_containing") as lookup:
			self.assertEqual(payroll_window(slip), (START, END))
		lookup.assert_not_called()


class DivisorSlip(FakeSlip):
	def __init__(self, **kwargs):
		defaults = dict(
			relieving_date=None,
			company="Test Co",
			total_working_days=22.0,
			custom_daily_divisor_used=0.0,
			custom_daily_divisor_basis=None,
		)
		defaults.update(kwargs)
		super().__init__(**defaults)


def divisor_by_span():
	"""resolve_daily_divisor stand-in returning the span it was handed, in days."""
	return patch(
		"nepal_hrms.custom_code.payroll.period.resolve_daily_divisor",
		side_effect=lambda start, end, **_k: (float((end - start).days + 1), "days in payroll period"),
	)


class TestSlipDailyDivisor(TestCase):
	def test_joiner_stub_gets_the_regular_divisor(self):
		regular = DivisorSlip()
		joiner = DivisorSlip(start_date=JOINED, joining_date=JOINED)
		with period(), divisor_by_span():
			self.assertEqual(slip_daily_divisor(regular)[0], 31.0)
			self.assertEqual(slip_daily_divisor(joiner)[0], 31.0)
		self.assertEqual(joiner.custom_daily_divisor_used, 31.0)

	def test_leaver_stub_gets_the_regular_divisor(self):
		leaver = DivisorSlip(end_date=RELIEVED, relieving_date=RELIEVED)
		with period(), divisor_by_span():
			self.assertEqual(slip_daily_divisor(leaver)[0], 31.0)

	def test_a_snapshot_is_kept(self):
		slip = DivisorSlip(custom_daily_divisor_used=30.0)
		with divisor_by_span() as resolve:
			self.assertEqual(slip_daily_divisor(slip), (30.0, "snapshot on slip"))
		resolve.assert_not_called()


class TestCountingPeriod(TestCase):
	def test_joiner_stub_counts_over_the_period_and_keeps_its_dates(self):
		slip = FakeSlip(start_date=JOINED, joining_date=JOINED, relieving_date=None)
		with period(), patch(
			"nepal_hrms.custom_code.payroll.bs_period.extension_enabled", return_value=False
		):
			with CustomSalarySlip._counting_period(slip):
				self.assertEqual((slip.start_date, slip.end_date), (START, END))
				with settings():
					# The days before joining are charged like any period-start slip's.
					self.assertEqual(days_outside_employment(slip), 7.0)
		self.assertEqual((slip.start_date, slip.end_date), (JOINED, END))
