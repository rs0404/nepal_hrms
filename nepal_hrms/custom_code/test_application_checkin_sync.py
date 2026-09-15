from datetime import datetime, time
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from frappe import _dict

from nepal_hrms.custom_code.application_hooks import (
	_fill_actuals_from_existing_checkins,
	_validate_application_reason,
	_validate_cnr_application_deadline,
	_validate_cnr_application_time_limit,
	sync_cnr_application_from_checkin,
)


class TestApplicationCheckinSync(TestCase):
	@patch(
		"nepal_hrms.custom_code.application_hooks._set_application_actuals"
	)
	@patch("nepal_hrms.custom_code.application_hooks._active_application")
	def test_normal_in_fills_late_entry_actual_time(
		self, active_application, set_actuals
	):
		application = Mock()
		active_application.return_value = application
		checkin = _dict(
			employee="EMP-1",
			time=datetime(2026, 9, 14, 10, 12, 34),
			shift_start=datetime(2026, 9, 14, 9, 30),
			log_type="IN",
			custom_attendance_type="Normal",
		)

		sync_cnr_application_from_checkin(checkin)

		active_application.assert_called_once_with(
			"Late Entry Application",
			"EMP-1",
			datetime(2026, 9, 14).date(),
			{"late_entry_time": ["is", "not set"]},
		)
		set_actuals.assert_called_once_with(
			application, {"late_entry_time": time(10, 12, 34)}
		)

	@patch(
		"nepal_hrms.custom_code.application_hooks._set_application_actuals"
	)
	@patch(
		"nepal_hrms.custom_code.application_hooks._ooo_application_for_checkin"
	)
	@patch("nepal_hrms.custom_code.application_hooks.frappe.get_meta")
	def test_ooo_out_fills_actual_return_and_duration(
		self, get_meta, ooo_application, set_actuals
	):
		get_meta.return_value.has_field.return_value = False
		application = _dict(from_time=time(13, 0))
		ooo_application.return_value = application
		checkin = _dict(
			employee="EMP-1",
			time=datetime(2026, 9, 14, 15, 30),
			shift_start=datetime(2026, 9, 14, 9, 30),
			log_type="OUT",
			custom_attendance_type="OOO Work",
		)

		sync_cnr_application_from_checkin(checkin)

		set_actuals.assert_called_once_with(
			application,
			{"to_time": time(15, 30), "total_hours": 2.5},
		)


