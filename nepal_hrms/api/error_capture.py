# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Put every error the employee app shows into Error Log.

Frappe logs a crash (5xx) itself, with its traceback. A frappe.throw -- the red
toast an employee actually sees, "Not permitted", "Rejection Reason is
required", a validation that blocks Approve -- answers 4xx and is logged
nowhere, so the first anyone hears of it is a screenshot. This records those,
for requests made from the app only: Desk users see the same messages on the
form they are editing, and logging every one of those would bury the rest.

Errors that never reach the server (a crashed component) are posted by the app
to log_client_error.
"""

import json
from urllib.parse import urlparse

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cstr, strip_html

# Session expiry, CSRF and the like are not bugs, and each one would repeat
# on every request until the user logs in again.
SKIP_STATUS = {401}
SKIP_EXC_TYPES = {"AuthenticationError", "CSRFTokenError", "SessionStopped", "SessionExpired"}
SECRET_HINTS = ("password", "pwd", "token", "secret", "api_key", "otp")
MAX_VALUE = 2000


def _from_app(request):
	"""True when the request came from the employee app's pages."""
	from nepal_hrms.pwa_route import LEGACY_ROUTES, get_pwa_route

	referer = request.headers.get("Referer") or ""
	head = urlparse(referer).path.strip("/").split("/", 1)[0]
	return bool(head) and head in (get_pwa_route(), *LEGACY_ROUTES)


def _clean_args(form_dict):
	args = {}
	for key, value in (form_dict or {}).items():
		if key == "cmd":
			continue
		if any(hint in key.lower() for hint in SECRET_HINTS):
			args[key] = "***"
			continue
		value = value if isinstance(value, str) else json.dumps(value, default=str)
		args[key] = value if len(value) <= MAX_VALUE else value[:MAX_VALUE] + " …"
	return args


def _shown_messages():
	"""The text the user was shown, from the message log."""
	messages = []
	for entry in getattr(frappe.local, "message_log", None) or []:
		if isinstance(entry, str):
			try:
				entry = json.loads(entry)
			except ValueError:
				entry = {"message": entry}
		text = strip_html(cstr(entry.get("message") if isinstance(entry, dict) else entry)).strip()
		if text:
			messages.append(text)
	return messages


def log_app_errors(response=None, request=None):
	"""after_request hook."""
	try:
		status = getattr(response, "status_code", 200) or 200
		if status < 400 or status >= 500 or status in SKIP_STATUS:
			return
		if not request or not request.path.startswith("/api/") or not _from_app(request):
			return
		exc_type = cstr(frappe.local.response.get("exc_type"))
		if exc_type in SKIP_EXC_TYPES:
			return

		form_dict = frappe.local.form_dict or {}
		method = cstr(form_dict.get("cmd") or request.path)
		# Its own rate limit tripping is not an app error worth a row.
		if method.endswith("error_capture.log_client_error"):
			return
		shown = _shown_messages() or [exc_type or f"HTTP {status}"]
		details = {
			"user": frappe.session.user,
			"method": method,
			"http_status": status,
			"exc_type": exc_type,
			"shown_to_user": shown,
			"args": _clean_args(form_dict),
			"referer": request.headers.get("Referer"),
			"user_agent": request.headers.get("User-Agent"),
		}
		frappe.log_error(
			title=f"App: {shown[0]}"[:140],
			message=json.dumps(details, indent=1, default=str),
			reference_doctype=form_dict.get("doctype") if isinstance(form_dict.get("doctype"), str) else None,
			reference_name=form_dict.get("name") if isinstance(form_dict.get("name"), str) else None,
			# The request may have rolled back; this is queued and inserted on its own.
			defer_insert=True,
		)
	except Exception:
		# Logging must never be the thing that fails a request.
		frappe.logger().error("nepal_hrms: could not log app error", exc_info=True)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=60 * 60)
def log_client_error(message, stack=None, url=None, context=None):
	"""An error raised in the app itself, which the server never saw."""
	message = cstr(message)[:MAX_VALUE]
	details = {
		"user": frappe.session.user,
		"message": message,
		"url": cstr(url)[:500],
		"context": cstr(context)[:MAX_VALUE],
		"stack": cstr(stack)[: MAX_VALUE * 2],
		"user_agent": frappe.get_request_header("User-Agent"),
	}
	frappe.log_error(
		title=f"App (browser): {message}"[:140],
		message=json.dumps(details, indent=1, default=str),
		defer_insert=True,
	)
