# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Deliberately shadows Frappe HR's `roster` page so /hr belongs to BS HRMS.

hrms registers `/hr/<path:app_path>` -> `roster`, and that rule is merged ahead
of ours: frappe feeds every app's rules to one werkzeug Map, hrms is installed
before nepal_hrms, and werkzeug keeps the first of two identical rules. We
cannot win by ordering either -- moving nepal_hrms ahead of hrms in
installed_apps would flip `override_doctype_class`, which takes the *last*
app's class, and hand Salary Slip and Payroll Entry back to stock.

So we take the other end: `set_template_path` searches installed apps in
reverse, so the later-installed nepal_hrms shadows hrms's roster template and
that rule lands here. `/hr` itself matches no rule and resolves straight to
www/hr.py.

The cost is intended: Frappe HR's own roster page is no longer reachable, at
/hr or at /roster.
"""

from nepal_hrms.www.hr import get_context  # noqa: F401

no_cache = 1
