"""App integrity tests.

Read-only smoke tests that check every part of this app still loads on the
Frappe / ERPNext version the bench is running: Python modules, hooks, DocTypes
and their database tables, reports, print formats, web pages, templates,
fixtures and patches.

They are meant as a regression baseline: run them before an upgrade (for
example version-15 -> version-16) and again after it, and compare.

    bench --site <site> run-tests --app <app> \
        --module <app>.tests.test_app_integrity --skip-before-tests

Nothing is created, submitted or sent; every query is rolled back.

The file is identical in every app. App-specific exceptions go in an optional
sibling module ``integrity_overrides.py`` (see ``_override`` below).
"""

import importlib
import importlib.util
import json
import os
import pkgutil
import re

import frappe

try:  # Frappe 16+
	from frappe.tests import IntegrationTestCase as _TestCase
except ImportError:  # Frappe 15
	from frappe.tests.utils import FrappeTestCase as _TestCase

APP = __name__.split(".")[0]

_ASSET_EXTENSIONS = (
	".js", ".ts", ".css", ".scss", ".less", ".html", ".json", ".png", ".svg",
	".jpg", ".jpeg", ".ico", ".vue", ".jsx", ".tsx", ".txt", ".md", ".py", ".xml",
)
_DOTTED_PATH = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)+$")
# hooks whose dict keys are DocType names
_DOCTYPE_KEYED_HOOKS = (
	"doc_events",
	"override_doctype_class",
	"override_doctype_dashboards",
	"doctype_js",
	"doctype_list_js",
	"doctype_tree_js",
	"doctype_calendar_js",
	"permission_query_conditions",
	"has_permission",
	"has_website_permission",
)


def _override(name, default):
	"""Read an app-specific setting from ``<app>.tests.integrity_overrides``.

	Supported names:
	  SKIP_MODULES        list of regexes; matching python modules are not imported
	  SKIP_HOOK_PATHS     list of dotted paths in hooks.py that may be unresolvable
	  SKIP_HOOK_ASSETS    list of asset paths in hooks.py that may be missing
	  SKIP_DOCTYPES       list of DocTypes to leave out of the DocType checks
	  SKIP_COLUMNS        list of "DocType.fieldname" allowed to have no database column
	  SKIP_REPORTS        list of reports that are not executed
	  REPORT_FILTERS      {report name: {filters}} used instead of the defaults
	  SKIP_PRINT_FORMATS  list of print formats that are not rendered
	  SKIP_ROUTES         list of web routes that are not rendered
	  SKIP_FIXTURES       list of "DocType::name" fixture records allowed to be missing
	"""
	try:
		module = importlib.import_module(f"{APP}.tests.integrity_overrides")
	except ModuleNotFoundError:
		return default
	return getattr(module, name, default)


def _app_path(*parts):
	return os.path.join(frappe.get_app_path(APP), *parts)


def _app_modules():
	"""Module Def names that belong to this app."""
	return frappe.get_all("Module Def", filters={"app_name": APP}, pluck="name")


def _walk_files(*extensions, subdirs=None):
	root = frappe.get_app_path(APP)
	for base, dirs, files in os.walk(root):
		dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "dist", "__pycache__")]
		if subdirs and not any(f"{os.sep}{s}{os.sep}" in base + os.sep for s in subdirs):
			continue
		for fname in files:
			if fname.endswith(extensions):
				yield os.path.join(base, fname)


def _fail_report(title, problems):
	lines = "\n".join(f"  - {p}" for p in problems)
	return f"{APP}: {len(problems)} {title}:\n{lines}"


