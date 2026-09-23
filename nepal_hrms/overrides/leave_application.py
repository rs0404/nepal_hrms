# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

from hrms.hr.doctype.leave_application.leave_application import LeaveApplication

from nepal_hrms.custom_code.approval_hooks import check_leave_application_approval


class CustomLeaveApplication(LeaveApplication):
	def validate_for_self_approval(self):
		"""Replaces Frappe HR's self-approval check with the approver-chain rule.

		Frappe HR only stops an employee approving their own leave; anyone else
		who can edit it may approve it. Here only the employee's Leave Approver,
		or someone above them in Reports To, may decide it, and the employee
		themself only with an Allow Self-Approval policy escape.
		"""
		check_leave_application_approval(self)

	def before_submit(self):
		parent = getattr(super(), "before_submit", None)
		if parent:
			parent()
		check_leave_application_approval(self, on_submit=True)
