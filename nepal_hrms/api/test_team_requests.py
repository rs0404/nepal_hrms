"""Team approvals happen in two steps, and the queue keeps a decided draft.

Approve used to leave a request as an "Approved" draft that nobody below HR
could submit; the list counted it as approved and dropped it from the queue,
so no attendance was ever created.
"""

from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.api import team_requests as tr


class _Doc(frappe._dict):
	def __init__(self, **kw):
		super().__init__({"doctype": "Leave Application", "employee": "EMP-1", "docstatus": 0, "status": "Open", **kw})
		self.flags = frappe._dict()
		self.meta = type("M", (), {"has_field": staticmethod(lambda f: False)})()
		self.saved = self.submitted = False
		self.comments = []

	def save(self):
		self.saved = True

	def submit(self):
		self.submitted = True
		self.docstatus = 1

	def add_comment(self, _type, text):
		self.comments.append(text)


def _run(fn, doc, *args, allowed=True):
	with patch.object(tr.frappe, "get_doc", return_value=doc), patch.object(
		tr, "_can_decide", return_value=allowed
	):
		return fn(doc.doctype, "X", *args)


class TestDecide(TestCase):
	def test_approve_sets_status_without_submitting(self):
		doc = _Doc()
		result = _run(tr.decide_team_request, doc, "Approved")
		self.assertEqual((doc.status, doc.saved, doc.submitted), ("Approved", True, False))
		self.assertTrue(result["awaiting_submit"])

	def test_reject_needs_a_reason(self):
		with self.assertRaises(frappe.ValidationError):
			_run(tr.decide_team_request, _Doc(), "Rejected", "  ")

	def test_reason_lands_as_a_comment_without_the_field(self):
		doc = _Doc()
		_run(tr.decide_team_request, doc, "Rejected", "Not on duty")
		self.assertEqual(doc.comments, ["Rejected: Not on duty"])

	def test_a_wrong_tap_can_be_changed_before_submit(self):
		doc = _Doc(status="Approved")
		_run(tr.decide_team_request, doc, "Rejected", "Wrong day")
		self.assertEqual(doc.status, "Rejected")

	def test_rejected_attendance_request_is_final(self):
		doc = _Doc(doctype="Attendance Request")
		result = _run(tr.decide_team_request, doc, "Rejected", "Already present")
		self.assertFalse(result["awaiting_submit"])

	def test_outside_the_chain_is_refused(self):
		with self.assertRaises(frappe.PermissionError):
			_run(tr.decide_team_request, _Doc(), "Approved", allowed=False)


class TestSubmit(TestCase):
	def test_undecided_cannot_be_submitted(self):
		with self.assertRaises(frappe.ValidationError):
			_run(tr.submit_team_request, _Doc())

	def test_decided_is_submitted(self):
		doc = _Doc(status="Approved")
		_run(tr.submit_team_request, doc)
		self.assertTrue(doc.submitted)

	def test_rejected_attendance_request_is_never_submitted(self):
		with self.assertRaises(frappe.ValidationError):
			_run(tr.submit_team_request, _Doc(doctype="Attendance Request", status="Rejected"))

	def test_outside_the_chain_is_refused_before_anything_else(self):
		with self.assertRaises(frappe.PermissionError):
			_run(tr.submit_team_request, _Doc(), allowed=False)

	def test_unknown_doctype_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			tr.submit_team_request("Expense Claim", "X")
