from unittest import TestCase
from unittest.mock import patch

from frappe import _dict

from nepal_hrms.custom_code.payroll import journal_access as ja

PAYROLL_JE = _dict(
	name="JV-1",
	accounts=[
		_dict(account="Wages", reference_type=None),
		_dict(account="Payroll Payable", reference_type="Payroll Entry", reference_name="PE-1"),
	],
)
OTHER_JE = _dict(name="JV-2", accounts=[_dict(account="Rent", reference_type="Purchase Invoice")])


def roles(*names):
	return patch.object(ja.frappe, "get_roles", return_value=list(names))


class TestPayrollJournalAccess(TestCase):
	def test_payroll_journal_is_recognised_by_its_reference(self):
		self.assertTrue(ja.is_payroll_journal(PAYROLL_JE))
		self.assertFalse(ja.is_payroll_journal(OTHER_JE))

	def test_accountant_without_the_role_is_refused_payroll_only(self):
		with roles("Accounts User", "HR Manager", "System Manager"):
			self.assertIs(ja.has_permission(PAYROLL_JE, "read", "acct@example.com"), False)
			# Anything else is left to the normal role permissions.
			self.assertIsNone(ja.has_permission(OTHER_JE, "read", "acct@example.com"))
			condition = ja.get_permission_query_conditions("acct@example.com")
		self.assertIn("not exists", condition)
		self.assertIn("'Payroll Entry'", condition)

	def test_role_holder_and_administrator_see_everything(self):
		with roles("Accounts User", ja.PAYROLL_JOURNAL_ROLE):
			self.assertIsNone(ja.has_permission(PAYROLL_JE, "read", "payroll@example.com"))
			self.assertEqual(ja.get_permission_query_conditions("payroll@example.com"), "")
		with roles():
			self.assertIsNone(ja.has_permission(PAYROLL_JE, "read", "Administrator"))
			self.assertEqual(ja.get_permission_query_conditions("Administrator"), "")
