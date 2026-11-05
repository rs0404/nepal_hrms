"""Self-approval gaps: Shift Request's setting, the HR Settings mirror, OOO ticks in Desk."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from nepal_hrms.api import ooo_attendance
from nepal_hrms.custom_code import approval_hooks


def _checkin(new=False, changed=(), ignore_permissions=False, **values):
	doc = MagicMock()
	doc.flags = frappe._dict(ignore_permissions=ignore_permissions)
	doc.meta.has_field = lambda field: True
	doc.get = lambda field: values.get(field, 0)
	doc.is_new = lambda: new
	doc.has_value_changed = lambda field: field in changed
	doc.employee = "EMP-STAFF"
	doc.time = "2026-11-05 10:00:00"
	return doc


class TestOOOTickInDesk(TestCase):
	def _run(self, doc):
		with patch.object(ooo_attendance, "_assert_is_leave_approver") as check:
			ooo_attendance._check_ooo_decision(doc)
		return check

	def test_ticking_approved_takes_the_approver_rule(self):
		check = self._run(_checkin(changed=("custom_is_approved",), custom_is_approved=1))
		check.assert_called_once()

	def test_ticking_rejected_takes_the_approver_rule(self):
		check = self._run(_checkin(changed=("custom_ooo_rejected",), custom_ooo_rejected=1))
		check.assert_called_once()

	def test_a_new_check_in_created_approved_takes_it_too(self):
		check = self._run(_checkin(new=True, custom_is_approved=1))
		check.assert_called_once()

	def test_a_save_that_leaves_the_decision_alone_does_not(self):
		check = self._run(_checkin(custom_is_approved=1))
		check.assert_not_called()

	def test_system_saves_pass(self):
		check = self._run(
			_checkin(changed=("custom_is_approved",), ignore_permissions=True, custom_is_approved=1)
		)
		check.assert_not_called()


class TestShiftRequestSetting(TestCase):
	def _submit(self, setting):
		doc = SimpleNamespace(
			flags=frappe._dict(), employee="EMP-STAFF", from_date="2026-11-05"
		)
		with patch.object(approval_hooks, "_prevent_self_shift_approval", return_value=setting), patch.object(
			approval_hooks, "assert_can_approve"
		) as check:
			approval_hooks.before_submit_shift_request(doc)
		return check.call_args.kwargs["site_allows_self"]

	def test_prevent_on_keeps_self_approval_off(self):
		self.assertFalse(self._submit(True))

	def test_prevent_off_lets_self_approve(self):
		self.assertTrue(self._submit(False))

	def _read(self, rows):
		meta = MagicMock()
		meta.has_field.return_value = True
		with patch("frappe.get_meta", return_value=meta), patch("frappe.db.sql", return_value=rows):
			return approval_hooks._prevent_self_shift_approval()

	def test_never_saved_setting_reads_as_on(self):
		self.assertTrue(self._read(()))

	def test_saved_setting_is_read(self):
		self.assertFalse(self._read((("0",),)))
		self.assertTrue(self._read((("1",),)))


class TestLeaveSettingMirror(TestCase):
	def test_hr_settings_change_is_mirrored(self):
		meta = MagicMock()
		meta.has_field.return_value = True
		with patch("frappe.get_meta", return_value=meta), patch("frappe.db.set_single_value") as write:
			approval_hooks.sync_self_leave_approval_from_hr_settings(
				frappe._dict(prevent_self_leave_approval=0)
			)
		write.assert_called_once_with(
			"Nepal HRMS Settings", approval_hooks.LEAVE_SELF_APPROVAL_FIELD, 0
		)
