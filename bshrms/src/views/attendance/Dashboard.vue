<template>
	<BaseLayout pageTitle="Attendance">
		<template #header-extra>
			<div
				class="inline-flex rounded-md border border-gray-200 bg-gray-50 overflow-hidden text-[11px] font-semibold ml-1"
				role="group"
				:aria-label="__('Calendar type')"
			>
				<button
					type="button"
					class="px-2 py-0.5 transition-colors"
					:class="
						activeCalendar === 'Nepali'
							? 'bg-gray-900 text-white'
							: 'text-gray-500'
					"
					@click="activeCalendar = 'Nepali'"
				>
					{{ __("BS") }}
				</button>
				<button
					type="button"
					class="px-2 py-0.5 transition-colors border-l border-gray-200"
					:class="
						activeCalendar === 'English'
							? 'bg-gray-900 text-white'
							: 'text-gray-500'
					"
					@click="activeCalendar = 'English'"
				>
					{{ __("AD") }}
				</button>
			</div>
		</template>
		<template #body>
			<div class="flex flex-col mt-4 mb-7 p-4 gap-5">
				<AttendanceCalendar
					v-if="activeCalendar === 'English'"
					@select-day="onCalendarDaySelect"
				/>
				<NepaliAttendanceCalendar v-else @select-day="onCalendarDaySelect" />

				<ion-action-sheet
					:header="__('Absent day')"
					:buttons="absentSheetButtons"
					:is-open="showAbsentSheet"
					@didDismiss="onAbsentSheetDismiss"
				/>

				<!-- Late / Early pool — coloured, above applications -->
				<div
					v-if="poolSummary.data"
					class="bg-white border border-gray-100 rounded-lg shadow-sm p-3 flex flex-col gap-2"
				>
					<div class="text-sm font-semibold text-gray-800">
						{{ __("Late / Early this month") }}
					</div>
					<div class="grid grid-cols-2 gap-2 text-[11px]">
						<div
							class="rounded-md bg-orange-50 px-2 py-2 text-center ring-1 ring-inset ring-orange-200"
						>
							<div class="text-orange-700 font-semibold text-base leading-5">
								{{ poolSummary.data.late_pool_count }}
							</div>
							<div class="text-orange-600">{{ __("Late days") }}</div>
						</div>
						<div
							class="rounded-md bg-violet-50 px-2 py-2 text-center ring-1 ring-inset ring-violet-200"
						>
							<div class="text-violet-700 font-semibold text-base leading-5">
								{{ poolSummary.data.early_pool_count }}
							</div>
							<div class="text-violet-600">{{ __("Early exits") }}</div>
						</div>
					</div>
					<div
						v-if="poolSummary.data.penalty_enabled"
						class="grid grid-cols-2 gap-2 text-[11px]"
					>
						<div class="rounded-md bg-emerald-50 px-2 py-1.5 text-center">
							<div class="text-emerald-700 font-semibold">
								{{ poolSummary.data.free_remaining }}
							</div>
							<div class="text-emerald-600">{{ __("Free remaining") }}</div>
						</div>
						<div class="rounded-md bg-amber-50 px-2 py-1.5 text-center">
							<div class="text-amber-700 font-semibold">
								{{ poolSummary.data.half_days_so_far }}
							</div>
							<div class="text-amber-600">{{ __("Half-days so far") }}</div>
						</div>
					</div>
					<div
						v-if="
							poolSummary.data.penalty_enabled &&
							poolSummary.data.full_day_escalation_enabled
						"
						class="text-xs mt-0.5"
						:class="
							poolSummary.data.full_day_escalation_active
								? 'text-red-600'
								: 'text-gray-500'
						"
					>
						<span v-if="poolSummary.data.full_day_escalation_active">
							{{
								__(
									"Full-day absent escalation active (more than {0} late/early days).",
									[poolSummary.data.full_day_escalation_threshold]
								)
							}}
						</span>
						<span v-else>
							{{
								__(
									"Full-day absent after more than {0} late/early days.",
									[poolSummary.data.full_day_escalation_threshold]
								)
							}}
						</span>
					</div>
				</div>

				<!-- Applications: Late / Early / OOO + Leave -->
				<div
					v-if="appCounts.data || leaveCounts.data"
					class="bg-white border border-gray-100 rounded-lg shadow-sm p-3 flex flex-col gap-3"
				>
					<div class="text-sm font-semibold text-gray-800">
						{{ __("Late / Early / OOO / Leave this month") }}
					</div>
					<template v-if="appCounts.data">
						<div
							v-for="key in ['late_entry', 'early_exit', 'out_of_office']"
							:key="key"
							class="flex flex-col gap-1"
						>
							<div class="text-xs font-medium text-gray-700">
								{{ __(appCounts.data[key].label) }}
								<span class="text-gray-400 font-normal">
									({{ appCounts.data[key].total }})
								</span>
							</div>
							<div class="grid grid-cols-3 gap-2 text-[11px]">
								<div class="rounded-md bg-green-50 px-2 py-1.5 text-center">
									<div class="text-green-700 font-semibold">
										{{ appCounts.data[key].approved }}
									</div>
									<div class="text-green-600">{{ __("Approved") }}</div>
								</div>
								<div class="rounded-md bg-red-50 px-2 py-1.5 text-center">
									<div class="text-red-700 font-semibold">
										{{ appCounts.data[key].rejected }}
									</div>
									<div class="text-red-600">{{ __("Rejected") }}</div>
								</div>
								<div class="rounded-md bg-amber-50 px-2 py-1.5 text-center">
									<div class="text-amber-700 font-semibold">
										{{ appCounts.data[key].pending }}
									</div>
									<div class="text-amber-600">{{ __("Pending") }}</div>
								</div>
							</div>
						</div>
					</template>
					<div v-if="leaveCounts.data" class="flex flex-col gap-1">
						<div class="text-xs font-medium text-gray-700">
							{{ __("Leave Application") }}
							<span class="text-gray-400 font-normal">
								({{ leaveCounts.data.total }})
							</span>
						</div>
						<div class="grid grid-cols-3 gap-2 text-[11px]">
							<div class="rounded-md bg-green-50 px-2 py-1.5 text-center">
								<div class="text-green-700 font-semibold">
									{{ leaveCounts.data.approved }}
								</div>
								<div class="text-green-600">{{ __("Approved") }}</div>
							</div>
							<div class="rounded-md bg-red-50 px-2 py-1.5 text-center">
								<div class="text-red-700 font-semibold">
									{{ leaveCounts.data.rejected }}
								</div>
								<div class="text-red-600">{{ __("Rejected") }}</div>
							</div>
							<div class="rounded-md bg-amber-50 px-2 py-1.5 text-center">
								<div class="text-amber-700 font-semibold">
									{{ leaveCounts.data.pending }}
								</div>
								<div class="text-amber-600">{{ __("Pending") }}</div>
							</div>
						</div>
						<div v-if="leaveCounts.data.days" class="text-[11px] text-gray-500">
							{{ __("Approved leave days") }}:
							<span class="font-semibold text-gray-700">{{
								leaveCounts.data.days
							}}</span>
						</div>
					</div>
				</div>

				<div class="w-full grid grid-cols-2 gap-2">
					<router-link
						:to="{ name: 'AttendanceRequestFormView' }"
						v-slot="{ navigate }"
						class="col-span-2"
					>
						<Button @click="navigate" variant="solid" class="w-full py-5 text-base">
							{{ __("Request Attendance") }}
						</Button>
					</router-link>
					<router-link
						:to="{ name: 'LateEntryApplicationFormView' }"
						v-slot="{ navigate }"
					>
						<Button @click="navigate" variant="subtle" class="w-full py-4 text-sm">
							{{ __("Late Entry") }}
						</Button>
					</router-link>
					<router-link
						:to="{ name: 'EarlyExitApplicationFormView' }"
						v-slot="{ navigate }"
					>
						<Button @click="navigate" variant="subtle" class="w-full py-4 text-sm">
							{{ __("Early Exit") }}
						</Button>
					</router-link>
					<router-link
						:to="{ name: 'OutOfOfficeApplicationFormView' }"
						v-slot="{ navigate }"
						class="col-span-2"
					>
						<Button @click="navigate" variant="subtle" class="w-full py-4 text-sm">
							{{ __("Out of Office Application") }}
						</Button>
					</router-link>
				</div>
				<div>
					<div class="text-lg text-gray-800 font-bold">
						{{ __("Recent Attendance Requests") }}
					</div>
					<RequestList
						:component="markRaw(AttendanceRequestItem)"
						:items="myAttendanceRequests?.data?.slice(0, 5)"
						:addListButton="true"
						:listButtonRoute="__('AttendanceRequestListView')"
					/>
				</div>
				<div>
					<div class="text-lg text-gray-800 font-bold">{{ __("Upcoming Shifts") }}</div>
					<RequestList
						:component="markRaw(ShiftAssignmentItem)"
						:items="upcomingShifts"
						:addListButton="true"
						listButtonRoute="ShiftAssignmentListView"
						:emptyStateMessage="__('You have no upcoming shifts')"
					/>
				</div>
				<div class="w-full">
					<router-link :to="{ name: 'ShiftRequestFormView' }" v-slot="{ navigate }">
						<Button @click="navigate" variant="solid" class="w-full py-5 text-base">
							{{ __("Request a Shift") }}
						</Button>
					</router-link>
				</div>
				<div>
					<div class="text-lg text-gray-800 font-bold">
						{{ __("Recent Shift Requests") }}
					</div>
					<RequestList
						:component="markRaw(ShiftRequestItem)"
						:items="myShiftRequests?.data?.slice(0, 5)"
						:addListButton="true"
						listButtonRoute="ShiftRequestListView"
					/>
				</div>
				<div>
					<div class="text-lg text-gray-800 font-bold mb-3">{{ __("My Attendance") }}</div>
					<div
						class="flex flex-col gap-0 bg-white rounded-lg shadow-sm border border-gray-100 overflow-hidden"
						v-if="recentAttendance.data?.length"
					>
						<div
							v-for="row in recentAttendance.data"
							:key="row.name"
							class="px-3.5 border-b last:border-0"
						>
							<AttendanceItem :doc="row" />
						</div>
						<router-link :to="{ name: 'AttendanceListView' }" v-slot="{ navigate }">
							<Button
								variant="ghost"
								@click="navigate"
								class="w-full !text-gray-500 rounded-none"
							>
								{{ __("View All Attendance") }}
							</Button>
						</router-link>
					</div>
					<div
						v-else
						class="text-sm text-gray-500 italic p-4 text-center bg-white rounded-lg"
					>
						{{ __("No attendance records found") }}
					</div>
				</div>
				<div>
					<div class="text-lg text-gray-800 font-bold mb-3">
						{{ __("Recent Attendance Logs") }}
					</div>
					<div
						class="flex flex-col gap-3 bg-white p-4 rounded-lg shadow-sm border border-gray-100"
						v-if="recentCheckins.data?.length"
					>
						<div
							v-for="log in recentCheckins.data"
							:key="log.name"
							class="flex justify-between items-center border-b last:border-0 py-2"
						>
							<div class="flex flex-col">
								<span class="text-sm font-medium text-gray-800">{{
									dayjs(log.time).format("hh:mm a")
								}}</span>
								<span class="text-xs text-gray-500">{{
									dayjs(log.time).format("D MMM, YYYY")
								}}</span>
							</div>
							<div class="flex items-center gap-3">
								<Badge
									:label="
										log.custom_attendance_type === 'OOO Work'
											? 'OOO ' + __(log.log_type)
											: __(log.log_type)
									"
									:theme="log.log_type === 'IN' ? 'green' : 'orange'"
									size="sm"
								/>
							</div>
						</div>
						<router-link
							:to="{ name: 'EmployeeCheckinListView' }"
							v-slot="{ navigate }"
						>
							<Button
								variant="ghost"
								@click="navigate"
								class="w-full mt-2 !text-gray-500"
								>{{ __("View All Logs") }}</Button
							>
						</router-link>
					</div>
					<div
						v-else
						class="text-sm text-gray-500 italic p-4 text-center bg-white rounded-lg"
					>
						{{ __("No recent logs found") }}
					</div>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, inject, markRaw, ref, onMounted, watch } from "vue"
