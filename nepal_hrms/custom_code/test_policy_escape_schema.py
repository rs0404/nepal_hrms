"""The resolver must survive new code meeting an un-synced table.

get_policy_escapes() sits on the path of every attendance save and every salary
slip. Selecting a column the site does not have yet throws, so a flag whose
column is missing has to read as 0 instead of stopping payroll.
"""

from unittest import TestCase
from unittest.mock import patch

import frappe

from nepal_hrms.custom_code import policy_escape as pe

OLD = [
	"escape_sandwich",
	"escape_late_early",
	"escape_continuous_lwp_gross",
	"escape_absent_gross",
	"escape_applications",
	"escape_attendance_deduction",
]
NEW = "escape_ssf_earned_scaling"


class _StubDB:
	"""Stands in for what frappe.db proxies; that proxy is unbound without a site."""

	def exists(self, *_args, **_kwargs):
		return True


class _Base(TestCase):
	def setUp(self):
		frappe.local._nepal_policy_escape_columns = None
		frappe.local._nepal_policy_escapes = None
		self._db = getattr(frappe.local, "db", None)
		frappe.local.db = _StubDB()

	def tearDown(self):
		frappe.local.db = self._db

	def rows(self, **values):
		row = frappe._dict({"from_date": None, "to_date": None})
		row.update(values)
		return [row]


class TestQueryableFlags(_Base):
	def test_every_flag_has_a_column(self):
		"""ESCAPE_FLAGS and the doctype must not drift apart."""
		from nepal_hrms.nepal_hrms.doctype.attendance_policy_escape import (
			attendance_policy_escape as doctype_module,
		)

		self.assertEqual(set(pe.ESCAPE_FLAGS), set(doctype_module.ESCAPE_FLAGS))
		self.assertIn(NEW, pe.ESCAPE_FLAGS)

	def test_unsynced_column_is_left_out_of_the_query(self):
		with patch.object(pe, "_table_columns", return_value=set(["name"] + OLD)):
			self.assertEqual(list(pe.queryable_flags()), OLD)

	def test_synced_column_is_queried(self):
		with patch.object(pe, "_table_columns", return_value=set(["name"] + OLD + [NEW])):
			self.assertIn(NEW, pe.queryable_flags())

	def test_unreadable_table_yields_no_flags(self):
		with patch.object(pe, "_table_columns", return_value=set()):
			self.assertEqual(pe.queryable_flags(), ())

	def test_schema_is_read_once_per_request(self):
		"""Read inside the generator, this ran once per flag."""
		with patch.object(pe, "_table_columns", return_value=set(OLD)) as columns:
			pe.queryable_flags()
			pe.queryable_flags()
		self.assertEqual(columns.call_count, 1)

	def test_clearing_the_cache_forgets_the_schema(self):
		"""A sync mid-process must not be masked by a stale column set."""
		with patch.object(pe, "_table_columns", return_value=set(OLD)):
			self.assertNotIn(NEW, pe.queryable_flags())
		pe.clear_policy_escape_cache()
		with patch.object(pe, "_table_columns", return_value=set(OLD + [NEW])):
			self.assertIn(NEW, pe.queryable_flags())

	def test_clearing_forgets_the_schema_even_when_no_flags_were_cached(self):
		"""The early return on an empty flag cache must not skip the schema."""
		frappe.local._nepal_policy_escape_columns = tuple(OLD)
		frappe.local._nepal_policy_escapes = None
		pe.clear_policy_escape_cache()
		self.assertIsNone(frappe.local._nepal_policy_escape_columns)


class TestDegradedResolver(_Base):
	def test_missing_flag_reads_zero_and_the_rest_still_resolve(self):
		with patch.object(pe, "_table_columns", return_value=set(OLD)), patch.object(
			frappe, "get_all", return_value=self.rows(**{f: 1 for f in OLD})
		):
			flags = pe.get_policy_escapes("EMP-1", "2026-09-01")

		self.assertEqual(flags[NEW], 0)
		self.assertEqual(flags.escape_sandwich, 1)

	def test_period_resolver_degrades_the_same_way(self):
		with patch.object(pe, "_table_columns", return_value=set(OLD)), patch.object(
			frappe, "get_all", return_value=self.rows(**{f: 1 for f in OLD})
		):
			flags = pe.get_policy_escapes_for_period("EMP-1", "2026-08-17", "2026-09-16")

		self.assertEqual(flags[NEW], 0)
		self.assertEqual(flags.escape_absent_gross, 1)

	def test_no_columns_skips_the_query_entirely(self):
		with patch.object(pe, "_table_columns", return_value=set()), patch.object(
			frappe, "get_all", side_effect=AssertionError("must not query")
		):
			flags = pe.get_policy_escapes("EMP-1", "2026-09-01")

		self.assertEqual(flags[NEW], 0)
		self.assertEqual(flags.escape_sandwich, 0)

	def test_synced_column_is_honoured(self):
		with patch.object(pe, "_table_columns", return_value=set(OLD + [NEW])), patch.object(
			frappe, "get_all", return_value=self.rows(**{**{f: 0 for f in OLD}, NEW: 1})
		):
			flags = pe.get_policy_escapes("EMP-2", "2026-09-01")

		self.assertEqual(flags[NEW], 1)
