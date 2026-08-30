# -*- coding: utf-8 -*-
# Copyright (c) 2026, Yarsa and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from nepal_hrms.custom_code.application_hooks import (
	before_submit_cnr_application,
	on_cancel_ooo_application,
	on_submit_ooo_application,
	validate_ooo_application,
)


class OutofOfficeApplication(Document):
	def validate(self):
		validate_ooo_application(self)

	def before_submit(self):
		before_submit_cnr_application(self)

	def on_submit(self):
		on_submit_ooo_application(self)

	def on_cancel(self):
		on_cancel_ooo_application(self)
