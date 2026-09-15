function isLeaveDay(info) {
	if (!info || typeof info === "string") return false
	const status = info.status || ""
	return (
		!!info.leave ||
		!!info.half_day ||
		["On Leave", "Leave Pending", "Leave Rejected"].includes(status)
	)
}

export function leaveTypeKind(leaveType) {
	const name = String(leaveType || "").toLowerCase()
	if (name.includes("sick")) return "sick"
	if (name.includes("home")) return "home"
	return ""
}

export function leaveTypeMarks(leaveType) {
	const kind = leaveTypeKind(leaveType)
	if (kind === "sick") return ["SL"]
	if (kind === "home") return ["HL"]
	return []
}

export function leaveDayMarks(info) {
	if (!isLeaveDay(info)) return []
	const marks = []
	if (info.half_day) marks.push("1/2")
	marks.push(...leaveTypeMarks(info.leave_type))
	return marks
}

export function leaveDayLabel(info) {
	return leaveDayMarks(info).join(" ")
}

export function leaveApplicationMarks(doc) {
	if (!doc) return []
	const marks = []
	if (doc.half_day) marks.push("1/2")
	marks.push(...leaveTypeMarks(doc.leave_type))
	return marks
}

export function leaveMarkClass(mark) {
	if (mark === "1/2") return "half"
	if (mark === "SL") return "sick"
	if (mark === "HL") return "home"
	return ""
}
