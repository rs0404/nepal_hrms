"""Back-dated leave is blocked once the window passes, bar the exempt types."""

from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.custom_code.leave_application_hooks import (
	exempt_leave_types,
	validate_leave_application_deadline,
)


def _leave(leave_type="Annual/Home Leave", to_date="2026-01-10", docstatus=0, status="Open"):
	return frappe._dict(
		employee="EMP-001",
		leave_type=leave_type,
		to_date=to_date,
		docstatus=docstatus,
		status=status,
	)


def _settings(enabled=1, exempt=("Sick Leave",), max_days=2):
	return frappe._dict(
		enable_leave_application_deadline=enabled,
		late_early_application_max_days=max_days,
		leave_types_exempt_from_deadline=[{"leave_type": name} for name in exempt],
	)


class TestExemptLeaveTypes(TestCase):
	def test_reads_the_child_rows(self):
		self.assertEqual(
			exempt_leave_types(_settings(exempt=("Sick Leave", "Bereavement"))),
			{"Sick Leave", "Bereavement"},
		)

	def test_an_empty_table_exempts_nothing(self):
		self.assertEqual(exempt_leave_types(_settings(exempt=())), set())

	def test_a_missing_field_exempts_nothing(self):
		self.assertEqual(exempt_leave_types(frappe._dict()), set())


class TestLeaveDeadline(TestCase):
	def _run(self, doc, settings=None, escaped=False):
		with patch(
			"nepal_hrms.custom_code.attendance_policy.get_hr_settings",
			return_value=settings or _settings(),
		), patch(
			"nepal_hrms.custom_code.policy_escape.has_policy_escape", return_value=escaped
		), patch(
			"nepal_hrms.custom_code.leave_application_hooks.today", return_value="2026-09-21"
		), patch(
			"nepal_hrms.custom_code.leave_application_hooks.frappe.throw",
			side_effect=frappe.ValidationError,
		) as throw:
			try:
				validate_leave_application_deadline(doc)
			except frappe.ValidationError:
				pass
			return throw.called

	def test_stale_leave_is_blocked(self):
		self.assertTrue(self._run(_leave()))

	def test_an_exempt_type_is_always_allowed(self):
		self.assertFalse(self._run(_leave(leave_type="Sick Leave")))

	def test_leave_inside_the_window_is_allowed(self):
		self.assertFalse(self._run(_leave(to_date="2026-09-20")))

	def test_the_deadline_day_itself_is_allowed(self):
		"""to_date 09-19 plus 2 days is 09-21, and today is 09-21."""
		self.assertFalse(self._run(_leave(to_date="2026-09-19")))

	def test_the_day_after_the_deadline_is_blocked(self):
		self.assertTrue(self._run(_leave(to_date="2026-09-18")))

	def test_the_rule_off_blocks_nothing(self):
		self.assertFalse(self._run(_leave(), settings=_settings(enabled=0)))

	def test_a_policy_escape_lets_it_through(self):
		self.assertFalse(self._run(_leave(), escaped=True))

	def test_a_cancellation_is_not_a_new_filing(self):
		self.assertFalse(self._run(_leave(docstatus=2)))
		self.assertFalse(self._run(_leave(status="Cancelled")))

	def test_a_leave_with_no_end_date_is_left_alone(self):
		self.assertFalse(self._run(_leave(to_date=None)))