class TestApplicationLimits(TestCase):
	@patch(
		"nepal_hrms.custom_code.application_hooks.frappe.get_all",
		return_value=[],
	)
	@patch(
		"nepal_hrms.custom_code.application_hooks.frappe.get_meta"
	)
	def test_client_supplied_late_actual_is_cleared_without_checkin(
		self, get_meta, get_all
	):
		get_meta.return_value.has_field.return_value = False
		doc = Mock()
		doc.employee = "EMP-1"
		doc.attendance_date = "2026-09-14"
		doc.doctype = "Late Entry Application"
		doc.status = "Draft"
		doc.late_entry_time = time(7, 18, 47)
		doc.is_new.return_value = True

		_fill_actuals_from_existing_checkins(doc)

		self.assertIsNone(doc.late_entry_time)

	def test_reason_is_required(self):
		with self.assertRaises(frappe.ValidationError):
			_validate_application_reason(_dict(reason="  "))

	@patch(
		"nepal_hrms.custom_code.application_hooks.get_hr_settings"
	)
	def test_ooo_estimate_above_limit_is_blocked(self, get_settings):
		get_settings.return_value = _dict(
			max_paid_out_of_office_hours=2
		)
		doc = _dict(
			doctype="Out of Office Application",
			type_of_work="Personal Work",
			estimated_from_time=time(10, 0),
			estimated_to_time=time(12, 30),
		)

		with self.assertRaises(frappe.ValidationError):
			_validate_cnr_application_time_limit(doc)

	@patch(
		"nepal_hrms.custom_code.application_hooks.get_shift_bounds"
	)
	@patch(
		"nepal_hrms.custom_code.application_hooks.get_hr_settings"
	)
	def test_late_estimate_above_limit_is_blocked(
		self, get_settings, get_shift_bounds
	):
		get_settings.return_value = _dict(late_early_max_delay_mins=60)
		get_shift_bounds.return_value = (
			datetime(2026, 9, 14, 9, 30),
			datetime(2026, 9, 14, 17, 30),
		)
		doc = _dict(
			doctype="Late Entry Application",
			type_of_work="Personal Work",
			employee="EMP-1",
			attendance_date="2026-09-14",
			attendance=None,
			estimated_late_entry_time=time(10, 31),
		)

		with self.assertRaises(frappe.ValidationError):
			_validate_cnr_application_time_limit(doc)

	@patch(
		"nepal_hrms.custom_code.application_hooks.get_shift_bounds"
	)
	@patch(
		"nepal_hrms.custom_code.application_hooks.get_hr_settings"
	)
	def test_late_estimate_above_limit_allowed_when_rejected(
		self, get_settings, get_shift_bounds
	):
		get_settings.return_value = _dict(late_early_max_delay_mins=60)
		get_shift_bounds.return_value = (
			datetime(2026, 9, 14, 9, 30),
			datetime(2026, 9, 14, 17, 30),
		)
		doc = _dict(
			doctype="Late Entry Application",
			status="Rejected",
			type_of_work="Personal Work",
			employee="EMP-1",
			attendance_date="2026-09-14",
			attendance=None,
			estimated_late_entry_time=time(10, 54),
		)

		_validate_cnr_application_time_limit(doc)

	@patch(
		"nepal_hrms.custom_code.application_hooks.get_hr_settings"
	)
	def test_ooo_estimate_above_limit_allowed_when_rejected(self, get_settings):
		get_settings.return_value = _dict(max_paid_out_of_office_hours=2)
		doc = _dict(
			doctype="Out of Office Application",
			status="Rejected",
			type_of_work="Personal Work",
			estimated_from_time=time(10, 0),
			estimated_to_time=time(13, 0),
		)

		_validate_cnr_application_time_limit(doc)

	@patch(
		"nepal_hrms.custom_code.application_hooks.get_shift_bounds"
	)
	@patch(
		"nepal_hrms.custom_code.application_hooks.get_hr_settings"
	)
	def test_late_estimate_above_limit_allowed_for_office_work(
		self, get_settings, get_shift_bounds
	):
		get_settings.return_value = _dict(late_early_max_delay_mins=60)
		get_shift_bounds.return_value = (
			datetime(2026, 9, 14, 9, 30),
			datetime(2026, 9, 14, 17, 30),
		)
		doc = _dict(
			doctype="Late Entry Application",
			type_of_work="Office Work",
			employee="EMP-1",
			attendance_date="2026-09-14",
			attendance=None,
			estimated_late_entry_time=time(10, 54),
		)

		_validate_cnr_application_time_limit(doc)

	@patch(
		"nepal_hrms.custom_code.application_hooks.get_hr_settings"
	)
	def test_ooo_estimate_above_limit_allowed_for_office_work(self, get_settings):
		get_settings.return_value = _dict(max_paid_out_of_office_hours=2)
		doc = _dict(
			doctype="Out of Office Application",
			type_of_work="Office Work",
			estimated_from_time=time(10, 0),
			estimated_to_time=time(13, 0),
		)

		_validate_cnr_application_time_limit(doc)

	@patch("nepal_hrms.custom_code.application_hooks.today")
	@patch(
		"nepal_hrms.custom_code.application_hooks.get_hr_settings"
	)
	def test_ooo_uses_shared_application_deadline(
		self, get_settings, today
	):
		get_settings.return_value = _dict(
			enable_late_early_application_deadline=1,
			late_early_application_max_days=2,
		)
		today.return_value = "2026-09-14"
		doc = _dict(
			doctype="Out of Office Application",
			employee="EMP-1",
			attendance_date="2026-09-11",
		)

		with self.assertRaises(frappe.ValidationError):
			_validate_cnr_application_deadline(doc)

	@patch("nepal_hrms.custom_code.application_hooks.today")
	@patch(
		"nepal_hrms.custom_code.application_hooks.get_hr_settings"
	)
	def test_deadline_does_not_block_rejection(self, get_settings, today):
		get_settings.return_value = _dict(
			enable_late_early_application_deadline=1,
			late_early_application_max_days=2,
		)
		today.return_value = "2026-09-14"
		doc = _dict(
			doctype="Out of Office Application",
			status="Rejected",
			employee="EMP-1",
			attendance_date="2026-09-11",
		)

		_validate_cnr_application_deadline(doc)
