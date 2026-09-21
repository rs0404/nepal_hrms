"""The PWA's payslip tab renders the app's own print format."""

from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.api.salary_slip_print import (
	APP_PRINT_FORMAT,
	default_print_format,
	get_salary_slip_html,
)


class TestDefaultPrintFormat(TestCase):
	def test_the_apps_own_format_wins(self):
		with patch(
			"nepal_hrms.api.salary_slip_print.frappe.db.exists", return_value=True
		):
			self.assertEqual(default_print_format(), APP_PRINT_FORMAT)

	def test_it_falls_back_to_the_site_default(self):
		with patch(
			"nepal_hrms.api.salary_slip_print.frappe.db.exists",
			side_effect=[False, True],
		), patch(
			"nepal_hrms.api.salary_slip_print.frappe.db.get_value",
			return_value="Salary Slip Standard",
		):
			self.assertEqual(default_print_format(), "Salary Slip Standard")

	def test_it_falls_back_to_standard_when_nothing_is_configured(self):
		with patch(
			"nepal_hrms.api.salary_slip_print.frappe.db.exists", return_value=False
		), patch(
			"nepal_hrms.api.salary_slip_print.frappe.db.get_value", return_value=None
		):
			self.assertEqual(default_print_format(), "Standard")


class TestGetSalarySlipHtml(TestCase):
	def test_permission_is_checked_against_the_document(self):
		"""An employee sees their own slip, not the whole payroll."""
		with patch(
			"nepal_hrms.api.salary_slip_print.frappe.has_permission"
		) as perm, patch(
			"nepal_hrms.api.salary_slip_print.frappe.get_print", return_value="<html/>"
		), patch(
			"nepal_hrms.api.salary_slip_print.default_print_format", return_value="X"
		):
			get_salary_slip_html("SS-0001")
		self.assertEqual(perm.call_args.args[:2], ("Salary Slip", "read"))
		self.assertEqual(perm.call_args.kwargs["doc"], "SS-0001")
		self.assertTrue(perm.call_args.kwargs["throw"])

	def test_a_missing_name_is_refused(self):
		with patch(
			"nepal_hrms.api.salary_slip_print.frappe.throw",
			side_effect=frappe.ValidationError,
		):
			self.assertRaises(frappe.ValidationError, get_salary_slip_html, "")

	def test_a_broken_format_falls_back_rather_than_leaving_the_tab_empty(self):
		with patch("nepal_hrms.api.salary_slip_print.frappe.has_permission"), patch(
			"nepal_hrms.api.salary_slip_print.default_print_format", return_value="Broken"
		), patch(
			"nepal_hrms.api.salary_slip_print.frappe.get_print",
			side_effect=[Exception("bad template"), "<html>fallback</html>"],
		), patch(
			"nepal_hrms.api.salary_slip_print.frappe.log_error"
		) as log:
			result = get_salary_slip_html("SS-0001")
		self.assertEqual(result["print_format"], "Standard")
		self.assertIn("fallback", result["html"])
		self.assertTrue(log.called)

	def test_an_explicit_format_overrides_the_default(self):
		with patch("nepal_hrms.api.salary_slip_print.frappe.has_permission"), patch(
			"nepal_hrms.api.salary_slip_print.frappe.get_print", return_value="<html/>"
		) as get_print:
			result = get_salary_slip_html("SS-0001", print_format="Salary Slip Yarsa")
		self.assertEqual(result["print_format"], "Salary Slip Yarsa")
		self.assertEqual(get_print.call_args.kwargs["print_format"], "Salary Slip Yarsa")
