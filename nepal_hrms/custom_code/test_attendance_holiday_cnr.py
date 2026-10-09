"""Holidays and approved Attendance Requests must not produce late/early/penalty."""

from datetime import date
from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.custom_code import attendance_holiday, attendance_policy
from nepal_hrms.custom_code.attendance_holiday import clear_cnr_flags


def _doc(**overrides):
	"""Minimal Attendance stand-in carrying every field the C&R engine touches."""
	fields = {
		"employee": "EMP-1",
		"attendance_date": date(2026, 1, 10),
		"status": "Present",
		"half_day_status": None,
		"leave_type": None,
		"name": "ATT-1",
		"shift": None,
		"in_time": "2026-01-10 09:40:00",
		"out_time": "2026-01-10 18:00:00",
		"late_entry": 0,
		"early_exit": 0,
		"custom_late_mins": 0,
		"custom_early_mins": 0,
		"custom_cnr_unexcused_late": 0,
		"custom_cnr_unexcused_early": 0,
		"custom_cnr_late_in_pool": 0,
		"custom_cnr_early_in_pool": 0,
		"custom_cnr_month_late_pool_count": 0,
		"custom_cnr_month_early_pool_count": 0,
		"custom_cnr_pool_penalty": "",
	}
	fields.update(overrides)
	return frappe._dict(fields)


class TestClearCnrFlags(TestCase):
	def test_keep_minutes_leaves_timing_readable(self):
		doc = _doc(late_entry=1, custom_late_mins=40, custom_cnr_late_in_pool=1)
		clear_cnr_flags(doc, keep_minutes=True)
		self.assertEqual(doc.custom_late_mins, 40)
		self.assertEqual(doc.late_entry, 0)
		self.assertEqual(doc.custom_cnr_late_in_pool, 0)

	def test_default_still_clears_minutes(self):
		doc = _doc(late_entry=1, custom_late_mins=40)
		clear_cnr_flags(doc)
		self.assertEqual(doc.custom_late_mins, 0)
		self.assertEqual(doc.late_entry, 0)

	def test_reset_half_day_status_can_be_suppressed(self):
		doc = _doc(half_day_status="Absent")
		clear_cnr_flags(doc, reset_half_day_status=False)
		self.assertEqual(doc.half_day_status, "Absent")
		clear_cnr_flags(doc)
		self.assertIsNone(doc.half_day_status)


class TestHolidayGuard(TestCase):
	"""apply_late_early_to_attendance must exclude holiday dates from every count."""

	def run_engine(self, doc, *, is_holiday, weekly_off=False, has_checkins=True, settings=None):
		settings = settings or frappe._dict(
			enable_late_early_penalty=1,
			late_early_grace_mins=15,
			late_early_max_delay_mins=60,
		)
		info = frappe._dict(
			is_holiday=is_holiday, weekly_off=weekly_off, holiday_list="HL" if is_holiday else None
		)
		with patch.object(attendance_policy, "get_hr_settings", return_value=settings), patch.object(
			attendance_policy, "compute_late_early_minutes", return_value=(40, 0)
		), patch.object(attendance_holiday, "holiday_info", return_value=info), patch.object(
			attendance_holiday, "has_checkins", return_value=has_checkins
		), patch.object(
			attendance_policy, "count_month_pool", return_value=0
		), patch.object(
			attendance_policy, "has_policy_escape", create=True, return_value=0
		), patch(
			"nepal_hrms.custom_code.policy_escape.has_policy_escape", return_value=0
		), patch.object(
			attendance_policy, "get_approved_application", return_value=None
		), patch.object(
			attendance_policy, "_current_doc_pool_penalty", return_value=""
		):
			attendance_policy.apply_late_early_to_attendance(doc, apply_unexcused_status=True)
		return doc

	def test_holiday_keeps_minutes_but_clears_every_count(self):
		doc = self.run_engine(_doc(), is_holiday=True)
		self.assertEqual(doc.custom_late_mins, 40, "raw timing must stay visible")
		self.assertEqual(doc.late_entry, 0)
		self.assertEqual(doc.custom_cnr_late_in_pool, 0)
		self.assertEqual(doc.custom_cnr_unexcused_late, 0)
		self.assertEqual(doc.custom_cnr_pool_penalty, "")

	def test_worked_holiday_marked_present_is_still_excluded(self):
		# apply_holiday_sandwich_status rewrites a worked holiday to Present, so a
		# status-based guard would miss exactly this case. The guard is date-based.
		doc = self.run_engine(_doc(status="Present"), is_holiday=True)
		self.assertEqual(doc.late_entry, 0)
		self.assertEqual(doc.custom_cnr_late_in_pool, 0)

	def test_holiday_penalty_written_earlier_is_undone_in_the_same_pass(self):
		# custom_cnr_pool_penalty is the only signal the period sweep uses to spot a
		# status it wrote, so clearing it must not strand the Half Day.
		doc = self.run_engine(
			_doc(status="Half Day", half_day_status="Absent", custom_cnr_pool_penalty="half"),
			is_holiday=True,
		)
		self.assertEqual(doc.custom_cnr_pool_penalty, "")
		self.assertEqual(doc.status, "Present", "worked holiday returns to Present")

	def test_holiday_penalty_without_checkins_returns_to_weekly_off(self):
		doc = self.run_engine(
			_doc(status="Absent", custom_cnr_pool_penalty="full"),
			is_holiday=True,
			weekly_off=True,
			has_checkins=False,
		)
		self.assertEqual(doc.status, "Weekly Off")

	def test_working_day_still_counts(self):
		doc = self.run_engine(_doc(), is_holiday=False)
		self.assertEqual(doc.custom_late_mins, 40)
		self.assertEqual(doc.late_entry, 1, "a normal working day is unaffected")


