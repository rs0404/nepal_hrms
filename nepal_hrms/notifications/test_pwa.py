"""PWA notification routing: who hears an event, and who never does."""

from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.notifications import pwa
from nepal_hrms.notifications.events import EVENT_BY_KEY

EMP = "HR-EMP-001"
EMP_USER = "worker@example.com"
MANAGER_USER = "manager@example.com"
APPROVER_USER = "approver@example.com"


def _row(**over):
	base = {
		"event_key": "late_entry_app_new",
		"enabled": 1,
		"send_to_pwa": 1,
		"send_to_employee": 0,
		"send_to_reports_to": 0,
		"send_to_approver": 0,
		"message": None,
	}
	base.update(over)
	return frappe._dict(base)


def _doc(doctype="Late Entry Application", has_approver_field=False, **over):
	d = frappe._dict(
		{
			"doctype": doctype,
			"name": "APP-0001",
			"employee": EMP,
			"employee_name": "Worker",
			"status": "Approved",
			"attendance_date": "2026-09-01",
		}
	)
	d.update(over)
	d.meta = type("M", (), {"has_field": lambda _s, f: has_approver_field and f == "leave_approver"})()
	return d


class _Base(TestCase):
	"""frappe.db and frappe.local.session are unbound without a site, so the
	resolvers are patched directly rather than the database underneath them."""

	def setUp(self):
		self.inserted = []

		def fake_get_doc(payload):
			self.inserted.append(payload)
			return type("D", (), {"insert": lambda _s, **_k: None})()

		self.patches = [
			patch.object(frappe, "get_doc", fake_get_doc),
			patch.object(pwa, "_employee_user", lambda e: EMP_USER if e == EMP else None),
			patch.object(pwa, "_reports_to_user", lambda e: MANAGER_USER),
			patch.object(pwa, "_approver_user", lambda d: APPROVER_USER),
			patch.object(pwa, "_render", lambda e, d, o=None: "<b>msg</b>"),
		]
		for p in self.patches:
			p.start()

		self._session = getattr(frappe.local, "session", None)
		frappe.local.session = frappe._dict(user="someone-else@example.com")

	def tearDown(self):
		for p in self.patches:
			p.stop()
		frappe.local.session = self._session

	def recipients(self):
		return [i["to_user"] for i in self.inserted]


class TestRecipients(_Base):
	def _run(self, row):
		with patch.object(pwa, "_settings_row", return_value=row):
			pwa.notify(row.event_key, _doc())

	def test_approver_only(self):
		self._run(_row(send_to_approver=1))
		self.assertEqual(self.recipients(), [APPROVER_USER])

	def test_employee_only(self):
		self._run(_row(send_to_employee=1))
		self.assertEqual(self.recipients(), [EMP_USER])

	def test_all_three_deduplicated_and_ordered(self):
		self._run(_row(send_to_employee=1, send_to_reports_to=1, send_to_approver=1))
		self.assertEqual(self.recipients(), [EMP_USER, MANAGER_USER, APPROVER_USER])

	def test_no_boxes_ticked_sends_nothing(self):
		self._run(_row())
		self.assertEqual(self.recipients(), [])

	def test_the_actor_is_not_notified(self):
		frappe.local.session = frappe._dict(user=APPROVER_USER)
		self._run(_row(send_to_approver=1, send_to_employee=1))
		self.assertEqual(self.recipients(), [EMP_USER])


