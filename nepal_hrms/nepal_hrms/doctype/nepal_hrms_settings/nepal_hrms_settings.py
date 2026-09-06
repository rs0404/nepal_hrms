# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

# Account shape each scheduled-run field needs, mirroring stock Payroll Entry's
# own link filters. Anything the grid lets through must still satisfy these.
SCHEDULED_ACCOUNT_RULES = {
	"payroll_payable_account": {"label": "Payroll Payable A/C", "root_type": "Liability"},
	"payment_account": {"label": "Payment Account", "account_type": ("Bank", "Cash")},
}


class NepalHRMSSettings(Document):
	def validate(self):
		self.validate_payroll_period_start_day()
		self.validate_period_leave_gross_lwp()
		self.validate_payroll_accounts()
		self.validate_scheduled_payroll_runs()

	def validate_period_leave_gross_lwp(self):
		if not cint(self.enable_period_leave_gross_lwp):
			return
		threshold = cint(self.period_leave_gross_lwp_threshold)
		if threshold < 1:
			frappe.throw(
				_("Period Leave Threshold Days must be at least 1."),
				title=_("Invalid Period Leave Threshold"),
			)
		self.period_leave_gross_lwp_threshold = threshold

	def validate_payroll_period_start_day(self):
		"""Custom ranges open on a day that exists in every BS month (1–29)."""
		if self.payroll_period_basis != "Custom Day Range":
			return
		day = cint(self.payroll_period_start_day)
		if day < 1 or day > 29:
			frappe.throw(
				_("Period Start Day (BS) must be between 1 and 29."),
				title=_("Invalid Period Start Day"),
			)
		self.payroll_period_start_day = day

	def validate_payroll_accounts(self):
		"""Keep each mapping row's account inside its own company.

		The grid filters the account list by company, but that guard is client-side
		only: rows written through the API, or rows whose company was edited after
		the account was picked, can still hold a foreign account. Setup copies these
		straight onto Salary Component, where a cross-company account posts the
		expense against the wrong books.
		"""
		for row in self.get("payroll_accounts") or []:
			if not (row.company and row.account):
				continue

			details = self._account_details(row.account)
			if not details:
				continue

			self._assert_company(row, "Component Account Mapping", "Account", row.account, details.company)

			if details.is_group:
				frappe.throw(
					_("Component Account Mapping row #{0}: {1} is a group account and cannot take entries.").format(
						row.idx, frappe.bold(row.account)
					),
					title=_("Group Account"),
				)

	def validate_scheduled_payroll_runs(self):
		"""Hold scheduled rows to the same rules a manual Payroll Entry enforces.

		These rows drive unattended document creation, so a bad reference surfaces
		as a failed background job rather than a form error someone can act on.
		Catching it at save is the only point where the person who made the mistake
		is still looking at it.
		"""
		for row in self.get("scheduled_payroll_runs") or []:
			if not row.company:
				continue

			if row.salary_structure:
				structure_company = frappe.db.get_value("Salary Structure", row.salary_structure, "company")
				if structure_company:
					self._assert_company(
						row, "Scheduled Runs", "Salary Structure", row.salary_structure, structure_company
					)

			if row.cost_center:
				cc_company = frappe.db.get_value("Cost Center", row.cost_center, "company")
				if cc_company:
					self._assert_company(row, "Scheduled Runs", "Cost Center", row.cost_center, cc_company)

			for fieldname, rule in SCHEDULED_ACCOUNT_RULES.items():
				account = row.get(fieldname)
				if not account:
					continue

				details = self._account_details(account)
				if not details:
					continue

				self._assert_company(row, "Scheduled Runs", rule["label"], account, details.company)

				if details.is_group:
					frappe.throw(
						_("Scheduled Runs row #{0}: {1} is a group account and cannot take entries.").format(
							row.idx, frappe.bold(account)
						),
						title=_("Group Account"),
					)

				if rule.get("root_type") and details.root_type != rule["root_type"]:
					frappe.throw(
						_("Scheduled Runs row #{0}: {1} must be a {2} account, but {3} is {4}.").format(
							row.idx,
							_(rule["label"]),
							_(rule["root_type"]),
							frappe.bold(account),
							_(details.root_type or "unclassified"),
						),
						title=_("Wrong Account Type"),
					)

				if rule.get("account_type") and details.account_type not in rule["account_type"]:
					frappe.throw(
						_("Scheduled Runs row #{0}: {1} must be a Bank or Cash account, but {2} is {3}.").format(
							row.idx,
							_(rule["label"]),
							frappe.bold(account),
							_(details.account_type or "unclassified"),
						),
						title=_("Wrong Account Type"),
					)

	@staticmethod
	def _account_details(account):
		return frappe.db.get_value(
			"Account", account, ["company", "is_group", "root_type", "account_type"], as_dict=True
		)

	@staticmethod
	def _assert_company(row, table, label, value, owner_company):
		if owner_company == row.company:
			return

		frappe.throw(
			_("{0} row #{1}: {2} {3} belongs to {4}, not {5}.").format(
				_(table),
				row.idx,
				_(label),
				frappe.bold(value),
				frappe.bold(owner_company),
				frappe.bold(row.company),
			),
			title=_("Company Mismatch"),
		)
