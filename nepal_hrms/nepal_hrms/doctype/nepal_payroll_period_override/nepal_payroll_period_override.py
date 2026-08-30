# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Per-period day-count override, e.g. treating Shrawan as 32 days instead of 31.

Restricted to HR Manager by DocType permissions. `applies_from` plus the divisor
snapshot written onto each Salary Slip keep historical pay from being restated.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate


class NepalPayrollPeriodOverride(Document):
	def validate(self):
		self._resolve_dates()
		self._validate_override()
		self._validate_unique()

	def _resolve_dates(self):
		from nepal_hrms.custom_code.payroll.period import resolve_bs_period

		month = cint(str(self.bs_month).split(" - ")[0])
		start, end, days = resolve_bs_period(cint(self.bs_year), month)
		if not start:
			frappe.throw(_("Could not resolve BS {0}-{1} to calendar dates.").format(self.bs_year, month))
		self.from_date, self.to_date, self.natural_days = start, end, days

	def _validate_override(self):
		if cint(self.total_days_override) < 1:
			frappe.throw(_("Use This Many Days must be at least 1."))
		if cint(self.total_days_override) > 40:
			frappe.throw(_("Use This Many Days looks wrong ({0}).").format(self.total_days_override))
		if not self.applies_from:
			self.applies_from = frappe.utils.today()

	def _validate_unique(self):
		clash = frappe.db.exists(
			"Nepal Payroll Period Override",
			{
				"name": ("!=", self.name or ""),
				"bs_year": self.bs_year,
				"bs_month": self.bs_month,
				"company": self.company or "",
			},
		)
		if clash:
			frappe.throw(
				_("An override already exists for this period and company: {0}").format(clash)
			)

	def on_update(self):
		self.add_comment(
			"Comment",
			_("Period day count set to {0} (actual {1}), applying to salary slips created from {2}. Reason: {3}").format(
				self.total_days_override, self.natural_days, getdate(self.applies_from), self.reason
			),
		)
