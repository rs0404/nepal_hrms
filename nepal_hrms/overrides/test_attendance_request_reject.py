"""A request whose day is already marked can still be rejected.

Stock refuses every save once there is no attendance left to create, which
left such a request stuck Open in the approver's list for good.
"""

from unittest import TestCase
from unittest.mock import patch

from hrms.hr.doctype.attendance_request.attendance_request import AttendanceRequest

from nepal_hrms.overrides.attendance_request import CustomAttendanceRequest


def _request(status):
	doc = CustomAttendanceRequest.__new__(CustomAttendanceRequest)
	doc.__dict__["status"] = status
	return doc


class TestRejectWithNothingToCreate(TestCase):
	def test_rejecting_skips_the_nothing_to_create_check(self):
		with patch.object(AttendanceRequest, "validate_no_attendance_to_create") as stock:
			_request("Rejected").validate_no_attendance_to_create()
		stock.assert_not_called()

	def test_open_and_approved_keep_the_check(self):
		for status in ("Open", "Approved"):
			with patch.object(AttendanceRequest, "validate_no_attendance_to_create") as stock:
				_request(status).validate_no_attendance_to_create()
			stock.assert_called_once()