import { createResource, createListResource, Badge } from "frappe-ui"
import { useRouter } from "vue-router"
import { IonActionSheet } from "@ionic/vue"

import BaseLayout from "@/components/BaseLayout.vue"
import AttendanceRequestItem from "@/components/AttendanceRequestItem.vue"
import AttendanceItem from "@/components/AttendanceItem.vue"
import ShiftRequestItem from "@/components/ShiftRequestItem.vue"
import ShiftAssignmentItem from "@/components/ShiftAssignmentItem.vue"
import RequestList from "@/components/RequestList.vue"
import AttendanceCalendar from "@/components/AttendanceCalendar.vue"
import NepaliAttendanceCalendar from "@/components/NepaliAttendanceCalendar.vue"
import { getBsMonthAdRange } from "@/utils/nepali_date"

const activeCalendar = ref("Nepali")
const employee = inject("$employee")
const dayjs = inject("$dayjs")
const socket = inject("$socket")
const __ = inject("$translate")
const router = useRouter()

const showAbsentSheet = ref(false)
const absentDate = ref(null)
const absentSheetButtons = computed(() => [
	{
		text: __("Attendance Request"),
		data: { action: "attendance_request" },
	},
	{
		text: __("Leave Application"),
		data: { action: "leave_application" },
	},
	{
		text: __("Cancel"),
		role: "cancel",
		data: { action: "cancel" },
	},
])

