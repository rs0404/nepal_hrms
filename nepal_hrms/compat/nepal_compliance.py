# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Neutralise nepal_compliance's duplicate payroll hooks from inside nepal_hrms.

Both apps register a `Salary Slip: after_insert` handler, and the two modules are
identical bar the import line. Because hooks of that kind are *merged* rather than
overridden, both fire: every slip is saved twice and nepal_compliance -- which is
installed earlier, so runs first -- wins the tax-row append with its own hardcoded
component list.

`override_doctype_class` is different: frappe takes `class_overrides[doctype][-1]`,
so the last-installed app wins outright and nepal_hrms's payroll classes are already
in force. Only the merged hooks need this shim.

Every step degrades to a no-op: nepal_compliance absent, module renamed, function
gone, or already patched. Nothing here raises.

Written against nepal_compliance @ fix/vat (4b896dc). Re-check on upgrade.
"""

import frappe

_PATCH_FLAG = "_nepal_hrms_neutralised"


def _no_op(*args, **kwargs):
	return None


def _neutralise(module_path: str, attribute: str) -> bool:
	"""Replace one nepal_compliance callable with a no-op. Returns True if patched."""
	try:
		import importlib

		module = importlib.import_module(module_path)
	except Exception:
		# App not installed, or the module was moved/removed in this version.
		return False

	if not hasattr(module, attribute):
		# This version of nepal_compliance does not ship that function.
		return False

	if getattr(module, _PATCH_FLAG, None) == attribute:
		return False  # already done in this process

	try:
		setattr(module, attribute, _no_op)
		setattr(module, _PATCH_FLAG, attribute)
		return True
	except Exception:
		frappe.log_error(
			frappe.get_traceback(), f"Could not neutralise {module_path}.{attribute}"
		)
		return False


# (module, attribute, why)
_TARGETS = (
	(
		"nepal_compliance.patches.payroll_entry",
		"execute",
		"duplicate Salary Slip after_insert; nepal_hrms computes taxable_salary itself",
	),
	(
		"nepal_compliance.custom_code.leave_allocation.scheduled_tasks",
		"run_daily_bs_tasks",
		"duplicate daily BS leave allocation; nepal_hrms owns the watermark",
	),
)


def apply():
	"""Idempotent, safe to call on every request / job."""
	if getattr(frappe.local, "_nepal_hrms_compat_applied", False):
		return
	frappe.local._nepal_hrms_compat_applied = True

	for module_path, attribute, _why in _TARGETS:
		_neutralise(module_path, attribute)


def status():
	"""Report what is patched -- for troubleshooting, not used at runtime."""
	import importlib

	out = []
	for module_path, attribute, why in _TARGETS:
		try:
			module = importlib.import_module(module_path)
		except Exception:
			out.append({"target": f"{module_path}.{attribute}", "state": "absent", "why": why})
			continue
		if not hasattr(module, attribute):
			state = "not in this version"
		elif getattr(module, _PATCH_FLAG, None) == attribute:
			state = "neutralised"
		else:
			state = "ACTIVE - duplicate will run"
		out.append({"target": f"{module_path}.{attribute}", "state": state, "why": why})
	return out
