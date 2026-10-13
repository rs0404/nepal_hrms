"""Errors the employee app shows reach Error Log; Desk and expired sessions do not."""

import json
from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.api import error_capture as ec


class _Request:
	def __init__(self, referer="https://site/hr/home", path="/api/method/x"):
		self.path = path
		self.headers = {"Referer": referer, "User-Agent": "test"}


class _Response:
	def __init__(self, status):
		self.status_code = status


class TestLogAppErrors(TestCase):
	def _log(self, status=417, referer="https://site/hr/home", form=None, messages=None, exc_type="ValidationError"):
		form = frappe._dict(form or {"cmd": "nepal_hrms.api.x", "doctype": "Leave Application", "name": "LA-1"})
		with patch.object(frappe, "local", frappe._dict(
			form_dict=form,
			message_log=messages if messages is not None else [json.dumps({"message": "<b>Not</b> permitted"})],
			response=frappe._dict(exc_type=exc_type),
			flags=frappe._dict(),
		)), patch.object(frappe, "session", frappe._dict(user="a@b.c")), patch.object(
			ec, "_from_app", side_effect=lambda r: "/hr/" in r.headers["Referer"]
		), patch.object(ec.frappe, "log_error") as log_error:
			ec.log_app_errors(_Response(status), _Request(referer))
		return log_error

	def test_validation_error_from_the_app_is_logged(self):
		log_error = self._log()
		log_error.assert_called_once()
		kwargs = log_error.call_args.kwargs
		self.assertEqual(kwargs["title"], "App: Not permitted")
		self.assertEqual((kwargs["reference_doctype"], kwargs["reference_name"]), ("Leave Application", "LA-1"))
		self.assertTrue(kwargs["defer_insert"])
		details = json.loads(kwargs["message"])
		self.assertEqual(details["shown_to_user"], ["Not permitted"])
		self.assertEqual(details["method"], "nepal_hrms.api.x")

	def test_desk_errors_are_not_logged(self):
		self._log(referer="https://site/app/leave-application/LA-1").assert_not_called()

	def test_crashes_are_left_to_frappe(self):
		self._log(status=500).assert_not_called()

	def test_expired_session_is_not_logged(self):
		self._log(status=401).assert_not_called()
		self._log(exc_type="CSRFTokenError", status=400).assert_not_called()

	def test_success_is_not_logged(self):
		self._log(status=200).assert_not_called()

	def test_secrets_are_masked_and_long_args_cut(self):
		args = ec._clean_args({"cmd": "x", "new_password": "hunter2", "doc": "x" * 5000})
		self.assertEqual(args["new_password"], "***")
		self.assertNotIn("cmd", args)
		self.assertLess(len(args["doc"]), 2100)

	def test_its_own_rate_limit_is_not_logged(self):
		self._log(status=429, form={"cmd": "nepal_hrms.api.error_capture.log_client_error"}).assert_not_called()
