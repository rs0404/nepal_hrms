import { createResource } from "frappe-ui"
import { employeeResource } from "./employee"

import { formatNepaliPeriod } from "@/utils/nepali_date"
import dayjs from "@/utils/dayjs"


export const getDates = (shift) => {
	if (!shift.to_date) {
		const from = formatNepaliPeriod(shift.from_date, shift.from_date)
		return from ? `${from} · Ongoing` : "Ongoing"
	}
	return formatNepaliPeriod(shift.from_date, shift.to_date)
}

export const getTotalDays = (shift) => {
	if (!shift.to_date) return null
	const toDate = dayjs(shift.to_date)
	const fromDate = dayjs(shift.from_date)
	return toDate.diff(fromDate, "d") + 1
}

export const getShiftDates = (shift) => {
	if (!shift.end_date) {
		const start = formatNepaliPeriod(shift.start_date, shift.start_date)
		return start ? `${start} · Ongoing` : "Ongoing"
	}
	return formatNepaliPeriod(shift.start_date, shift.end_date)
}

export const getTotalShiftDays = (shift) => {
	if (!shift.end_date) return null
	const end_date = dayjs(shift.end_date)
	const start_date = dayjs(shift.start_date)
	return end_date.diff(start_date, "d") + 1
}

export const getShiftTiming = (shift) => {
	return (
		shift.start_time.split(":").slice(0, 2).join(":") +
		" - " +
		shift.end_time.split(":").splice(0, 2).join(":")
	)
}

const transformShiftRequests = (data) =>
	data.map((request) => {
		request.doctype = "Shift Request"
		request.shift_dates = getDates(request)
		request.total_shift_days = getTotalDays(request)
		return request
	})

export const myAttendanceRequests = createResource({
	url: "hrms.api.get_attendance_requests",
	params: {
		employee: employeeResource.data.name,
		limit: 10,
	},
	auto: true,
	cache: "hrms:my_attendance_requests",
	transform(data) {
		return transformAttendanceRequests(data)
	}
})
const transformAttendanceRequests = (data) => {
		return data.map((request) => {
			request.doctype = "Attendance Request"
			request.attendance_dates = getDates(request)
			request.total_attendance_days = getTotalDays(request)
			return request
		})
}
export const myShiftRequests = createResource({
	url: "hrms.api.get_shift_requests",
	params: {
		employee: employeeResource.data.name,
		limit: 10,
	},
	auto: true,
	cache: "hrms:my_shift_requests",
	transform(data) {
		return transformShiftRequests(data)
	},
})

export const teamShiftRequests = createResource({
	url: "hrms.api.get_shift_requests",
	params: {
		employee: employeeResource.data.name,
		approver_id: employeeResource.data.user_id,
		for_approval: 1,
		limit: 10,
	},
	auto: false,
	cache: "hrms:team_shift_requests",
	transform(data) {
		return transformShiftRequests(data)
	},
})
export const teamAttendanceRequests = createResource({
	url: "hrms.api.get_attendance_requests",
	params: {
		employee: employeeResource.data.name,
		for_approval: 1,
		limit: 10,
	},
	auto: false,
	cache: "hrms:team_attendance_requests",
	transform: (data) => {
		return transformAttendanceRequests(data)
	},
})

export const pendingOOOApprovals = createResource({
	url: "nepal_hrms.api.ooo_attendance.get_pending_ooo_approvals",
	auto: false,
	cache: "nepal_hrms:pending_ooo_approvals",
	transform(data) {
		const pending = Array.isArray(data) ? data : data?.pending || []
		return pending.map((log) => {
			log.doctype = "OOO Approval"
			return log
		})
	},
})

export const approvedOOOApprovals = createResource({
	url: "nepal_hrms.api.ooo_attendance.get_pending_ooo_approvals",
	auto: false,
	cache: "nepal_hrms:approved_ooo_approvals",
	transform(data) {
		const approved = Array.isArray(data) ? [] : data?.approved || []
		return approved.map((log) => {
			log.doctype = "OOO Approval"
			return log
		})
	},
})
