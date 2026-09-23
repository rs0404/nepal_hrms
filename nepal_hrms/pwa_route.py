# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Serve the BS HRMS PWA at the route chosen in Nepal HRMS Settings.

Route rules and www pages are fixed when the app loads, so a route that is
set from the settings page cannot be declared in hooks. Frappe's
`page_renderer` hook runs ahead of every stock renderer, so this one claims
`/<route>` and `/<route>/<anything>` at request time instead.
"""

import os
import re

import frappe
from frappe import _
from frappe.boot import load_translations
from frappe.website.page_renderers.base_renderer import BaseRenderer
from werkzeug.wrappers import Response

DEFAULT_ROUTE = "hr"
# Addresses the PWA has been served at before. They keep redirecting to the
# current route, and the apps screen links through one so it never goes stale.
LEGACY_ROUTES = ("bshrms",)
TEMPLATE = "nepal_hrms/templates/pwa/bshrms.html"
ROUTE_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
# Frappe's own paths, which no www page shows up for.
RESERVED_ROUTES = {
	"api",
	"app",
	"apps",
	"assets",
	"desk",
	"files",
	"login",
	"logout",
	"me",
	"private",
	"socket.io",
	"update-password",
	*LEGACY_ROUTES,
}

ICONS = [
	{
		"src": f"/assets/nepal_hrms/icon/nepal-hrms-{size}{suffix}.png?v=3",
		"sizes": f"{size}x{size}",
		"type": "image/png",
		"purpose": purpose,
	}
	for size in (192, 512)
	for suffix, purpose in (("", "any"), ("-maskable", "maskable"))
]


def normalise_route(route):
	return (route or "").strip().strip("/").lower()


def get_pwa_route():
	"""The configured route, without slashes. Falls back to DEFAULT_ROUTE."""
	try:
		route = frappe.get_cached_doc("Nepal HRMS Settings").get("pwa_route")
	except Exception:
		# Runs on every website request: a settings problem must not take the
		# whole site down with it.
		route = None
	route = normalise_route(route)
	return route if ROUTE_PATTERN.match(route) else DEFAULT_ROUTE


def validate_pwa_route(route):
	"""Normalise and check a route before it is saved. Returns the normalised route."""
	route = normalise_route(route) or DEFAULT_ROUTE
	if not ROUTE_PATTERN.match(route):
		frappe.throw(
			_("App Route must be a single word of lowercase letters, digits and hyphens, such as hr or staff.")
		)
	if route in RESERVED_ROUTES:
		frappe.throw(_("App Route /{0} is reserved. Choose another one.").format(route))

	owner = _www_page_owner(route)
	if owner:
		frappe.throw(_("App Route /{0} is already a page of the {1} app. Choose another one.").format(route, owner))
	for doctype in ("Web Page", "Web Form"):
		if frappe.db.exists(doctype, {"route": ["in", [route, f"{route}/"]]}):
			frappe.throw(_("App Route /{0} is already used by a {1}. Choose another one.").format(route, doctype))
	return route


def _www_page_owner(route):
	for app in frappe.get_installed_apps():
		if app == "nepal_hrms":
			continue
		base = os.path.join(frappe.get_app_path(app), "www", route)
		if os.path.isdir(base) or any(os.path.isfile(base + ext) for ext in (".html", ".md", ".py")):
			return app
	return None


class PWAPage(BaseRenderer):
	def can_render(self):
		self.redirect_to = None
		path = _original_path(self.path)
		head, _, rest = path.partition("/")
		route = get_pwa_route()
		if head == route:
			self.path = path
			return True
		if head in LEGACY_ROUTES:
			self.path = path
			self.redirect_to = "/" + "/".join(p for p in (route, rest) if p)
			return True
		return False

	def render(self):
		if self.redirect_to:
			location = self.redirect_to
			query = frappe.local.request.query_string if getattr(frappe.local, "request", None) else b""
			if query:
				location += "?" + query.decode()
			# 302, not 301: browsers keep a 301 forever, and the route can change again.
			return self.build_response(
				"", 302, {"Location": location, "Cache-Control": "no-store, no-cache, must-revalidate"}
			)

		html = frappe.render_template(TEMPLATE, get_context())
		return self.build_response(html, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


def _original_path(endpoint):
	"""The path as requested, when route rules rewrote it on the way in.

	hrms maps /hr/<path> to its `roster` page, so a renderer is handed "roster"
	for /hr/leaves. Only fall back to the raw request path when it is the one
	that produced this endpoint, so a PathResolver check on some other path is
	not answered for the current request.
	"""
	request = getattr(frappe.local, "request", None)
	path = (request.path if request else "").strip("/ ")
	if not path or path == endpoint:
		return endpoint
	from frappe.website.path_resolver import resolve_from_map

	try:
		return path if resolve_from_map(path) == endpoint else endpoint
	except Exception:
		return endpoint


def get_context():
	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # nosempgrep
	return frappe._dict(csrf_token=csrf_token, boot=get_boot(), site_name=frappe.local.site)


def get_boot():
	bootinfo = frappe._dict(
		{
			"site_name": frappe.local.site,
			"push_relay_server_url": frappe.conf.get("push_relay_server_url") or "",
			"default_route": "/" + get_pwa_route(),
		}
	)

	bootinfo.lang = frappe.local.lang
	load_translations(bootinfo)

	return bootinfo


@frappe.whitelist(allow_guest=True, methods=["GET"])
def manifest():
	"""Web app manifest. Served from here, not a built file, so start_url and scope follow the setting."""
	route = "/" + get_pwa_route()
	data = {
		"name": "Nepal Hrms",
		"short_name": "Nepal Hrms",
		"description": "Everyday HR & Payroll operations at your fingertips (BS)",
		"start_url": route,
		"scope": route,
		"display": "standalone",
		"lang": "en",
		"theme_color": "#ffffff",
		"background_color": "#ffffff",
		"icons": ICONS,
	}
	return Response(frappe.as_json(data), mimetype="application/manifest+json")
