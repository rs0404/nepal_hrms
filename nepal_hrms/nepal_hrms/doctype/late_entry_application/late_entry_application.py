# -*- coding: utf-8 -*-
# Copyright (c) 2026, Yarsa and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from nepal_hrms.custom_code.application_hooks import (
	before_submit_cnr_application,
	on_cancel_late_early_application,
	on_submit_late_early_application,
	validate_late_early_application,
)


class LateEntryApplication(Document):
	def validate(self):
		validate_late_early_application(self)

	def before_submit(self):
		before_submit_cnr_application(self)

	def on_submit(self):
		on_submit_late_early_application(self)

	def on_cancel(self):
		on_cancel_late_early_application(self)
