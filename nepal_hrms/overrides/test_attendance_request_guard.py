from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.overrides.attendance_override import _has_approved_attendance_request



class TestApprovedAttendanceRequestGuard(TestCase):
	def test_no_request_is_not_protected(self):
		self.assertFalse(
			_has_approved_attendance_request(frappe._dict(attendance_request=None))
		)

	def _protected(self, docstatus, request):
		# frappe.db is an unbound proxy outside a site, so swap the module reference.
		with patch("nepal_hrms.overrides.attendance_override.frappe") as mock_frappe:
			mock_frappe.db.get_value.return_value = docstatus
			return _has_approved_attendance_request(
				frappe._dict(attendance_request=request)
			)

	def test_submitted_request_is_protected(self):
		self.assertTrue(self._protected(1, "HR-ARQ-26-09-00032"))

	def test_draft_request_is_not_protected(self):
		self.assertFalse(self._protected(0, "HR-ARQ-26-09-00040"))

	def test_cancelled_request_is_not_protected(self):
		self.assertFalse(self._protected(2, "HR-ARQ-26-09-00024"))
