export function normalizeAppStatus(status) {
	const value = String(status || "").trim()
	if (value === "Approved") return "Approved"
	if (value === "Rejected") return "Rejected"
	if (["Draft", "Pending", "Open"].includes(value)) return "Draft"
	return ""
}

export function appStatusClass(status) {
	const value = normalizeAppStatus(status)
	if (value === "Approved") return "approved"
	if (value === "Rejected") return "rejected"
	if (value === "Draft") return "draft"
	return ""
}

/** True when the day has actual late/early minutes (not application-only). */
export function hasDelayGraceAfter(info, side) {
	if (!info || typeof info === "string") return { delay: false, grace: false, after: false }
	const graceKey = side === "early" ? "early_grace" : "late_grace"
	const afterKey = side === "early" ? "early_after" : "late_after"
	const grace = !!info[graceKey]
	const after = !!info[afterKey]
	return { delay: grace || after, grace: grace && !after, after: !!after }
}

export function appStatusTitle(kind, status, extra) {
	const value = normalizeAppStatus(status)
	const parts = [kind]
	if (extra) parts.push(extra)
	if (value) parts.push(value)
	return parts.join(" · ")
}
