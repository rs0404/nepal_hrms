# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Employee Attendance Policy Escape resolver (request-cached)."""

import frappe
from frappe.utils import cint, getdate, today

ESCAPE_FLAGS = (
	"escape_sandwich",
	"escape_late_early",
	"escape_continuous_lwp_gross",
	"escape_absent_gross",
	"escape_applications",
	"escape_attendance_deduction",
	"allow_self_approval",
	"allow_approve_all",
)


def _empty_flags():
	return frappe._dict({f: 0 for f in ESCAPE_FLAGS})


def _table_columns():
	"""Columns on the escape table, or none if it cannot be read.

	Split out so the degraded path can be tested without a site: frappe.db is an
	unbound proxy until one is connected.
	"""
	try:
		return set(frappe.db.get_table_columns("Attendance Policy Escape"))
	except Exception:
		return set()


def queryable_flags():
	"""The escape flags that actually exist as columns on this site.

	New code can reach a site whose table has not been synced yet. Selecting a
	column that is not there throws, and this resolver sits on the path of every
	attendance save and every salary slip -- so a missing flag reads as 0 rather
	than stopping payroll. The set is fixed for the life of a request.
	"""
	cached = getattr(frappe.local, "_nepal_policy_escape_columns", None)
	if cached is not None:
		return cached

	# Hoisted: inside the generator this would re-read the schema once per flag.
	columns = _table_columns()
	flags = tuple(f for f in ESCAPE_FLAGS if f in columns)
	frappe.local._nepal_policy_escape_columns = flags
	return flags


def clear_policy_escape_cache(employee=None):
	# A sync during a long-running process (bench console, a worker mid-deploy)
	# can add the column under us; forget what we knew about the schema too.
	# Above the early return: the schema can go stale while the flag cache is empty.
	frappe.local._nepal_policy_escape_columns = None

	cache = getattr(frappe.local, "_nepal_policy_escapes", None)
	if not cache:
		return
	if employee:
		# Drop all date-keyed entries for this employee
		prefix = f"{employee}::"
		for key in list(cache.keys()):
			if key.startswith(prefix) or key == employee:
				cache.pop(key, None)
	else:
		frappe.local._nepal_policy_escapes = {}


def _covers_date(from_date, to_date, on_date):
	on_date = getdate(on_date)
	if from_date and getdate(from_date) > on_date:
		return False
	if to_date and getdate(to_date) < on_date:
		return False
	return True


def _overlaps_period(from_date, to_date, start_date, end_date):
	start_date = getdate(start_date)
	end_date = getdate(end_date)
	if from_date and getdate(from_date) > end_date:
		return False
	if to_date and getdate(to_date) < start_date:
		return False
	return True


def get_policy_escapes(employee, on_date=None):
	"""
	Return OR-merged escape flags for employee on a date.
	Cached on frappe.local for the request.
	"""
	if not employee:
		return _empty_flags()

	on_date = getdate(on_date or today())
	cache_key = f"{employee}::{on_date}"
	cache = getattr(frappe.local, "_nepal_policy_escapes", None)
	if cache is None:
		cache = {}
		frappe.local._nepal_policy_escapes = cache
	if cache_key in cache:
		return cache[cache_key]

	flags = _empty_flags()
	if not frappe.db.exists("DocType", "Attendance Policy Escape"):
		cache[cache_key] = flags
		return flags

	flag_columns = queryable_flags()
	if not flag_columns:
		cache[cache_key] = flags
		return flags

	rows = frappe.get_all(
		"Attendance Policy Escape",
		filters={"employee": employee, "is_active": 1},
		fields=["from_date", "to_date"] + list(flag_columns),
	)
	for row in rows:
		if not _covers_date(row.from_date, row.to_date, on_date):
			continue
		for f in flag_columns:
			if cint(row.get(f)):
				flags[f] = 1

	cache[cache_key] = flags
	return flags


def get_policy_escapes_for_period(employee, start_date, end_date):
	"""OR-merge escape flags across any active row overlapping [start_date, end_date]."""
	if not employee:
		return _empty_flags()

	start_date = getdate(start_date)
	end_date = getdate(end_date)
	cache_key = f"{employee}::{start_date}..{end_date}"
	cache = getattr(frappe.local, "_nepal_policy_escapes", None)
	if cache is None:
		cache = {}
		frappe.local._nepal_policy_escapes = cache
	if cache_key in cache:
		return cache[cache_key]

	flags = _empty_flags()
	if not frappe.db.exists("DocType", "Attendance Policy Escape"):
		cache[cache_key] = flags
		return flags

	flag_columns = queryable_flags()
	if not flag_columns:
		cache[cache_key] = flags
		return flags

	rows = frappe.get_all(
		"Attendance Policy Escape",
		filters={"employee": employee, "is_active": 1},
		fields=["from_date", "to_date"] + list(flag_columns),
	)
	for row in rows:
		if not _overlaps_period(row.from_date, row.to_date, start_date, end_date):
			continue
		for f in flag_columns:
			if cint(row.get(f)):
				flags[f] = 1

	cache[cache_key] = flags
	return flags


def has_policy_escape(employee, flag, on_date=None):
	return cint(get_policy_escapes(employee, on_date).get(flag))
