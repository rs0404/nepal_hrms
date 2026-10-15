from unittest import TestCase

import frappe
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip

from nepal_hrms.overrides.salary_slip import CustomSalarySlip


class TestWhitelistedOverrides(TestCase):
	def test_overrides_keep_the_whitelist(self):
		# Redefining a whitelisted HRMS method drops its decorator, and the form's
		# calls to it (set_totals on every row edit) start failing as not permitted.
		missing = [
			name
			for name, fn in vars(CustomSalarySlip).items()
			if callable(fn)
			and getattr(SalarySlip, name, None) in frappe.whitelisted
			and fn not in frappe.whitelisted
		]
		self.assertEqual(missing, [])