class TestAppIntegrity(_TestCase):
	maxDiff = None

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.response = frappe._dict(docs=[])
		frappe.db.rollback()

	# ------------------------------------------------------------------ python

	def test_python_modules_import(self):
		"""Every python module of the app imports (catches removed/renamed core APIs)."""
		skip = [re.compile(p) for p in _override("SKIP_MODULES", [])]
		package = importlib.import_module(APP)
		problems = []
		count = 0
		for info in pkgutil.walk_packages(package.__path__, prefix=f"{APP}."):
			name = info.name
			leaf = name.rsplit(".", 1)[-1]
			if (
				".node_modules." in name
				or ".patches." in name
				or leaf.startswith("test_")
				or leaf == "integrity_overrides"
				or any(p.search(name) for p in skip)
			):
				continue
			try:
				importlib.import_module(name)
				count += 1
			except Exception as e:
				problems.append(f"{name}: {type(e).__name__}: {e}")
		self.assertFalse(problems, _fail_report("modules failed to import", problems))
		self.assertGreater(count, 0, f"{APP}: no python modules found")

	def test_patches_exist(self):
		"""Every line of patches.txt points at a module that exists."""
		path = _app_path("patches.txt")
		if not os.path.exists(path):
			self.skipTest("no patches.txt")
		problems = []
		with open(path) as f:
			for raw in f:
				line = raw.strip()
				if not line or line.startswith("#") or line.startswith("["):
					continue
				if line.startswith(("execute:", "finally:")):
					continue
				module = line.split()[0]
				try:
					found = importlib.util.find_spec(module)
				except Exception:
					found = None
				if not found:
					problems.append(module)
		self.assertFalse(problems, _fail_report("patches in patches.txt do not exist", problems))

	# ------------------------------------------------------------------- hooks

	def _hook_strings(self, value):
		if isinstance(value, str):
			yield value
		elif isinstance(value, dict):
			for v in value.values():
				yield from self._hook_strings(v)
		elif isinstance(value, list | tuple | set):
			for v in value:
				yield from self._hook_strings(v)

	def test_hooks_resolve(self):
		"""Every python path named in hooks.py resolves to a real function/class/module."""
		hooks = importlib.import_module(f"{APP}.hooks")
		installed = set(frappe.get_installed_apps())
		allowed = set(_override("SKIP_HOOK_PATHS", []))
		problems = []
		for hook_name, value in vars(hooks).items():
			if hook_name.startswith("_") or hook_name in ("app_email", "app_publisher", "fixtures"):
				continue
			for text in set(self._hook_strings(value)):
				if not _DOTTED_PATH.match(text) or text.endswith(_ASSET_EXTENSIONS):
					continue
				if text.split(".")[0] not in installed or text in allowed:
					continue
				try:
					frappe.get_attr(text)
				except Exception as attr_error:
					try:
						importlib.import_module(text)
					except Exception:
						problems.append(f"{hook_name}: {text} ({type(attr_error).__name__}: {attr_error})")
		self.assertFalse(problems, _fail_report("hook paths do not resolve", problems))

	def test_hooked_doctypes_exist(self):
		"""DocTypes that hooks.py attaches to (doc_events, overrides, doctype_js...) still exist."""
		hooks = importlib.import_module(f"{APP}.hooks")
		problems = []
		for hook_name in _DOCTYPE_KEYED_HOOKS:
			value = getattr(hooks, hook_name, None)
			if not isinstance(value, dict):
				continue
			for doctype in value:
				if doctype == "*":
					continue
				if not frappe.db.exists("DocType", doctype):
					problems.append(f"{hook_name}: DocType '{doctype}' does not exist")
		self.assertFalse(problems, _fail_report("hooks point at missing DocTypes", problems))

	def test_overridden_doctype_classes_load(self):
		"""override_doctype_class targets load and extend the current core controller."""
		hooks = importlib.import_module(f"{APP}.hooks")
		overrides = getattr(hooks, "override_doctype_class", None) or {}
		problems = []
		for doctype in overrides:
			try:
				from frappe.model.base_document import get_controller

				controller = get_controller(doctype)
				frappe.new_doc(doctype)
				self.assertTrue(controller)
			except Exception as e:
				problems.append(f"{doctype}: {type(e).__name__}: {e}")
		self.assertFalse(problems, _fail_report("overridden DocType classes failed to load", problems))

	def test_hook_assets_exist(self):
		"""JS/CSS files that hooks.py includes exist on disk."""
		hooks = importlib.import_module(f"{APP}.hooks")
		installed = set(frappe.get_installed_apps())
		allowed = set(_override("SKIP_HOOK_ASSETS", []))
		problems = []
		for hook_name, value in vars(hooks).items():
			if hook_name.startswith("_"):
				continue
			for text in set(self._hook_strings(value)):
				if text in allowed:
					continue
				if text.startswith("/assets/"):
					parts = text.split("?")[0].split("/", 3)
					if len(parts) < 4 or parts[2] not in installed:
						continue
					path = os.path.join(frappe.get_app_path(parts[2]), "public", parts[3])
					if not os.path.exists(path):
						problems.append(f"{hook_name}: {text}")
				elif hook_name.startswith("doctype_") and hook_name.endswith("_js") or hook_name == "doctype_js":
					if text.endswith(".js") and not os.path.exists(_app_path(text)):
						problems.append(f"{hook_name}: {text}")
		self.assertFalse(problems, _fail_report("hook assets are missing", problems))

	# ---------------------------------------------------------------- doctypes

	def _app_doctypes(self):
		modules = _app_modules()
		if not modules:
			return []
		skip = set(_override("SKIP_DOCTYPES", []))
		return [
			d
			for d in frappe.get_all(
				"DocType",
				filters={"module": ["in", modules]},
				fields=["name", "issingle", "istable", "is_virtual", "custom"],
				order_by="name",
			)
			if d.name not in skip
		]

	def test_doctype_files_are_installed(self):
		"""Every DocType JSON shipped by the app exists in the database."""
		problems = []
		for path in _walk_files(".json", subdirs=["doctype"]):
			try:
				with open(path) as f:
					data = json.load(f)
			except Exception:
				continue  # reported by test_json_files_are_valid
			if isinstance(data, dict) and data.get("doctype") == "DocType" and data.get("name"):
				if not frappe.db.exists("DocType", data["name"]):
					problems.append(data["name"])
		self.assertFalse(problems, _fail_report("DocTypes are in the app but not in the database", problems))

	def test_doctypes_load(self):
		"""Meta, controller class and a blank document load for every DocType."""
		from frappe.model.base_document import get_controller

		problems = []
		for d in self._app_doctypes():
			try:
				meta = frappe.get_meta(d.name)
				get_controller(d.name)
				frappe.new_doc(d.name)
				for df in meta.fields:
					if df.fieldtype in ("Link", "Table", "Table MultiSelect") and df.options:
						if df.options != "[Select]" and not frappe.db.exists("DocType", df.options):
							problems.append(f"{d.name}.{df.fieldname}: linked DocType '{df.options}' does not exist")
			except Exception as e:
				problems.append(f"{d.name}: {type(e).__name__}: {e}")
		self.assertFalse(problems, _fail_report("DocTypes failed to load", problems))

	def test_doctype_tables_match_meta(self):
		"""Database tables exist and contain every column the DocType defines."""
		allowed = set(_override("SKIP_COLUMNS", []))
		problems = []
		for d in self._app_doctypes():
			if d.issingle or d.is_virtual:
				continue
			try:
				if not frappe.db.table_exists(d.name):
					problems.append(f"{d.name}: table is missing")
					continue
				meta = frappe.get_meta(d.name)
				have = set(frappe.db.get_table_columns(d.name))
				expected = [
					df.fieldname
					for df in meta.fields
					if df.fieldtype not in frappe.model.no_value_fields and not df.get("is_virtual")
				]
				missing = [c for c in expected if c not in have and f"{d.name}.{c}" not in allowed]
				if missing:
					problems.append(f"{d.name}: missing columns {missing}")
			except Exception as e:
				problems.append(f"{d.name}: {type(e).__name__}: {e}")
		self.assertFalse(problems, _fail_report("DocType tables differ from their definition", problems))

	def test_doctype_records_readable(self):
		"""List query (with permission hooks) and the most recent document load."""
		problems = []
		for d in self._app_doctypes():
			if d.is_virtual:
				continue
			try:
				if d.issingle:
					frappe.get_single(d.name)
					continue
				if d.istable:
					frappe.get_all(d.name, limit=1)
					continue
				rows = frappe.get_list(d.name, limit=1, order_by="modified desc")
				if rows:
					frappe.get_doc(d.name, rows[0].name).as_dict()
			except Exception as e:
				problems.append(f"{d.name}: {type(e).__name__}: {e}")
			finally:
				frappe.db.rollback()
		self.assertFalse(problems, _fail_report("DocTypes could not be read", problems))

	# ----------------------------------------------------------------- reports

	def _default_report_filters(self):
		from frappe.utils import add_days, get_first_day, nowdate

		today = nowdate()
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		filters = frappe._dict(
			company=company,
			from_date=add_days(today, -30),
			to_date=today,
			start_date=add_days(today, -30),
			end_date=today,
			date=today,
			posting_date=today,
			as_on_date=today,
			report_date=today,
			month_start=get_first_day(today),
		)
		fiscal_year = frappe.db.get_value(
			"Fiscal Year",
			{"year_start_date": ["<=", today], "year_end_date": [">=", today], "disabled": 0},
			"name",
		)
		if fiscal_year:
			filters.update(fiscal_year=fiscal_year, from_fiscal_year=fiscal_year, to_fiscal_year=fiscal_year)
		return filters

	def test_reports_run(self):
		"""Every enabled report of the app executes without a server error.

		A report that only stops because a filter is missing (a normal
		validation message) counts as working.
		"""
		from frappe.desk.query_report import run

		modules = _app_modules()
		if not modules:
			self.skipTest("no modules")
		skip = set(_override("SKIP_REPORTS", []))
		custom_filters = _override("REPORT_FILTERS", {})
		reports = frappe.get_all(
			"Report",
			filters={"module": ["in", modules], "disabled": 0, "report_type": ["in", ["Script Report", "Query Report"]]},
			pluck="name",
			order_by="name",
		)
		problems = []
		for name in reports:
			if name in skip:
				continue
			filters = frappe._dict(custom_filters.get(name) or self._default_report_filters())
			try:
				run(name, filters=filters, ignore_prepared_report=True)
			except (frappe.ValidationError, frappe.PermissionError):
				pass  # asked for a filter / refused politely: the report code itself works
			except Exception as e:
				problems.append(f"{name}: {type(e).__name__}: {e}")
			finally:
				frappe.db.rollback()
				frappe.local.message_log = []
		self.assertFalse(problems, _fail_report("reports crashed", problems))

	# ----------------------------------------------------------- print formats

	def test_print_formats_render(self):
		"""Print formats shipped by the app render to HTML.

		Tried on the five most recent documents; one successful render is enough,
		so a single document with bad data (a deleted address, say) does not fail it.
		"""
		modules = _app_modules()
		if not modules:
			self.skipTest("no modules")
		skip = set(_override("SKIP_PRINT_FORMATS", []))
		formats = frappe.get_all(
			"Print Format",
			filters={"module": ["in", modules], "disabled": 0},
			fields=["name", "doc_type"],
			order_by="name",
		)
		problems = []
		for pf in formats:
			if pf.name in skip or not pf.doc_type or not frappe.db.exists("DocType", pf.doc_type):
				continue
			if frappe.get_meta(pf.doc_type).issingle:
				continue
			docnames = frappe.get_all(pf.doc_type, limit=5, order_by="modified desc", pluck="name")
			last_error = None
			for docname in docnames:
				try:
					html = frappe.get_print(pf.doc_type, docname, print_format=pf.name)
					self.assertTrue(html)
					last_error = None
					break
				except Exception as e:
					last_error = f"{pf.name} ({pf.doc_type} {docname}): {type(e).__name__}: {str(e)[:300]}"
				finally:
					frappe.db.rollback()
					frappe.local.message_log = []
			if last_error:
				problems.append(last_error)
		self.assertFalse(problems, _fail_report("print formats failed to render", problems))

	# --------------------------------------------------------------- templates

	def test_jinja_templates_compile(self):
		"""Server-side Jinja templates (templates/, www/) have no syntax errors."""
		jenv = frappe.get_jenv()
		problems = []
		for path in _walk_files(".html", ".jinja", ".jinja2", subdirs=["templates", "www"]):
			try:
				with open(path, encoding="utf-8") as f:
					jenv.parse(f.read())
			except Exception as e:
				problems.append(f"{os.path.relpath(path, frappe.get_app_path(APP))}: {type(e).__name__}: {e}")
		self.assertFalse(problems, _fail_report("templates have syntax errors", problems))

	def test_web_pages_render(self):
		"""Static www/ pages of the app answer without a server error (as Guest)."""
		from frappe.utils import set_request
		from frappe.website.serve import get_response

		www = _app_path("www")
		if not os.path.isdir(www):
			self.skipTest("no www folder")
		skip = set(_override("SKIP_ROUTES", []))
		routes = set()
		for base, _dirs, files in os.walk(www):
			for fname in files:
				stem, ext = os.path.splitext(fname)
				if ext not in (".html", ".md") or stem.startswith("_"):
					continue
				rel = os.path.relpath(os.path.join(base, stem), www).replace(os.sep, "/")
				if rel.endswith("/index"):
					rel = rel[: -len("/index")]
				elif rel == "index":
					rel = ""
				routes.add(rel)
		problems = []
		for route in sorted(routes):
			if route in skip:
				continue
			try:
				frappe.set_user("Guest")
				set_request(method="GET", path="/" + route)
				response = get_response()
				if response.status_code >= 500:
					problems.append(f"/{route}: HTTP {response.status_code}")
			except Exception as e:
				problems.append(f"/{route}: {type(e).__name__}: {e}")
			finally:
				frappe.set_user("Administrator")
				frappe.db.rollback()
				frappe.local.message_log = []
		self.assertFalse(problems, _fail_report("web pages returned a server error", problems))

	# ---------------------------------------------------------- files/fixtures

	def test_json_files_are_valid(self):
		"""Every JSON file in the app parses."""
		problems = []
		for path in _walk_files(".json"):
			if f"{os.sep}public{os.sep}" in path or os.path.basename(path).startswith("tsconfig"):
				continue
			try:
				with open(path, encoding="utf-8") as f:
					json.load(f)
			except Exception as e:
				problems.append(f"{os.path.relpath(path, frappe.get_app_path(APP))}: {e}")
		self.assertFalse(problems, _fail_report("JSON files are invalid", problems))

	def test_fixtures_are_installed(self):
		"""Fixture records (custom fields, property setters, roles...) exist on the site."""
		folder = _app_path("fixtures")
		if not os.path.isdir(folder):
			self.skipTest("no fixtures folder")
		allowed = set(_override("SKIP_FIXTURES", []))
		problems = []
		for fname in sorted(os.listdir(folder)):
			if not fname.endswith(".json"):
				continue
			try:
				with open(os.path.join(folder, fname), encoding="utf-8") as f:
					records = json.load(f)
			except Exception:
				continue
			if not isinstance(records, list):
				continue
			for record in records:
				doctype, name = record.get("doctype"), record.get("name")
				if not doctype or not name or f"{doctype}::{name}" in allowed:
					continue
				if not frappe.db.exists("DocType", doctype):
					problems.append(f"{fname}: DocType '{doctype}' does not exist")
					break
				if not frappe.db.exists(doctype, name):
					problems.append(f"{fname}: {doctype} '{name}' is missing")
		self.assertFalse(problems, _fail_report("fixture records are not on the site", problems))

	def test_custom_fields_target_existing_doctypes(self):
		"""Custom fields and property setters owned by the app point at DocTypes/fields that exist."""
		modules = _app_modules()
		if not modules:
			self.skipTest("no modules")
		problems = []
		for cf in frappe.get_all(
			"Custom Field",
			filters={"module": ["in", modules]},
			fields=["name", "dt", "fieldname", "fieldtype", "options", "insert_after"],
		):
			if not frappe.db.exists("DocType", cf.dt):
				problems.append(f"Custom Field {cf.name}: DocType '{cf.dt}' does not exist")
				continue
			if cf.fieldtype in ("Link", "Table", "Table MultiSelect") and cf.options:
				if not frappe.db.exists("DocType", cf.options):
					problems.append(f"Custom Field {cf.name}: linked DocType '{cf.options}' does not exist")
			if not frappe.get_meta(cf.dt).issingle and cf.fieldtype not in frappe.model.no_value_fields:
				if not frappe.db.has_column(cf.dt, cf.fieldname):
					problems.append(f"Custom Field {cf.name}: column is missing in the table")
		self.assertFalse(problems, _fail_report("custom fields are broken", problems))
