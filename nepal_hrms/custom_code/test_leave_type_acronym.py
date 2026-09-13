# Copyright (c) 2026, Yarsa Labs Pvt. Ltd.
from unittest import TestCase

from nepal_hrms.custom_code.leave_type_acronym import leave_type_acronym


class TestLeaveTypeAcronym(TestCase):
	def test_canonical_mappings(self):
		self.assertEqual(leave_type_acronym("Leave Without Pay"), "LWP")
		self.assertEqual(leave_type_acronym("Sick Leave"), "SL")
		self.assertEqual(leave_type_acronym("Annual/Home Leave"), "AHL")

	def test_initials_fallback(self):
		self.assertEqual(leave_type_acronym("Casual Leave"), "CL")

	def test_empty(self):
		self.assertEqual(leave_type_acronym(""), "Lv")
		self.assertEqual(leave_type_acronym(None), "Lv")
