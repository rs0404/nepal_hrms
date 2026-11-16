<template>
	<div v-if="days.length" class="flex flex-col gap-2 w-full">
		<div class="text-gray-600 text-base">
			{{ days.length === 1 ? __("Attendance on This Day") : __("Attendance on These Days") }}
		</div>
		<div
			v-for="day in days"
			:key="day.date"
			class="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 flex flex-col gap-2"
		>
			<div class="flex items-center justify-between gap-2">
				<span class="text-sm font-medium text-gray-800">{{ formatDualDate(day.date) }}</span>
				<span
					class="text-xs font-semibold rounded-full px-2 py-0.5"
					:class="statusClass(day.attendance)"
				>
					{{ statusLabel(day.attendance) }}
				</span>
			</div>

			<div v-if="day.attendance" class="text-xs text-gray-600 flex flex-wrap gap-x-3 gap-y-0.5">
				<span>{{ __("In") }} {{ clock(day.attendance.in_time) || "—" }}</span>
				<span>{{ __("Out") }} {{ clock(day.attendance.out_time) || "—" }}</span>
				<span v-if="day.attendance.working_hours">
					{{ Number(day.attendance.working_hours).toFixed(2) }} {{ __("hrs") }}
				</span>
				<span v-if="day.attendance.custom_late_mins" class="text-amber-700">
					{{ __("Late {0} min", [day.attendance.custom_late_mins]) }}
				</span>
				<span v-if="day.attendance.custom_early_mins" class="text-amber-700">
					{{ __("Early {0} min", [day.attendance.custom_early_mins]) }}
				</span>
				<span v-if="Number(day.attendance.docstatus) === 0" class="text-gray-400">
					{{ __("(draft)") }}
				</span>
			</div>

			<div v-if="day.checkins.length" class="flex flex-wrap gap-1.5">
				<span
					v-for="(c, i) in day.checkins"
					:key="i"
					class="text-xs rounded-md bg-white border border-gray-200 px-1.5 py-0.5 text-gray-700"
					:title="c.custom_reason || ''"
				>
					<b :class="c.log_type === 'IN' ? 'text-green-700' : 'text-gray-500'">{{ c.log_type || "—" }}</b>
					{{ clock(c.time) }}
					<span
						v-if="c.custom_attendance_type && c.custom_attendance_type !== 'Normal'"
						class="text-blue-700"
					>· {{ __(c.custom_attendance_type) }}</span>
				</span>
			</div>
			<div v-else class="text-xs text-gray-400">{{ __("No check-ins") }}</div>

			<div
				v-for="leave in day.leaves || []"
				:key="leave.name"
				class="text-xs rounded-md bg-blue-50 border border-blue-100 px-2 py-1 text-blue-900 flex flex-wrap items-center gap-x-1.5"
			>
				<FeatherIcon name="calendar" class="h-3 w-3 text-blue-600" />
				<span class="font-medium">{{ __(leave.leave_type) }}</span>
				<span v-if="isHalfDay(leave, day.date)">· {{ __("Half Day") }}</span>
				<span
					class="ml-auto font-semibold"
					:class="leave.status === 'Approved' ? 'text-green-700' : leave.status === 'Rejected' ? 'text-rose-700' : 'text-amber-700'"
				>
					{{ leaveStatus(leave) }}
				</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"

import { formatDualDate, timeFromDatetime } from "@/utils/nepali_date"

const __ = inject("$translate")
const props = defineProps({
	name: { type: String, required: true },
	doctype: { type: String, default: "Attendance Request" },
})

// What already happened on each day the request asks about, so the approver
// can verify it here instead of opening the calendar.
const evidence = createResource({
	url: "nepal_hrms.api.team_requests.get_attendance_request_evidence",
	params: { name: props.name, doctype: props.doctype },
	auto: true,
})

// A leave mostly covers days nobody worked; show only the days with something
// on them, such as the worked half of a half-day leave.
const days = computed(() => {
	const all = evidence.data || []
	if (props.doctype !== "Leave Application") return all
	return all.filter((d) => d.attendance || d.checkins.length || d.leaves?.length)
})

function clock(dt) {
	return (timeFromDatetime(dt) || "").slice(0, 5)
}

function isHalfDay(leave, date) {
	if (!Number(leave.half_day)) return false
	return !leave.half_day_date || leave.half_day_date === date || leave.from_date === leave.to_date
}

function leaveStatus(leave) {
	if (Number(leave.docstatus) === 0 && leave.status === "Open") return __("Pending")
	return __(leave.status)
}

function statusLabel(att) {
	if (!att) return __("Not marked")
	return att.half_day_status && att.status === "Half Day"
		? `${__(att.status)} · ${__(att.half_day_status)}`
		: __(att.status)
}

function statusClass(att) {
	if (!att) return "bg-gray-100 text-gray-500"
	if (att.status === "Present" || att.status === "Work From Home") return "bg-green-100 text-green-800"
	if (att.status === "Absent") return "bg-rose-100 text-rose-800"
	if (att.status === "On Leave") return "bg-blue-100 text-blue-800"
	return "bg-amber-100 text-amber-800"
}
</script>
