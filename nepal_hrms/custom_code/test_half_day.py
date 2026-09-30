"""Half-day leave: the worked half is judged from check-ins, not swept to Absent.

The bug: the check-in sync skipped leave rows, so modify_half_day_status stayed
set and stock's mark_absent_for_half_day_dates marked people who had checked in
Absent for the half they worked.
"""

from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.custom_code import half_day
from nepal_hrms.overrides import attendance_override

SHIFT = "A - 09:30-17:30"
# (start, midpoint, end) in seconds: 09:30, 13:30, 17:30
WINDOW = (9.5 * 3600, 13.5 * 3600, 17.5 * 3600)
ABSENT_TH, HALF_TH = 3.99, 7.0


class _StubDB:
	"""What frappe.db proxies; the proxy is unbound without a site."""

	def __init__(self, singles=None):
		self.singles = singles or {}

	def get_value(self, doctype, name, fields=None, *a, **k):
		if doctype == "Shift Type":
			return (ABSENT_TH, HALF_TH)
		return None

	def sql(self, query, values=None, *a, **k):
		field = values[1] if values else None
		return [[self.singles[field]]] if field in self.singles else []


class _Meta:
	def has_field(self, fieldname):
		return True


def _attendance(**over):
	d = frappe._dict(
		name="ATT-1",
		employee="EMP-1",
		attendance_date="2026-09-01",
		status="Half Day",
		leave_type="Sick Leave",
		half_day_status="Present",
		shift=SHIFT,
		attendance_request=None,
	)
	d.update(over)
	return d


def _computed(hours=4.0, first_in="2026-09-01 09:35:00", checkins=("CHK-1", "CHK-2"), unpaired=False):
	return frappe._dict(
		total_hours=hours,
		first_in=first_in and datetime.fromisoformat(first_in),
		last_out=first_in and datetime.fromisoformat(first_in) + timedelta(hours=hours),
		shift_name=SHIFT,
		checkin_names=list(checkins),
		unpaired_in=unpaired,
	)


class _Base(TestCase):
	def setUp(self):
		self._db = getattr(frappe.local, "db", None)
		frappe.local.db = _StubDB()
		frappe.local._nepal_half_day_scaling = None
		frappe.local._nepal_half_day_windows = None
		self.patches = [
			patch.object(frappe, "get_meta", return_value=_Meta()),
			patch.object(half_day, "shift_window", return_value=WINDOW),
			patch.object(attendance_override, "_has_approved_attendance_request", return_value=False),
		]
		for p in self.patches:
			p.start()

	def tearDown(self):
		for p in self.patches:
			p.stop()
		frappe.local.db = self._db

	def plan(self, attendance=None, computed=None, leave=None, scaling=False):
		with patch.object(half_day, "half_day_leave_on", return_value=leave), patch.object(
			half_day, "scaling_enabled", return_value=scaling
		):
			return half_day.compute_half_day_other_half(attendance or _attendance(), computed or _computed())


class TestWhichRowsAreSettled(_Base):
	def test_full_day_leave_is_left_alone(self):
		self.assertIsNone(self.plan(_attendance(status="On Leave")))

	def test_half_day_without_a_leave_is_left_alone(self):
		"""A ½P penalty is also Half Day; it has no leave half to settle."""
		self.assertIsNone(self.plan(_attendance(leave_type=None)))


