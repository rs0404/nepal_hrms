// Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
// For license information, please see license.txt

// Sharing an application with its approver: the link, and the clipboard.
//
// The link is built from the router rather than by stitching strings, so the
// PWA base (/hr) and the doctype -> route mapping stay in one place -- the same
// `${doctype without spaces}DetailView` convention ListView already relies on.

import router from "@/router"

// Application types an employee raises from the PWA and may want to share.
// Must stay in step with APPROVER_EVENT in api/application_share.py.
export const SHAREABLE_DOCTYPES = [
	"Late Entry Application",
	"Early Exit Application",
	"Out of Office Application",
	"Attendance Request",
	"Leave Application",
	"Shift Request",
]

export function isShareable(doctype) {
	return SHAREABLE_DOCTYPES.includes(doctype)
}

export function detailRouteName(doctype) {
	return `${(doctype || "").replace(/\s+/g, "")}DetailView`
}

// Absolute, because the point of the link is to leave the device.
export function applicationLink(doctype, name) {
	if (!doctype || !name) return ""
	const route = router.resolve({
		name: detailRouteName(doctype),
		params: { id: name },
	})
	if (!route || !route.href) return ""
	return new URL(route.href, window.location.origin).href
}

// navigator.clipboard is unavailable on http origins and in some in-app
// browsers, which is exactly where people paste links from. Fall back to the
// old execCommand path rather than failing silently.
export async function copyText(text) {
	if (!text) return false

	if (navigator.clipboard?.writeText) {
		try {
			await navigator.clipboard.writeText(text)
			return true
		} catch (e) {
			// Permission denied or insecure context; try the fallback below.
		}
	}

	try {
		const area = document.createElement("textarea")
		area.value = text
		area.setAttribute("readonly", "")
		area.style.position = "fixed"
		area.style.opacity = "0"
		document.body.appendChild(area)
		area.select()
		const ok = document.execCommand("copy")
		document.body.removeChild(area)
		return ok
	} catch (e) {
		return false
	}
}
