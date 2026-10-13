import { createResource } from "frappe-ui"

import { getDates, getTotalDays } from "./attendance"
import { getLeaveDates } from "./leaves"

// Same display fields the per-doctype team lists added, so every item
// component renders a queue row exactly as it renders its own list's rows.
const decorate = {
	"Leave Application": (row) => {
		row.leave_dates = getLeaveDates(row)
	},
	"Attendance Request": (row) => {
		row.attendance_dates = getDates(row)
		row.total_attendance_days = getTotalDays(row)
	},
	"Shift Request": (row) => {
		row.shift_dates = getDates(row)
		row.total_shift_days = getTotalDays(row)
	},
}

// Undecided and decided-but-unsubmitted requests the user may act on, each
// marked assigned_to_me (designated approver) or not (reaches them through
// Reports To). Expense Claims are not here: they follow the claim's own
// approver, not the org chart.
export const teamPendingRequests = createResource({
	url: "nepal_hrms.api.team_requests.get_team_pending_requests",
	params: { limit: 50 },
	auto: false,
	cache: "nepal_hrms:team_pending_requests",
	transform(data) {
		return (data || []).map((row) => {
			decorate[row.doctype]?.(row)
			return row
		})
	},
})