class TestTheBug(_Base):
	def test_a_worked_half_is_present_and_the_sweep_flag_is_cleared(self):
		values = self.plan(computed=_computed(hours=4.2)).writes
		self.assertEqual(values["half_day_status"], "Present")
		self.assertEqual(values["modify_half_day_status"], 0)

	def test_too_few_hours_is_absent_like_stock(self):
		values = self.plan(computed=_computed(hours=1.5)).writes
		self.assertEqual(values["half_day_status"], "Absent")
		self.assertEqual(values["modify_half_day_status"], 0)

	def test_no_checkins_leaves_the_flag_for_the_stock_sweep(self):
		"""Nobody came: stock's Absent is right, so do not pre-empt it."""
		values = self.plan(computed=_computed(checkins=(), first_in=None)).writes
		self.assertNotIn("half_day_status", values)
		self.assertNotIn("modify_half_day_status", values)

	def test_unpaired_in_is_present_not_zero_hours(self):
		values = self.plan(computed=_computed(hours=0, unpaired=True)).writes
		self.assertEqual(values["half_day_status"], "Present")

	def test_an_approved_attendance_request_keeps_its_ruling(self):
		with patch.object(attendance_override, "_has_approved_attendance_request", return_value=True):
			values = self.plan(_attendance(half_day_status="Absent"), _computed(hours=6)).writes
		self.assertEqual(values["half_day_status"], "Absent")


class TestScaling(_Base):
	"""2.5h of work: under the 3.99h absent threshold, over half of it (1.995h)."""

	def test_off_uses_the_shifts_own_thresholds(self):
		values = self.plan(computed=_computed(hours=2.5), scaling=False).writes
		self.assertEqual(values["half_day_status"], "Absent")

	def test_on_halves_them(self):
		values = self.plan(computed=_computed(hours=2.5), scaling=True).writes
		self.assertEqual(values["half_day_status"], "Present")

	def test_status_from_hours_scales_both_thresholds(self):
		sfh = attendance_override._status_from_hours
		self.assertEqual(sfh(3.0, SHIFT), "Absent")
		self.assertEqual(sfh(3.0, SHIFT, factor=0.5), "Half Day")  # 3.0 < 7.0 * 0.5
		self.assertEqual(sfh(3.6, SHIFT, factor=0.5), "Present")


class TestScalingSwitch(TestCase):
	"""Read from tabSingles: a never-saved Check loads as 0 and would read off."""

	def setUp(self):
		self._db = getattr(frappe.local, "db", None)
		frappe.local._nepal_half_day_scaling = None

	def tearDown(self):
		frappe.local.db = self._db
		frappe.local._nepal_half_day_scaling = None

	def _enabled(self, singles):
		frappe.local.db = _StubDB(singles)
		frappe.local._nepal_half_day_scaling = None
		return half_day.scaling_enabled()

	def test_never_saved_reads_as_on(self):
		self.assertTrue(self._enabled({}))

	def test_saved_off_is_off(self):
		self.assertFalse(self._enabled({half_day.SCALE_FIELD: "0"}))

	def test_saved_on_is_on(self):
		self.assertTrue(self._enabled({half_day.SCALE_FIELD: "1"}))


class TestWhichHalf(_Base):
	def test_the_leaves_own_choice_wins(self):
		leave = frappe._dict({half_day.SESSION_FIELD: half_day.FIRST_HALF})
		plan = self.plan(leave=leave, computed=_computed(first_in="2026-09-01 09:35:00"))
		self.assertEqual(plan.writes[half_day.SESSION_FIELD], half_day.FIRST_HALF)

	def test_a_morning_arrival_means_the_afternoon_was_leave(self):
		plan = self.plan(computed=_computed(first_in="2026-09-01 09:35:00"))
		self.assertEqual(plan.writes[half_day.SESSION_FIELD], half_day.SECOND_HALF)

	def test_an_afternoon_arrival_means_the_morning_was_leave(self):
		plan = self.plan(computed=_computed(first_in="2026-09-01 13:40:00"))
		self.assertEqual(plan.writes[half_day.SESSION_FIELD], half_day.FIRST_HALF)

	def test_no_choice_and_no_checkin_records_no_half(self):
		plan = self.plan(computed=_computed(checkins=(), first_in=None))
		self.assertNotIn(half_day.SESSION_FIELD, plan.writes)

	def test_worked_half_is_the_other_one(self):
		self.assertEqual(half_day.worked_half_for_session(half_day.FIRST_HALF), "second")
		self.assertEqual(half_day.worked_half_for_session(half_day.SECOND_HALF), "first")
		self.assertIsNone(half_day.worked_half_for_session(None))


