import { createResource } from "frappe-ui"
import { employeeResource } from "./employee"

import { formatNepaliPeriod } from "@/utils/nepali_date"

const transformLeaveData = (data) => {
	return data.map((leave) => {
		leave.leave_dates = getLeaveDates(leave)
		leave.doctype = "Leave Application"
		return leave
	})
}

export const getLeaveDates = (leave) => {
	return formatNepaliPeriod(leave.from_date, leave.to_date)
}

export const myLeaves = createResource({
	url: "hrms.api.get_leave_applications",
	params: {
		employee: employeeResource.data.name,
		limit: 10,
	},
	auto: true,
	cache: "hrms:my_leaves",
	transform(data) {
		return transformLeaveData(data)
	},
	onSuccess() {
		leaveBalance.reload()
	},
})

export const teamLeaves = createResource({
	url: "hrms.api.get_leave_applications",
	params: {
		employee: employeeResource.data.name,
		approver_id: employeeResource.data.user_id,
		for_approval: 1,
		limit: 10,
	},
	auto: true,
	cache: "hrms:team_leaves",
	transform(data) {
		return transformLeaveData(data)
	},
})

export const leaveBalance = createResource({
	url: "hrms.api.get_leave_balance_map",
	auto: true,
	cache: "hrms:leave_balance",
	transform: (data) => {
		// Calculate balance percentage for each leave type
		return Object.fromEntries(
			Object.entries(data).map(([leave_type, allocation]) => {
				allocation.balance_percentage =
					(allocation.balance_leaves / allocation.allocated_leaves) * 100
				return [leave_type, allocation]
			})
		)
	},
})