class TestProtectedStatus(TestCase):
	def test_holiday_and_weekly_off_are_protected(self):
		self.assertTrue(attendance_policy._protected_status(_doc(status="Holiday")))
		self.assertTrue(attendance_policy._protected_status(_doc(status="Weekly Off")))

	def test_is_holiday_hint_short_circuits(self):
		self.assertTrue(
			attendance_policy._protected_status(_doc(status="Present"), is_holiday=True)
		)

	def test_present_is_still_unprotected(self):
		self.assertFalse(attendance_policy._protected_status(_doc(status="Present")))

	def test_protected_holiday_row_keeps_its_status(self):
		doc = _doc(status="Weekly Off", custom_cnr_pool_penalty="full")
		attendance_policy._apply_pool_or_major_status(doc, "full", 0, False, is_holiday=True)
		self.assertEqual(doc.status, "Weekly Off")
		self.assertEqual(doc.custom_cnr_pool_penalty, "")


class TestPoolExcludesHolidays(TestCase):
	"""The pool is indexed by position, so a stray holiday shifts who gets charged."""

	def _flags(self, holidays):
		rows = [
			frappe._dict(attendance_date=date(2026, 1, d), custom_cnr_late_in_pool=1, custom_cnr_early_in_pool=0)
			for d in (5, 6, 7, 8)
		]
		meta = type("M", (), {"has_field": lambda _s, _f: True})()
		with patch.object(frappe, "get_meta", return_value=meta), patch.object(
			frappe, "get_all", return_value=rows
		), patch.object(attendance_holiday, "holiday_dates_between", return_value=holidays), patch.object(
			attendance_policy, "_late_early_escaped_dates", return_value=set()
		):
			return attendance_policy._pool_flags_between("EMP-1", date(2026, 1, 1), date(2026, 1, 31))

	def test_holiday_days_are_dropped(self):
		flags = self._flags({date(2026, 1, 6)})
		self.assertEqual([f[0] for f in flags], [date(2026, 1, 5), date(2026, 1, 7), date(2026, 1, 8)])

	def test_dropping_a_holiday_shifts_which_day_is_charged(self):
		settings = frappe._dict(
			initial_grace_occurrences=2,
			subsequent_grace_step_occurrences=2,
			combine_late_and_early_pool=0,
			enable_late_full_day_escalation=0,
			late_full_day_after_occurrences=5,
		)
		charged = lambda flags: attendance_policy.assign_employee_pool_penalties(flags, settings)

		with_holiday = charged(self._flags(set()))
		without_holiday = charged(self._flags({date(2026, 1, 6)}))

		# 3rd pool occurrence is the penalty slot.
		self.assertEqual(with_holiday, {date(2026, 1, 7): "half"})
		self.assertEqual(
			without_holiday,
			{date(2026, 1, 8): "half"},
			"the holiday must not consume a pool slot ahead of a real working day",
		)


