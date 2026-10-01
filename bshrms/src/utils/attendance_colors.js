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
 *     the pending clock / ✕ mark, not by a hue of their own.
 *   - A penalty day is a *worked* day, so it keeps its outcome fill and says ½P/1P.
 *   - A half day splits the cell diagonally rather than taking a seventh hue.
 *
 * The five outcome hues are validated as a categorical set under all-pairs (any
 * two cells can touch in a grid): normal-vision ΔE 20.8, CVD ΔE 7.2. That CVD
 * figure sits in the band that is legal *only* with secondary encoding — which is
 * why dayCodes() puts a letter on every chromatic non-Present cell. Do not remove
 * the letters and keep the colours.
 */

/**
 * Four outcomes, one hue each.
 *
 * Every kind of leave shares one blue and lets its letters (L / SL / HL / LWP)
 * say which kind — they are all leave, and the kind is what varies, not the
 * category. Collapsing them is what freed amber for Holiday, and this set is the
 * first to clear every check outright: CVD ΔE 12.7, normal-vision ΔE 24.0,
 * all-pairs. The previous five-hue version could only reach the 6–8 warn band.
 */
export const OUTCOME = {
	present: { fill: "#c7e9d4", ring: "#008300", code: "" },
	leave: { fill: "#cbdafa", ring: "#2a78d6", code: "L" },
	absent: { fill: "#fad3e7", ring: "#d4537e", code: "A" },
	// Amber, not grey: a rest day should still look like a day. Red numerals do
	// the rest, so it needs no letter.
	holiday: { fill: "#fde8c4", ring: "#eda100", code: "" },
	// A penalty is a charge, not an outcome, so it takes the solid ink of the
	// ½P / 1P chip rather than borrowing the absent pink. Colouring a charged
	// half as absence contradicted the summary, which counts it under Penalty
	// Days and not one hour under Absent.
	penalty: { fill: "#d6d3d1", ring: "#1c1917", code: "P" },
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

/** "present" | "leave" | "absent" | "holiday" | null */
export function dayOutcome(info) {
	const status = statusOf(info)
	if (!status) return null
	if (PRESENT_STATUSES.has(status)) return "present"
	if (HOLIDAY_STATUSES.has(status)) return "holiday"
	if (LEAVE_STATUSES.has(status)) return "leave"
	if (status === "Absent") return "absent"
	// A half day is half worked; the fill leads with that and splits to the rest.
	if (status === "Half Day") return "present"
	return null
}

/**
 * The two halves of a half day as [workedOutcome, otherOutcome], or null.
 *
 * A half day arrives two ways and both must split: status "Half Day" (worked
 * half + absent half) and status "On Leave" with half_day set (worked half +
 * leave half). Keying only on the status string missed the second, which is the
 * common one — every half day in the live data is a half-day leave.
 *
 * half_day_status is Attendance's own word for what the other half was, and it
 * overrules the leave: a day can carry an approved half-day leave *and* still
 * have its other half marked Absent, which payroll charges as half a day. Left
 * to the leave flag alone the cell came out present + leave, showing nothing of
 * the half that was actually deducted.
 *
 * A ½P comes first of all: that half is a penalty, and calling it absent put the
 * cell at odds with Penalty Days, which is where the charge is reported.
 */
export function halfDayParts(info) {
	if (!info || typeof info === "string") return null
	const isHalf = !!info.half_day || info.status === "Half Day"
	if (!isHalf) return null
	// A ½P is charged as a penalty, not an absence. The worked half stands.
	if (info.pool_penalty === "half" || info.penalty_mark === "½P") {
		return ["present", "penalty"]
	}
	const onLeave = !!info.leave || !!info.leave_type || LEAVE_STATUSES.has(info.status)
	// [non-leave half, leave half]. half_day_status is the *non-leave* half, so on
	// a half-day leave an Absent there is that half -- the leave half is still
	// leave. Reading it as the second part drew the absent half as present and
	// lost the leave half entirely.
	// With no Attendance row yet (a leave applied for ahead, or the day not
	// marked) the worked half has not happened: "none", drawn white, rather than
	// a Present nobody has earned. Only an explicit 0 says so -- a payload from
	// before the flag existed keeps the old drawing.
	if (onLeave) {
		if (info.attendance === 0) return ["none", "leave"]
		return [info.half_day_status === "Absent" ? "absent" : "present", "leave"]
	}
	return ["present", "absent"]
}

// The half of a day that has not happened yet. Not an outcome, so not in OUTCOME.
const UNMARKED_FILL = "#ffffff"
const partFill = (part) => (part === "none" ? UNMARKED_FILL : OUTCOME[part].fill)

/**
 * Inline style for a day cell, or null when the day has no attendance at all.
 *
 * A half day splits corner to corner: **top-left is the first half of the day,
 * bottom-right the second**. Which is which comes from worked_half, inferred
 * server-side from the check-in against the shift midpoint. With no shift or no
 * check-in there is nothing to infer, and the worked half leads.
 */
export function dayCellStyle(info) {
	const outcome = dayOutcome(info)
	if (!outcome) return null
	const base = OUTCOME[outcome]
	const parts = halfDayParts(info)
	const ring = { boxShadow: `inset 0 0 0 1.5px ${base.ring}` }
	if (!parts) return { backgroundColor: base.fill, ...ring }

	const [worked, other] = parts
	const workedSecond = info && typeof info !== "string" && info.worked_half === "second"
	const [first, second] = workedSecond
		? [partFill(other), partFill(worked)]
		: [partFill(worked), partFill(other)]
	// 135° runs top-left to bottom-right, so the first colour is the first half.
	return {
		backgroundImage: `linear-gradient(135deg, ${first} 0 50%, ${second} 50% 100%)`,
		backgroundColor: base.fill,
		...ring,
	}
}

/** Which kind of leave, since the fill no longer distinguishes them. */
function leaveKindCode(info) {
	const name = String((info && info.leave_type) || "").toLowerCase()
	if (info && info.is_lwp) return "LWP"
	if (name.includes("without pay") || name.includes("unpaid") || name.includes("lwp")) {
		return "LWP"
	}
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
	// Same test as the split: "Half Day" status carries no half_day flag of its own.
	const parts = halfDayParts(info)
	if (parts) codes.push("½")
	const outcome = dayOutcome(info)
	if (outcome === "leave") codes.push(leaveKindCode(info) || OUTCOME.leave.code)
	else if (outcome === "absent") codes.push(OUTCOME.absent.code)
	// Half-day leave whose other half is still Absent: the leave letter alone
	// would leave the pink half with no secondary encoding, which is what the
	// palette's CVD margin rests on.
	// Either position: on a leave day the absent half is the first part.
	if (parts && parts.includes("absent") && outcome !== "absent") {
		codes.push(OUTCOME.absent.code)
	}
	return codes
}

/** Penalty codes are a charge, not a leave kind — they get the solid chip. */
export function dayCodeClass(code) {
	return code === "½P" || code === "1P" ? "att-code att-code-penalty" : "att-code"
}
