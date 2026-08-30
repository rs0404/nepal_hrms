import frappe
from frappe.boot import load_translations

no_cache = 1

def get_context(context):
	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # nosempgrep
	context = frappe._dict()
	context.csrf_token = csrf_token
	context.boot = get_boot()
	return context

def get_boot():
	bootinfo = frappe._dict(
		{
			"site_name": frappe.local.site,
			"push_relay_server_url": frappe.conf.get("push_relay_server_url") or "",
			"default_route": get_default_route(),
		}
	)

	bootinfo.lang = frappe.local.lang
	load_translations(bootinfo)

	return bootinfo

def get_default_route():
	return "/bshrms"
