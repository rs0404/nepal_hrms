from unittest import TestCase

from nepal_hrms.custom_code.payroll.excel_formula import Untranslatable, names_in, to_excel

CELLS = {"base": "B7", "basic_salary": "C7", "revised_salary": "D7", "ctc": "E7", "grade_level": "F7"}


def resolve(name):
	if name not in CELLS:
		raise Untranslatable(name)
	return CELLS[name]


def xl(expr):
	return to_excel(expr, resolve)


class TestToExcel(TestCase):
	def test_arithmetic_keeps_python_precedence(self):
		self.assertEqual(xl("base * .6"), "(B7*0.6)")
		self.assertEqual(xl("basic_salary/30/2*grade_level"), "(((C7/30)/2)*F7)")
		self.assertEqual(xl("(base + ctc) * 0.11"), "((B7+E7)*0.11)")
		self.assertEqual(xl("-base"), "(-B7)")
		self.assertEqual(xl("base ** 2"), "(B7^2)")

	def test_floor_division_and_modulo(self):
		self.assertEqual(xl("base // 30"), "INT(B7/30)")
		self.assertEqual(xl("base % 30"), "MOD(B7,30)")

	def test_conditional_expression(self):
		self.assertEqual(
			xl("(revised_salary * 0.6) if (revised_salary * 0.6) > 12170 else 12170"),
			"IF((D7*0.6)>12170,(D7*0.6),12170)",
		)
		self.assertEqual(xl("(revised_salary if revised_salary else ctc) - basic_salary"), "(IF(D7,D7,E7)-C7)")

	def test_conditions(self):
		self.assertEqual(xl("base > 0"), "B7>0")
		self.assertEqual(xl("base >= 1 and ctc != 0"), "AND(B7>=1,E7<>0)")
		self.assertEqual(xl("not base or ctc"), "OR(NOT(B7),E7)")
		self.assertEqual(xl("0 < base <= 10"), "AND(0<B7,B7<=10)")

	def test_strings_are_quoted(self):
		self.assertEqual(xl('ctc == "Intern"'), 'E7="Intern"')
		self.assertEqual(xl("ctc == 'say \"hi\"'"), 'E7="say ""hi"""')

	def test_whitelisted_functions(self):
		self.assertEqual(xl("round(base)"), "ROUND(B7,0)")
		self.assertEqual(xl("rounded(base, 2)"), "ROUND(B7,2)")
		self.assertEqual(xl("int(base)"), "TRUNC(B7)")
		self.assertEqual(xl("float(base)"), "B7")
		self.assertEqual(xl("floor(base)"), "INT(B7)")
		self.assertEqual(xl("ceil(base)"), "(-INT(-B7))")
		self.assertEqual(xl("max(base, ctc, 0)"), "MAX(B7,E7,0)")
		self.assertEqual(xl("abs(base)"), "ABS(B7)")

	def test_unknown_name_or_function_is_untranslatable(self):
		with self.assertRaises(Untranslatable):
			xl("missing * 2")
		with self.assertRaises(Untranslatable):
			xl("getdate(base)")
		with self.assertRaises(Untranslatable):
			xl("base.real")
		with self.assertRaises(Untranslatable):
			xl("base +")
		with self.assertRaises(Untranslatable):
			xl("")

	def test_multiline_formula(self):
		self.assertEqual(xl("base\n* 2"), "(B7*2)")


class TestNamesIn(TestCase):
	def test_lists_variables_not_functions(self):
		self.assertEqual(names_in("round(base * x) if y > 0 else max(x, z)"), {"y", "base", "x", "z"})