const monthRange = computed(() => {
	if (activeCalendar.value === "Nepali") {
		const bs = getBsMonthAdRange()
		if (bs) return bs
	}
	return {
		from_date: dayjs().startOf("month").format("YYYY-MM-DD"),
		to_date: dayjs().endOf("month").format("YYYY-MM-DD"),
	}
})

const poolSummary = createResource({
	url: "nepal_hrms.api.cnr_applications.get_late_early_pool_summary",
	makeParams: () => ({
		employee: employee.data?.name,
		from_date: monthRange.value.from_date,
		to_date: monthRange.value.to_date,
	}),
	auto: true,
	cache: [
		"hrms:late-early-pool",
		() => employee.data?.name,
		() => monthRange.value.from_date,
	],
})

const appCounts = createResource({
	url: "nepal_hrms.api.cnr_applications.get_cnr_application_counts",
	makeParams: () => ({
		employee: employee.data?.name,
		from_date: monthRange.value.from_date,
		to_date: monthRange.value.to_date,
	}),
	auto: true,
	cache: [
		"nepal_hrms:cnr-app-counts",
		() => employee.data?.name,
		() => monthRange.value.from_date,
	],
})

const leaveCounts = createResource({
	url: "nepal_hrms.api.attendance_calendar.get_leave_application_counts",
	makeParams: () => ({
		employee: employee.data?.name,
		from_date: monthRange.value.from_date,
		to_date: monthRange.value.to_date,
	}),
	auto: true,
	cache: [
		"nepal_hrms:leave-app-counts",
		() => employee.data?.name,
		() => monthRange.value.from_date,
	],
})