class TestLeaveHook(TestCase):
	def test_ignores_leaves_that_are_not_half_days(self):
		with patch.object(half_day, "resolve_half_day_other_half") as resolve:
			half_day.on_leave_application_change(frappe._dict(half_day=0, docstatus=1, status="Approved"))
		resolve.assert_not_called()

	def test_ignores_unapproved(self):
		with patch.object(half_day, "resolve_half_day_other_half") as resolve:
			half_day.on_leave_application_change(
				frappe._dict(half_day=1, half_day_date="2026-09-01", docstatus=1, status="Rejected")
			)
		resolve.assert_not_called()

	def test_a_failure_never_blocks_the_approval(self):
		doc = frappe._dict(
			half_day=1, half_day_date="2026-09-01", docstatus=1, status="Approved", employee="EMP-1"
		)
		# Not patch.object(frappe.local, "db"): a werkzeug Local has no __dict__, so
		# patch cannot see the attribute is there and deletes it on the way out.
		stub = _StubDB()
		stub.get_value = lambda *a, **k: "ATT-1"
		saved = getattr(frappe.local, "db", None)
		frappe.local.db = stub
		try:
			with patch.object(frappe, "log_error"), patch.object(
				half_day, "resolve_half_day_other_half", side_effect=RuntimeError("boom")
			):
				half_day.on_leave_application_change(doc)  # must not raise
		finally:
			frappe.local.db = saved


class TestSessionRequired(TestCase):
	"""A new half-day leave must say which half; old submitted ones never block."""

	def _leave(self, **over):
		d = frappe._dict(half_day=1, half_day_date="2026-09-01", from_date="2026-09-01", docstatus=0)
		d[half_day.SESSION_FIELD] = None
		d.update(over)
		d.meta = _Meta()
		d.set = lambda k, v: d.__setitem__(k, v)
		return d

	def _validate(self, doc):
		from nepal_hrms.custom_code.leave_application_hooks import validate_half_day_session

		with patch("nepal_hrms.custom_code.leave_application_hooks.format_date", return_value="1 Sep"):
			return validate_half_day_session(doc)

	def test_a_draft_half_day_without_a_half_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self._validate(self._leave())

	def test_a_draft_with_a_half_passes(self):
		self._validate(self._leave(**{half_day.SESSION_FIELD: half_day.SECOND_HALF}))

	def test_a_submitted_leave_from_before_the_field_is_never_blocked(self):
		self._validate(self._leave(docstatus=1))

	def test_unticking_half_day_clears_a_stale_half(self):
		doc = self._leave(half_day=0, **{half_day.SESSION_FIELD: half_day.FIRST_HALF})
		self._validate(doc)
		self.assertIsNone(doc[half_day.SESSION_FIELD])


class TestSheetHalfBounds(TestCase):
	"""BS sheet: which clock half a half-day cell marks. 09:00-17:00 = 540-1020."""

	def _bounds(self, abbr, session=None):
		from nepal_hrms.nepal_hrms.report.monthly_attendance_sheet_bs.monthly_attendance_sheet_bs import (
			_half_day_bounds,
		)

		return _half_day_bounds(abbr, 540, 1020, session)

	def test_leave_goes_on_the_recorded_half(self):
		self.assertEqual(self._bounds("HD/P", half_day.FIRST_HALF), (540, 780))
		self.assertEqual(self._bounds("HD/P", half_day.SECOND_HALF), (780, 1020))

	def test_the_charged_half_is_the_one_the_leave_did_not_cover(self):
		self.assertEqual(self._bounds("HD/A", half_day.FIRST_HALF), (780, 1020))
		self.assertEqual(self._bounds("HD/A", half_day.SECOND_HALF), (540, 780))

	def test_unrecorded_keeps_the_old_fixed_halves(self):
		self.assertEqual(self._bounds("HD/P"), (540, 780))
		self.assertEqual(self._bounds("HD/A"), (780, 1020))