class TestApprovedAttendanceRequest(TestCase):
	def test_null_status_on_a_submitted_request_counts_as_approved(self):
		# Requests predating the custom status field carry SQL NULL, which an
		# ["in", ["Approved", ""]] filter would not match.
		self.assertTrue(attendance_policy._attendance_request_is_approved({"status": None}))
		self.assertTrue(attendance_policy._attendance_request_is_approved({"status": "Approved"}))
		self.assertFalse(attendance_policy._attendance_request_is_approved({"status": "Rejected"}))

	def test_dates_are_clipped_to_the_window(self):
		rows = [
			frappe._dict(
				name="AR-1", status="Approved",
				from_date=date(2026, 1, 1), to_date=date(2026, 1, 31),
			)
		]
		frappe.local._nepal_approved_attendance_requests = {}
		with patch.object(frappe, "get_all", return_value=rows):
			dates = attendance_policy.approved_attendance_request_dates(
				"EMP-1", date(2026, 1, 10), date(2026, 1, 12)
			)
		self.assertEqual(dates, {date(2026, 1, 10), date(2026, 1, 11), date(2026, 1, 12)})

	def test_rejected_request_covers_nothing(self):
		rows = [
			frappe._dict(
				name="AR-1", status="Rejected",
				from_date=date(2026, 1, 1), to_date=date(2026, 1, 31),
			)
		]
		frappe.local._nepal_approved_attendance_requests = {}
		with patch.object(frappe, "get_all", return_value=rows):
			dates = attendance_policy.approved_attendance_request_dates(
				"EMP-1", date(2026, 1, 10), date(2026, 1, 12)
			)
		self.assertEqual(dates, set())


class TestAttendanceRequestExcuse(TestCase):
	def run_engine(self, setting_value):
		doc = _doc()
		settings = frappe._dict(
			enable_late_early_penalty=1,
			late_early_grace_mins=15,
			late_early_max_delay_mins=60,
			excuse_late_early_on_attendance_request=setting_value,
		)
		info = frappe._dict(is_holiday=False, weekly_off=False, holiday_list=None)
		with patch.object(attendance_policy, "get_hr_settings", return_value=settings), patch.object(
			attendance_policy, "compute_late_early_minutes", return_value=(40, 0)
		), patch.object(attendance_holiday, "holiday_info", return_value=info), patch.object(
			attendance_policy, "count_month_pool", return_value=0
		), patch(
			"nepal_hrms.custom_code.policy_escape.has_policy_escape", return_value=0
		), patch.object(
			attendance_policy, "get_approved_attendance_request", return_value={"name": "AR-1"}
		), patch.object(
			attendance_policy, "get_approved_application", return_value=None
		), patch.object(
			attendance_policy, "_current_doc_pool_penalty", return_value=""
		):
			attendance_policy.apply_late_early_to_attendance(doc, apply_unexcused_status=True)
		return doc

	def test_setting_off_still_counts_the_late(self):
		doc = self.run_engine("0")
		self.assertEqual(doc.late_entry, 1)
		self.assertEqual(doc.custom_cnr_late_in_pool, 1)

	def test_setting_on_excuses_everything(self):
		# The string form matters: get_singles_dict(cast=False) returns "0"/"1", and
		# a bare truthiness test would read "0" as on.
		doc = self.run_engine("1")
		self.assertEqual(doc.late_entry, 0)
		self.assertEqual(doc.custom_cnr_late_in_pool, 0)
		self.assertEqual(doc.custom_cnr_unexcused_late, 0)
		self.assertEqual(doc.custom_late_mins, 40, "minutes stay for reference")

	def test_string_zero_reads_as_off(self):
		self.assertEqual(self.run_engine("0").late_entry, 1)


class TestDefaultNeedsNoCheckins(TestCase):
	def test_no_punches_yields_no_late_or_early(self):
		# A row created by an Attendance Request with no check-ins has nothing to
		# judge, so the documented default falls straight out of the minute maths.
		with patch.object(attendance_policy, "get_shift_bounds", return_value=(None, None)):
			self.assertEqual(
				attendance_policy.compute_late_early_minutes(
					"EMP-1", date(2026, 1, 10), in_time=None, out_time=None
				),
				(0, 0),
			)
