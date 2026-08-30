# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Shift Type override: route auto-attendance through OOO-aware mark_attendance."""

from hrms.hr.doctype.shift_type.shift_type import ShiftType


class NepalShiftType(ShiftType):
	def _process(self, logs):
		"""Use nepal_hrms mark_attendance so unapproved OOO is held for approver."""
		import hrms.hr.doctype.shift_type.shift_type as shift_type_module
		from nepal_hrms.overrides.attendance_override import (
			custom_mark_attendance_and_link_log,
		)

		original = shift_type_module.mark_attendance_and_link_log
		shift_type_module.mark_attendance_and_link_log = custom_mark_attendance_and_link_log
		try:
			return super()._process(logs)
		finally:
			shift_type_module.mark_attendance_and_link_log = original
