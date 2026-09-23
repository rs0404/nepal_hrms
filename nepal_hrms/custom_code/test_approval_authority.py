"""Only the approver chain decides; HR roles grant nothing; self needs an escape."""

from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.custom_code import approval_authority as aa

# employee -> (user_id, reports_to)
ORG = {
	"EMP-STAFF": ("staff@x.com", "EMP-LEAD"),
	"EMP-LEAD": ("lead@x.com", "EMP-HEAD"),
	"EMP-HEAD": ("head@x.com", None),
	"EMP-HR": ("hr@x.com", None),
}


def _fake_get_value(doctype, filters, fieldname=None, as_dict=False, **_kwargs):
	if isinstance(filters, dict):  # {"user_id": ..., "status": "Active"}
		name = next((n for n, (u, _) in ORG.items() if u == filters.get("user_id")), None)
		if not name:
			return None
		return frappe._dict(name=name, reports_to=ORG[name][1])
	user_id, reports_to = ORG[filters]
	return {"user_id": user_id, "reports_to": reports_to}[fieldname]


class TestApprovalAuthority(TestCase):
	def setUp(self):
		patcher = patch.object(aa.frappe.db, "get_value", side_effect=_fake_get_value, create=True)
		self.addCleanup(patcher.stop)
		patcher.start()
		approver = patch.object(aa, "designated_approver", return_value="lead@x.com")
		self.addCleanup(approver.stop)
		approver.start()
		# No one holds Allow Approving Everyone unless a test says so.
		everyone = patch.object(aa, "approves_everyone", return_value=False)
		self.addCleanup(everyone.stop)
		everyone.start()

	def test_chain_climbs_reports_to_from_the_approver(self):
		self.assertEqual(aa.approver_chain("lead@x.com"), ["lead@x.com", "head@x.com"])

	def test_the_approver_and_their_manager_may_approve(self):
		self.assertTrue(aa.can_approve("EMP-STAFF", user="lead@x.com"))
		self.assertTrue(aa.can_approve("EMP-STAFF", user="head@x.com"))

	def test_an_hr_user_outside_the_chain_may_not(self):
		self.assertFalse(aa.can_approve("EMP-STAFF", user="hr@x.com"))

	def test_self_needs_an_escape(self):
		with patch.object(aa, "self_approval_allowed", return_value=False):
			self.assertFalse(aa.can_approve("EMP-STAFF", user="staff@x.com"))
		with patch.object(aa, "self_approval_allowed", return_value=True):
			self.assertTrue(aa.can_approve("EMP-STAFF", user="staff@x.com"))

	def test_being_your_own_approver_is_still_self_approval(self):
		with patch.object(aa, "self_approval_allowed", return_value=False):
			self.assertFalse(aa.can_approve("EMP-LEAD", user="lead@x.com"))

	def test_an_approve_everyone_escape_lets_an_outsider_approve(self):
		with patch.object(aa, "approves_everyone", return_value=True):
			self.assertTrue(aa.can_approve("EMP-STAFF", user="hr@x.com"))

	def test_approve_everyone_does_not_cover_your_own(self):
		with patch.object(aa, "approves_everyone", return_value=True), patch.object(
			aa, "self_approval_allowed", return_value=False
		):
			self.assertFalse(aa.can_approve("EMP-STAFF", user="staff@x.com"))

	def test_administrator_always_may(self):
		self.assertTrue(aa.can_approve("EMP-STAFF", user="Administrator"))

	def test_a_reports_to_loop_ends(self):
		looped = dict(ORG, **{"EMP-HEAD": ("head@x.com", "EMP-LEAD")})
		with patch.dict(ORG, looped):
			self.assertEqual(aa.approver_chain("lead@x.com"), ["lead@x.com", "head@x.com"])


class TestApproveEveryoneGrant(TestCase):
	"""Only a System Manager may give, move or extend Allow Approving Everyone."""

	def _escape(self, before=None, **values):
		doc = frappe.get_doc(
			dict(
				{"doctype": "Attendance Policy Escape", "employee": "EMP-HR", "is_active": 1},
				**values,
			)
		)
		doc.is_new = lambda: before is None
		doc.get_doc_before_save = lambda: before
		return doc

	def _check(self, doc, roles):
		with patch("frappe.get_roles", return_value=roles):
			doc._validate_approve_all_grant()

	def test_hr_manager_cannot_grant_it(self):
		with self.assertRaises(frappe.PermissionError):
			self._check(self._escape(allow_approve_all=1), ["HR Manager"])

	def test_system_manager_can_grant_it(self):
		self._check(self._escape(allow_approve_all=1), ["System Manager"])

	def test_hr_manager_cannot_move_a_grant_to_someone_else(self):
		before = frappe._dict(allow_approve_all=1, employee="EMP-HEAD", is_active=1)
		with self.assertRaises(frappe.PermissionError):
			self._check(self._escape(before, allow_approve_all=1), ["HR Manager"])

	def test_hr_manager_may_edit_a_row_without_the_grant(self):
		before = frappe._dict(allow_approve_all=0, employee="EMP-HR", is_active=1, escape_sandwich=1)
		self._check(self._escape(before, escape_sandwich=0, escape_late_early=1), ["HR Manager"])

	def test_hr_manager_may_edit_the_reason_on_a_grant(self):
		before = frappe._dict(allow_approve_all=1, employee="EMP-HR", is_active=1, reason="old")
		self._check(self._escape(before, allow_approve_all=1, reason="new"), ["HR Manager"])
