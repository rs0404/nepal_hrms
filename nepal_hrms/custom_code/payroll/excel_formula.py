# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Translate a Salary Structure formula or condition into an Excel formula.

HRMS evaluates component formulas as Python expressions over the slip's data
(`base * .6`, `x if cond else y`). The editable payroll workbook writes the same
expressions as Excel formulas so a changed input recalculates the row. Only the
expression forms HRMS formulas actually use are supported; anything else raises
Untranslatable and the caller writes the ERP's value instead.

Pure: no frappe import, unit-tested without a site.
"""

import ast


class Untranslatable(ValueError):
	"""The expression uses something Excel cannot reproduce faithfully."""


_BINARY = {
	ast.Add: "+",
	ast.Sub: "-",
	ast.Mult: "*",
	ast.Div: "/",
	ast.Pow: "^",
}
_COMPARE = {
	ast.Eq: "=",
	ast.NotEq: "<>",
	ast.Lt: "<",
	ast.LtE: "<=",
	ast.Gt: ">",
	ast.GtE: ">=",
}


def names_in(expr):
	"""Every variable name an expression reads."""
	tree = _parse(expr)
	return {
		node.id
		for node in ast.walk(tree)
		if isinstance(node, ast.Name) and not _is_call_target(tree, node)
	}


def to_excel(expr, resolve):
	"""The Excel form of a Python expression, without the leading '='.

	`resolve(name)` returns the cell reference (or literal) for a variable and
	raises Untranslatable for one it cannot place.
	"""
	return _Translator(resolve).visit(_parse(expr).body)


def _parse(expr):
	text = (expr or "").strip().replace("\r", " ").replace("\n", " ")
	if not text:
		raise Untranslatable("empty expression")
	try:
		return ast.parse(text, mode="eval")
	except SyntaxError as e:
		raise Untranslatable(f"syntax error: {e}") from e


def _is_call_target(tree, name_node):
	return any(isinstance(n, ast.Call) and n.func is name_node for n in ast.walk(tree))


class _Translator(ast.NodeVisitor):
	def __init__(self, resolve):
		self.resolve = resolve

	def generic_visit(self, node):
		raise Untranslatable(f"unsupported expression: {type(node).__name__}")

	def visit_Constant(self, node):
		value = node.value
		if isinstance(value, bool):
			return "TRUE" if value else "FALSE"
		if value is None:
			return "0"
		if isinstance(value, (int, float)):
			return repr(value)
		if isinstance(value, str):
			return '"' + value.replace('"', '""') + '"'
		raise Untranslatable(f"unsupported constant {value!r}")

	def visit_Name(self, node):
		return self.resolve(node.id)

	def visit_BinOp(self, node):
		left, right = self.visit(node.left), self.visit(node.right)
		if isinstance(node.op, ast.FloorDiv):
			return f"INT({left}/{right})"
		if isinstance(node.op, ast.Mod):
			return f"MOD({left},{right})"
		op = _BINARY.get(type(node.op))
		if not op:
			raise Untranslatable(f"unsupported operator {type(node.op).__name__}")
		return f"({left}{op}{right})"

	def visit_UnaryOp(self, node):
		operand = self.visit(node.operand)
		if isinstance(node.op, ast.USub):
			return f"(-{operand})"
		if isinstance(node.op, ast.UAdd):
			return operand
		if isinstance(node.op, ast.Not):
			return f"NOT({operand})"
		raise Untranslatable(f"unsupported operator {type(node.op).__name__}")

	def visit_BoolOp(self, node):
		fn = "AND" if isinstance(node.op, ast.And) else "OR"
		return f"{fn}({','.join(self.visit(v) for v in node.values)})"

	def visit_Compare(self, node):
		parts, left = [], self.visit(node.left)
		for op, comparator in zip(node.ops, node.comparators):
			symbol = _COMPARE.get(type(op))
			if not symbol:
				raise Untranslatable(f"unsupported comparison {type(op).__name__}")
			right = self.visit(comparator)
			parts.append(f"{left}{symbol}{right}")
			left = right
		return parts[0] if len(parts) == 1 else f"AND({','.join(parts)})"

	def visit_IfExp(self, node):
		return f"IF({self.visit(node.test)},{self.visit(node.body)},{self.visit(node.orelse)})"

	def visit_Call(self, node):
		if not isinstance(node.func, ast.Name) or node.keywords:
			raise Untranslatable("unsupported call")
		name = node.func.id
		args = [self.visit(a) for a in node.args]
		if name in ("round", "rounded") and len(args) in (1, 2):
			return f"ROUND({args[0]},{args[1] if len(args) == 2 else 0})"
		if len(args) == 1:
			x = args[0]
			if name in ("float", "flt"):
				return x
			if name in ("int", "long", "cint"):
				return f"TRUNC({x})"
			if name == "floor":
				return f"INT({x})"
			if name == "ceil":
				return f"(-INT(-{x}))"
			if name == "abs":
				return f"ABS({x})"
		if name in ("max", "min") and args:
			return f"{name.upper()}({','.join(args)})"
		raise Untranslatable(f"function {name}() has no Excel equivalent here")
