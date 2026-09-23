"""The seeded exemption limits must be ones Frappe HR will accept."""

from unittest import TestCase

from nepal_hrms.custom_code.payroll.tax_exemption import TAX_EXEMPTION_CATEGORIES


class TestTaxExemptionCategories(TestCase):
	def test_no_sub_category_exceeds_its_category(self):
		for category, (category_max, subs) in TAX_EXEMPTION_CATEGORIES.items():
			for sub, sub_max in subs:
				self.assertLessEqual(sub_max, category_max, f"{sub} exceeds {category}")

	def test_sub_category_names_are_unique(self):
		names = [sub for _, subs in TAX_EXEMPTION_CATEGORIES.values() for sub, _ in subs]
		self.assertEqual(len(names), len(set(names)))

	def test_fy_2083_84_limits(self):
		limits = {category: limit for category, (limit, _) in TAX_EXEMPTION_CATEGORIES.items()}
		self.assertEqual(limits["Life Insurance"], 40000)
		self.assertEqual(limits["Health Insurance"], 20000)
		self.assertEqual(limits["Private Building Insurance"], 10000)
		self.assertEqual(limits["Children's Education Fee"], 25000)
		self.assertEqual(limits["Donation"], 300000)
		self.assertNotIn("Remote Area Allowance", limits)
