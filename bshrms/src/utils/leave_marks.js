function isLeaveDay(info) {
	if (!info || typeof info === "string") return false
	const status = info.status || ""
	return (
		!!info.leave ||
		!!info.half_day ||
		["On Leave", "Leave Pending", "Leave Rejected"].includes(status)
	)
}

export function penaltyMarks(info) {
	if (!info || typeof info === "string") return []
	if (info.pool_penalty === "full" || info.penalty_mark === "1P") return ["1P"]
	if (info.pool_penalty === "half" || info.penalty_mark === "½P") return ["½P"]
	return []
}

export function leaveTypeKind(leaveType, isLwp) {
	const name = String(leaveType || "").toLowerCase()
	if (
		isLwp ||
		name === "lwp" ||
		name.includes("lwp") ||
		name.includes("without pay") ||
		name.includes("unpaid")
	) {
		return "lwp"
	}
	if (name.includes("sick")) return "sick"
	if (name.includes("home")) return "home"
	return ""
}

export function leaveTypeMarks(leaveType, isLwp) {
	const kind = leaveTypeKind(leaveType, isLwp)
	if (kind === "lwp") return ["LWP"]
	if (kind === "sick") return ["SL"]
	if (kind === "home") return ["HL"]
	return []
}

export function leaveDayMarks(info) {
	if (!info || typeof info === "string") return []
	const marks = [...penaltyMarks(info)]
	if (marks.length) return marks
	if (isLeaveDay(info)) {
		if (info.half_day) marks.push("1/2")
		marks.push(...leaveTypeMarks(info.leave_type, info.is_lwp))
	}
	return marks
}

export function leaveDayLabel(info) {
	return leaveDayMarks(info).join(" ")
}

export function leaveApplicationMarks(doc) {
	if (!doc) return []
	const marks = []
	if (doc.half_day) marks.push("1/2")
	marks.push(...leaveTypeMarks(doc.leave_type, doc.is_lwp))
	return marks
}

export function leaveMarkClass(mark) {
	if (mark === "1/2") return "half"
	if (mark === "SL") return "sick"
	if (mark === "HL") return "home"
	if (mark === "LWP") return "lwp"
	if (mark === "½P") return "penalty-half"
	if (mark === "1P") return "penalty-full"
	return ""
}

// How much of the day a leave takes: "full" | "first" | "second" | "half".
// "half" is a half day whose half was never recorded (filed before the field).
export function leaveSpan(doc) {
	if (!doc?.half_day) return "full"
	const session = doc.custom_half_day_session
	if (session === "First Half") return "first"
	if (session === "Second Half") return "second"
	return "half"
}

export function leaveSpanLabel(span, __, multiDay = false) {
	if (span === "first") return multiDay ? __("Incl. 1st half") : __("1st half")
	if (span === "second") return multiDay ? __("Incl. 2nd half") : __("2nd half")
	if (span === "half") return multiDay ? __("Incl. ½ day") : __("½ day")
	return __("Full day")
}