class TestGating(_Base):
	def test_disabled_row_sends_nothing(self):
		with patch.object(pwa, "_settings_row", return_value=None):
			self.assertEqual(pwa.notify("late_entry_app_new", _doc()), 0)
		self.assertEqual(self.recipients(), [])

	def test_unknown_event_key_sends_nothing(self):
		self.assertEqual(pwa.notify("no_such_event", _doc()), 0)

	def test_send_to_pwa_off_is_respected(self):
		"""_settings_row is the gate; a row without the box returns None."""
		settings = frappe._dict(enable_pwa_notifications=1, raven_notifications=[_row(send_to_pwa=0)])
		with patch.object(frappe, "get_cached_doc", return_value=settings):
			self.assertIsNone(pwa._settings_row("late_entry_app_new"))

	def test_master_switch_off_stops_every_event(self):
		settings = frappe._dict(
			enable_pwa_notifications=0, raven_notifications=[_row(send_to_pwa=1)]
		)
		with patch.object(frappe, "get_cached_doc", return_value=settings):
			self.assertIsNone(pwa._settings_row("late_entry_app_new"))

	def test_master_switch_on_lets_a_ticked_event_through(self):
		settings = frappe._dict(
			enable_pwa_notifications=1, raven_notifications=[_row(send_to_pwa=1)]
		)
		with patch.object(frappe, "get_cached_doc", return_value=settings):
			self.assertIsNotNone(pwa._settings_row("late_entry_app_new"))

	def test_master_switch_does_not_tick_events_for_you(self):
		"""On is not enough on its own; the per-event box still governs."""
		settings = frappe._dict(
			enable_pwa_notifications=1, raven_notifications=[_row(send_to_pwa=0)]
		)
		with patch.object(frappe, "get_cached_doc", return_value=settings):
			self.assertIsNone(pwa._settings_row("late_entry_app_new"))

	def test_master_switch_is_opt_in(self):
		"""Absent and unticked mean the same: a field default never reaches an
		existing Singleton, so anything else would read as broken on every site."""
		self.assertFalse(pwa._pwa_enabled(frappe._dict()))
		self.assertFalse(pwa._pwa_enabled(frappe._dict(enable_pwa_notifications=0)))
		self.assertFalse(pwa._pwa_enabled(frappe._dict(enable_pwa_notifications=None)))
		self.assertTrue(pwa._pwa_enabled(frappe._dict(enable_pwa_notifications=1)))

	def test_missing_send_to_pwa_column_is_treated_as_off(self):
		"""A site that has not synced the field must not error."""
		row = _row()
		row.pop("send_to_pwa")
		settings = frappe._dict(enable_pwa_notifications=1, raven_notifications=[row])
		with patch.object(frappe, "get_cached_doc", return_value=settings):
			self.assertIsNone(pwa._settings_row("late_entry_app_new"))


class TestEventMapping(TestCase):
	def test_leave_application_is_excluded(self):
		"""hrms.mixins.pwa_notifications already notifies it; twice is a bug."""
		for mapping in (pwa.EVENT_ON_NEW, pwa.EVENT_ON_SUBMIT):
			self.assertNotIn("Leave Application", mapping)

	def test_every_mapped_key_is_a_real_event(self):
		keys = list(pwa.EVENT_ON_NEW.values()) + list(pwa.EVENT_ON_SUBMIT.values())
		keys += list(pwa.ATTENDANCE_EVENT_BY_STATUS.values())
		for key in keys:
			self.assertIn(key, EVENT_BY_KEY, key)

	def test_absent_is_wired(self):
		self.assertEqual(pwa.ATTENDANCE_EVENT_BY_STATUS["Absent"], "attendance_absent")

	def test_all_three_applications_notify_on_create_and_decide(self):
		for dt in ("Late Entry Application", "Early Exit Application", "Out of Office Application"):
			self.assertIn(dt, pwa.EVENT_ON_NEW)
			self.assertIn(dt, pwa.EVENT_ON_SUBMIT)


class TestNeverBlocksASave(_Base):
	def test_a_raising_notifier_is_swallowed(self):
		with patch.object(pwa, "notify", side_effect=RuntimeError("boom")), patch.object(
			frappe, "log_error"
		):
			pwa.notify_application_created(_doc())  # must not raise
			pwa.notify_attendance(_doc(doctype="Attendance", status="Absent"))