watch(monthRange, () => {
	poolSummary.reload()
	appCounts.reload()
	leaveCounts.reload()
})

function onCalendarDaySelect({ date, late, early, status }) {
	if (!date) return
	// Prefer Early Exit when both markers are present
	if (early) {
		router.push({
			name: "EarlyExitApplicationFormView",
			query: { attendance_date: date, prefill: "1" },
		})
		return
	}
	if (late) {
		router.push({
			name: "LateEntryApplicationFormView",
			query: { attendance_date: date, prefill: "1" },
		})
		return
	}
	if (status === "Absent") {
		absentDate.value = date
		showAbsentSheet.value = true
	}
}

function onAbsentSheetDismiss(ev) {
	showAbsentSheet.value = false
	const action = ev?.detail?.data?.action
	const date = absentDate.value
	absentDate.value = null
	if (!date || !action || action === "cancel") return
	if (action === "attendance_request") {
		router.push({
			name: "AttendanceRequestFormView",
			query: { from_date: date, to_date: date, prefill: "1" },
		})
		return
	}
	if (action === "leave_application") {
		router.push({
			name: "LeaveApplicationFormView",
			query: { from_date: date, to_date: date, prefill: "1" },
		})
	}
}

const recentCheckins = createListResource({
	doctype: "Employee Checkin",
	fields: ["name", "time", "log_type", "custom_attendance_type"],
	filters: {
		employee: employee.data.name,
	},
	orderBy: "time desc",
	limit: 10,
	auto: true,
})

const recentAttendance = createListResource({
	doctype: "Attendance",
	fields: [
		"name",
		"employee",
		"attendance_date",
		"status",
		"working_hours",
		"in_time",
		"out_time",
		"leave_type",
		"leave_application",
		"attendance_request",
		"shift",
	],
	filters: {
		employee: employee.data.name,
		docstatus: ["<", 2],
	},
	orderBy: "attendance_date desc",
	limit: 8,
	auto: true,
})

import {
	getShiftDates,
	getTotalShiftDays,
	getShiftTiming,
	myAttendanceRequests,
	myShiftRequests,
} from "@/data/attendance"
import { useListUpdate } from "@/composables/realtime"

const shifts = createResource({
	url: "hrms.api.get_shifts",
	auto: true,
	cache: "hrms:shifts",
	transform: (data) => {
		return data.map((assignment) => {
			assignment.doctype = "Shift Assignment"
			assignment.is_upcoming =
				!assignment.end_date || dayjs(assignment.end_date).isAfter(dayjs())
			assignment.shift_dates = getShiftDates(assignment)
			assignment.total_shift_days = getTotalShiftDays(assignment)
			assignment.shift_timing = getShiftTiming(assignment)
			return assignment
		})
	},
})

const upcomingShifts = computed(() => {
	const filteredShifts = shifts.data?.filter((shift) => shift.is_upcoming)

	// show only 5 upcoming shifts
	return filteredShifts?.slice(0, 5)
})

onMounted(() => {
	useListUpdate(socket, "Attendance", () => {
		recentAttendance.reload()
		poolSummary.reload()
	})
	useListUpdate(socket, "Employee Checkin", () => recentCheckins.reload())
	useListUpdate(socket, "Late Entry Application", () => appCounts.reload())
	useListUpdate(socket, "Early Exit Application", () => appCounts.reload())
	useListUpdate(socket, "Out of Office Application", () => appCounts.reload())
	useListUpdate(socket, "Leave Application", () => leaveCounts.reload())
})
</script>
