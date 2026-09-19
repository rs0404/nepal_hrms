/**
 * The one place attendance colour is decided.
 *
 * The rule: **hue encodes the day's outcome, and nothing else.** Before this,
 * four independent dimensions — outcome, leave kind, lateness, application state —
 * all competed for the same channel, so green meant Present *and* Home leave *and*
 * Approved, and the Absent and Penalty tiles sat side by side at ΔE 5.8 (the
 * readability floor is 15). Everything that is not an outcome now identifies
 * itself with a letter or a glyph, which it already had.
 *
 * Consequences worth keeping:
 *   - Work From Home is Present. It is not a different outcome, just a location.
 *   - Leave Pending / Rejected are Leave. They are application states, shown by
 *     the ○ / ✕ glyph, not by a hue of their own.
 *   - A penalty day is a *worked* day, so it keeps its outcome fill and says ½P/1P.
 *   - A half day splits the cell diagonally rather than taking a seventh hue.
 *
 * The five outcome hues are validated as a categorical set under all-pairs (any
 * two cells can touch in a grid): normal-vision ΔE 20.8, CVD ΔE 7.2. That CVD
 * figure sits in the band that is legal *only* with secondary encoding — which is
 * why dayCodes() puts a letter on every chromatic non-Present cell. Do not remove
 * the letters and keep the colours.
 */

/** Dark-mode steps are recorded per token; the PWA is light-only today. */
export const OUTCOME = {
	// fill                 ring        dark ring   code
	present: { fill: "#e0f0e0", ring: "#008300", code: "" }, // dark: #008300
	leave: { fill: "#e5effa", ring: "#2a78d6", code: "L" }, // dark: #3987e5
	lwp: { fill: "#fdf4e0", ring: "#eda100", code: "LWP" }, // dark: #c98500
	absent: { fill: "#fce9e9", ring: "#e34948", code: "A" }, // dark: #e34948
	// Neutral on purpose: a non-working day should recede, and a hueless swatch
	// is outside the categorical set, so it needs no letter.
	holiday: { fill: "#eceae6", ring: "#8a8781", code: "" },
}

/**
 * Nepali calendars print rest days in red, so holidays and Saturdays take red
 * numerals. It is the same red family as the Absent ring, one step darker so it
 * clears 4.5:1 as text on every outcome fill (worst 5.9:1) — the Absent ring
 * itself only manages 3.3:1 and is not usable as type.
 */
export const REST_DAY_TEXT = "#a32d2d"

/**
 * Exceptions layered on top of an outcome. Deliberately none of the outcome hues,
 * and validated as their own all-pairs set in both modes (worst ΔE 9.4 dark).
 */
export const EXCEPTION = {
	late: "#eb6834", // dark: #d95926
	early: "#4a3aa7", // dark: #9085e9
	ooo: "#1baf7a", // dark: #199e70
}

const PRESENT_STATUSES = new Set(["Present", "Work From Home"])
const LEAVE_STATUSES = new Set(["On Leave", "Leave Pending", "Leave Rejected"])
const HOLIDAY_STATUSES = new Set(["Holiday", "Weekly Off"])

function statusOf(info) {
	if (!info) return null
	return typeof info === "string" ? info : info.status || null
}

/** Paid leave and leave without pay are different outcomes; they are paid differently. */
function leaveOutcome(info) {
	return info && typeof info !== "string" && info.is_lwp ? "lwp" : "leave"
}

/** "present" | "leave" | "lwp" | "absent" | "holiday" | null */
export function dayOutcome(info) {
	const status = statusOf(info)
	if (!status) return null
	if (PRESENT_STATUSES.has(status)) return "present"
	if (HOLIDAY_STATUSES.has(status)) return "holiday"
	if (LEAVE_STATUSES.has(status)) return leaveOutcome(info)
	if (status === "Absent") return "absent"
	// A half day is half worked; the fill leads with that and splits to the rest.
	if (status === "Half Day") return "present"
	return null
}

/** The outcome occupying the other half of a Half Day, or null. */
export function halfDayOutcome(info) {
	if (!info || typeof info === "string") return null
	if (info.status !== "Half Day") return null
	if (info.leave || info.leave_type) return leaveOutcome(info)
	return "absent"
}

/** Inline style for a day cell, or null when the day has no attendance at all. */
export function dayCellStyle(info) {
	const outcome = dayOutcome(info)
	if (!outcome) return null
	const base = OUTCOME[outcome]
	const other = halfDayOutcome(info)
	const ring = { boxShadow: `inset 0 0 0 1.5px ${base.ring}` }
	if (!other) return { backgroundColor: base.fill, ...ring }
	// 135° so the split reads as a diagonal rather than as two stacked rows.
	return {
		backgroundImage: `linear-gradient(135deg, ${base.fill} 0 50%, ${OUTCOME[other].fill} 50% 100%)`,
		backgroundColor: base.fill,
		...ring,
	}
}

/** Leave-kind letters, or "" for a leave type with no shorthand. */
function leaveKindCode(info) {
	const name = String((info && info.leave_type) || "").toLowerCase()
	if (name.includes("sick")) return "SL"
	if (name.includes("home")) return "HL"
	return ""
}

/**
 * The letters a cell carries. This is the secondary encoding the palette's CVD
 * margin depends on, not decoration.
 *
 * Penalty still wins over the leave letters, as it did before: a charged day is
 * the thing you need to see first, and the fill underneath still states the
 * outcome.
 */
export function dayCodes(info) {
	if (!info || typeof info === "string") return []
	if (info.pool_penalty === "full" || info.penalty_mark === "1P") return ["1P"]
	if (info.pool_penalty === "half" || info.penalty_mark === "½P") return ["½P"]

	const codes = []
	if (info.half_day) codes.push("½")
	const outcome = dayOutcome(info)
	if (outcome === "lwp") codes.push("LWP")
	else if (outcome === "leave") codes.push(leaveKindCode(info) || OUTCOME.leave.code)
	else if (outcome === "absent") codes.push(OUTCOME.absent.code)
	return codes
}

/** Penalty codes are a charge, not a leave kind — they get the solid chip. */
export function dayCodeClass(code) {
	return code === "½P" || code === "1P" ? "att-code att-code-penalty" : "att-code"
}
