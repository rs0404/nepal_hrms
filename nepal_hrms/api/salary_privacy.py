# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Keep salary figures off the PWA screen until the employee proves it is them.

This is a screen lock against someone glancing at, or picking up, an unlocked
phone. The employee's own salary data is still theirs to read through the API;
what this guards is the app showing it to whoever holds the phone.

HR chooses which Employee fields may serve as the unlock answer (Nepal HRMS
Settings), each employee picks one of those, and types its value to unlock.
The value is only ever compared here, never sent to the client.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint

USER_DEFAULT_KEY = "nepal_hrms_salary_unlock_field"
DEFAULT_UNLOCK_FIELDS = ("employee_name", "designation")
# Field types that hold no single typeable value.
BLOCKED_FIELDTYPES = {
	"Attach",
	"Attach Image",
	"Button",
	"Column Break",
	"HTML",
	"Password",
	"Section Break",
	"Tab Break",
	"Table",
	"Table MultiSelect",
}


def _settings():
	from nepal_hrms.custom_code.attendance_policy import get_hr_settings

	return get_hr_settings()


def is_enabled(settings=None):
	settings = settings or _settings()
	value = settings.get("mask_salary_in_pwa")
	# On until HR turns it off, including on sites that have not reloaded the doctype yet.
	return True if value is None else bool(cint(value))


def allowed_fields(settings=None):
	"""[{fieldname, label}] HR allows as unlock answers, in the order HR listed them."""
	settings = settings or _settings()
	raw = settings.get("salary_unlock_fields")
	names = [n.strip() for n in (raw or "").replace(",", "\n").splitlines() if n.strip()]
	if not names:
		names = list(DEFAULT_UNLOCK_FIELDS)

	meta = frappe.get_meta("Employee")
	fields = []
	for fieldname in dict.fromkeys(names):
		df = meta.get_field(fieldname)
		if not df or df.fieldtype in BLOCKED_FIELDTYPES:
			continue
		fields.append({"fieldname": fieldname, "label": _(df.label or fieldname)})
	return fields


def _session_employee():
	return frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")


def _chosen_field(fields):
	chosen = frappe.defaults.get_user_default(USER_DEFAULT_KEY)
	names = [f["fieldname"] for f in fields]
	return chosen if chosen in names else (names[0] if names else None)


def _normalise(value):
	return " ".join(str(value or "").split()).casefold()


@frappe.whitelist()
def get_salary_privacy():
	settings = _settings()
	fields = allowed_fields(settings)
	chosen = _chosen_field(fields)
	label = next((f["label"] for f in fields if f["fieldname"] == chosen), "")
	return {
		"enabled": is_enabled(settings) and bool(fields),
		"fields": fields,
		"field": chosen,
		"label": label,
	}


@frappe.whitelist(methods=["POST"])
def set_salary_unlock_field(fieldname):
	fields = allowed_fields()
	if fieldname not in [f["fieldname"] for f in fields]:
		frappe.throw(_("{0} cannot be used to unlock salary.").format(fieldname))
	frappe.defaults.set_user_default(USER_DEFAULT_KEY, fieldname)
	return get_salary_privacy()


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=10 * 60)
def verify_salary_unlock(value):
	"""True when `value` matches the employee's own value of their chosen field."""
	fields = allowed_fields()
	fieldname = _chosen_field(fields)
	employee = _session_employee()
	if not fieldname or not employee:
		return {"ok": False}

	expected = frappe.db.get_value("Employee", employee, fieldname)
	if expected in (None, ""):
		# An empty answer would unlock on an empty guess; make them pick another field.
		frappe.throw(
			_("Your {0} is not filled in on your Employee record. Choose another unlock field in Settings.").format(
				next((f["label"] for f in fields if f["fieldname"] == fieldname), fieldname)
			)
		)
	return {"ok": _normalise(value) == _normalise(expected)}
