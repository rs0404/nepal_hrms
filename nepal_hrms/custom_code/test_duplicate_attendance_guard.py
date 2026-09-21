"""One employee, one date, one submitted Attendance."""

from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.custom_code.attendance_hooks import guard_duplicate_attendance


def _att(name="new-attendance-1", employee="EMP-001", date="2026-07-14"):
	return frappe._dict(name=name, employee=employee, attendance_date=date)


class TestDuplicateAttendanceGuard(TestCase):
	def _run(self, existing, doc=None):
		with patch(
			"nepal_hrms.custom_code.attendance_hooks.frappe.db.get_value",
			return_value=existing,
		), patch(
			"nepal_hrms.custom_code.attendance_hooks.frappe.throw",
			side_effect=frappe.ValidationError,
		) as throw, patch(
			"nepal_hrms.custom_code.attendance_hooks.get_link_to_form", return_value="link"
		), patch(
			"nepal_hrms.custom_code.attendance_hooks.format_date", return_value="14-07-2026"
		):
			try:
				guard_duplicate_attendance(doc or _att())
			except frappe.ValidationError:
				pass
			return throw

	def test_a_second_submitted_row_is_refused(self):
		self.assertTrue(self._run("HR-ATT-2026-09606").called)

	def test_the_only_row_for_the_date_passes(self):
		self.assertFalse(self._run(None).called)

	def test_the_lookup_excludes_the_row_being_submitted(self):
		with patch(
			"nepal_hrms.custom_code.attendance_hooks.frappe.db.get_value",
			return_value=None,
		) as get_value:
			guard_duplicate_attendance(_att(name="HR-ATT-2026-09607"))
		filters = get_value.call_args.args[1]
		self.assertEqual(filters["name"], ["!=", "HR-ATT-2026-09607"])
		self.assertEqual(filters["docstatus"], 1)

	def test_an_incomplete_row_is_not_the_guard_s_business(self):
		self.assertFalse(self._run("X", doc=_att(employee=None)).called)
		self.assertFalse(self._run("X", doc=_att(date=None)).called)
