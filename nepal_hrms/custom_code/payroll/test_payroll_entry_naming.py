from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.custom_code.payroll.payroll_entry_naming import next_free_name, payroll_entry_title


def bs(year, month, day):
	return {"year": year, "month": month, "day": day}


class TestTitles(TestCase):
	def test_each_frequency_reads_as_its_period(self):
		cases = [
			("Monthly", bs(2083, 4, 1), bs(2083, 4, 28), None, "Shrawan 2083 Monthly"),
			("Monthly", bs(2083, 5, 29), bs(2083, 6, 28), "Wages", "Ashwin 2083 Monthly Wages"),
			("Bimonthly", bs(2083, 4, 1), bs(2083, 5, 31), None, "Shrawan-Bhadra 2083 Bimonthly"),
			("Bimonthly", bs(2083, 12, 1), bs(2084, 1, 31), None, "Chaitra 2083-Baisakh 2084 Bimonthly"),
			("Weekly", bs(2083, 4, 1), bs(2083, 4, 7), None, "Shrawan 1-7 2083 Weekly"),
			("Fortnightly", bs(2083, 4, 29), bs(2083, 5, 12), "Salary", "Shrawan 29-Bhadra 12 2083 Fortnightly Salary"),
			("Weekly", bs(2083, 12, 28), bs(2084, 1, 3), None, "Chaitra 28 2083-Baisakh 3 2084 Weekly"),
			("Daily", bs(2083, 4, 5), bs(2083, 4, 5), None, "Shrawan 5 2083 Daily"),
			("", bs(2083, 4, 1), bs(2083, 4, 28), None, "Shrawan 2083 Monthly"),
		]
		for frequency, start, end, variant, expected in cases:
			self.assertEqual(payroll_entry_title(frequency, start, end, variant), expected)

	def test_repeats_get_a_number(self):
		taken = {"Shrawan 2083 Monthly", "Shrawan 2083 Monthly-1", "Shrawan 2083 Monthly-2"}
		self.assertEqual(next_free_name("Bhadra 2083 Monthly", taken.__contains__), "Bhadra 2083 Monthly")
		# "-1" is an amendment's suffix; the next run is -3 here.
		self.assertEqual(next_free_name("Shrawan 2083 Monthly", taken.__contains__), "Shrawan 2083 Monthly-3")


class TestRealPeriods(TestCase):
	"""Through Frappe's own naming, with this company's BS-aligned periods."""

	def name_for(self, start, end, frequency="Monthly", structure=None):
		from frappe.model.naming import set_new_name

		doc = frappe.new_doc("Payroll Entry")
		doc.update({"start_date": start, "end_date": end, "payroll_frequency": frequency})
		if structure and doc.meta.has_field("custom_salary_structure"):
			doc.custom_salary_structure = structure
		with patch("frappe.db.exists", return_value=False):
			set_new_name(doc)
		return doc.name

	def test_months_by_their_end(self):
		self.assertEqual(self.name_for("2026-07-17", "2026-08-13"), "Shrawan 2083 Monthly")
		self.assertEqual(self.name_for("2026-08-14", "2026-09-13"), "Bhadra 2083 Monthly")
		self.assertEqual(self.name_for("2026-09-14", "2026-10-14"), "Ashwin 2083 Monthly")

	def test_structure_variant_is_named(self):
		self.assertEqual(
			self.name_for("2026-07-17", "2026-08-13", structure="Nepal Payroll - SSF - Wages - Yarsa Tech Pvt. Ltd."),
			"Shrawan 2083 Monthly Wages",
		)
