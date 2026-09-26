"""Which notification rows a new site starts with switched on.

Getting this wrong is quiet in both directions: too little and the approver
never hears about an application, too much and every check-in pushes a
notification to someone who never asked for one.
"""

from unittest import TestCase

from nepal_hrms.notifications.events import (
	DEFAULT_ON_EVENTS,
	EVENT_BY_KEY,
	seeded_row_defaults,
)

APPROVER_EVENTS = (
	"late_entry_app_new",
	"early_exit_app_new",
	"ooo_app_new",
	"attendance_request_new",
	"leave_app_new",
	"shift_request_new",
)


class TestDefaultOnSet(TestCase):
	def test_every_default_on_event_exists_in_the_catalog(self):
		for key in DEFAULT_ON_EVENTS:
			self.assertIn(key, EVENT_BY_KEY, f"{key} is defaulted on but not in the catalog")

	def test_the_six_application_events_are_on(self):
		self.assertEqual(set(DEFAULT_ON_EVENTS), set(APPROVER_EVENTS))


class TestSeededRowDefaults(TestCase):
	def test_an_application_row_can_actually_deliver(self):
		# enabled alone sends nothing: a row needs a channel and a recipient.
		for key in APPROVER_EVENTS:
			row = seeded_row_defaults(key)
			self.assertEqual(row["enabled"], 1, key)
			self.assertEqual(row["send_to_pwa"], 1, key)
			self.assertEqual(row["send_to_approver"], 1, key)

	def test_an_application_row_does_not_spam_the_employee(self):
		for key in APPROVER_EVENTS:
			row = seeded_row_defaults(key)
			self.assertEqual(row["send_to_employee"], 0, key)
			self.assertEqual(row["send_to_reports_to"], 0, key)
			self.assertEqual(row["send_to_channel"], 0, key)

	def test_everything_else_stays_opt_in(self):
		for key in EVENT_BY_KEY:
			if key in DEFAULT_ON_EVENTS:
				continue
			self.assertEqual(seeded_row_defaults(key), {
				"enabled": 0,
				"send_to_channel": 0,
				"send_to_employee": 0,
				"send_to_reports_to": 0,
				"send_to_approver": 0,
				"send_to_pwa": 0,
			}, key)

	def test_checkin_and_attendance_are_not_on(self):
		for key in ("checkin_in", "checkin_out", "attendance_present", "attendance_absent"):
			self.assertEqual(seeded_row_defaults(key)["enabled"], 0, key)

	def test_every_row_carries_the_same_keys(self):
		expected = set(seeded_row_defaults("checkin_in"))
		for key in EVENT_BY_KEY:
			self.assertEqual(set(seeded_row_defaults(key)), expected, key)
