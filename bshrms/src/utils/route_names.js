// Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
// For license information, please see license.txt

// Route names title-case every word of the doctype, so "Out of Office
// Application" is OutOfOfficeApplication -- stripping the spaces alone gives
// "Outof..." and the router throws on the unknown name.
export function doctypeRouteName(doctype, view) {
	const base = String(doctype || "")
		.split(/\s+/)
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
		.join("")
	return `${base}${view}`
}
