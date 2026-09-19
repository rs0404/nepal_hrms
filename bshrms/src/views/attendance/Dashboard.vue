<template>
	<BaseLayout pageTitle="Attendance" @viewWillEnter="refreshAttendanceView">
		<template #header-extra>
			<div class="flex items-center gap-1 ml-1">
				<div
					v-if="showLiveToggle"
					class="inline-flex rounded-md border border-gray-200 bg-gray-50 overflow-hidden text-[11px] font-semibold"
					role="group"
					:aria-label="__('Attendance view')"
				>
					<button
						type="button"
						class="px-2 py-0.5 transition-colors"
						:class="
							attendanceView === 'calendar'
								? 'bg-gray-900 text-white'
								: 'text-gray-500'
						"
						@click="attendanceView = 'calendar'"
					>
						{{ __("Cal") }}
					</button>
					<button
						type="button"
						class="px-2 py-0.5 transition-colors border-l border-gray-200"
						:class="
							attendanceView === 'live'
								? 'bg-gray-900 text-white'
								: 'text-gray-500'
						"
						@click="attendanceView = 'live'"
					>
						{{ __("Live") }}
					</button>
				</div>
				<div
					v-if="attendanceView === 'calendar'"
					class="inline-flex rounded-md border border-gray-200 bg-gray-50 overflow-hidden text-[11px] font-semibold"
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
			</div>
		</template>
		<template #body>
			<div class="flex flex-col mt-4 mb-7 p-4 gap-3">
				<LiveAttendanceBoard
					v-if="attendanceView === 'live'"
					:leaveBoardOnly="leaveBoardOnly"
					:canViewPast="!!pwaAccess.data?.can_view_past_attendance"
				/>

				<template v-else>
				<Autocomplete
					v-if="canViewOthers"
					class="w-full"
					:placeholder="__('Search employee')"
					v-model="selectedEmployeeOption"
					:options="employeeOptions"
					@update:query="onEmployeeQuery"
				/>

				<AttendanceCalendar
					v-if="activeCalendar === 'English'"
					ref="adCalendar"
					:key="'ad-' + calendarEmployee"
					:employee="calendarEmployee"
					@select-day="onCalendarDaySelect"
					@create-leave="onCreateLeave"
					@refresh="refreshAttendanceView"
					@period-change="onCalendarPeriodChange"
				/>
				<NepaliAttendanceCalendar
					v-else
					ref="bsCalendar"
					:key="'bs-' + calendarEmployee"
					:employee="calendarEmployee"
					@select-day="onCalendarDaySelect"
					@create-leave="onCreateLeave"
					@refresh="refreshAttendanceView"
					@period-change="onCalendarPeriodChange"
				/>

				<ion-modal
					:is-open="showDaySheet"
					@didDismiss="onDaySheetDismiss"
					:initial-breakpoint="1"
					:breakpoints="[0, 1]"
				>
					<AttendanceDaySheet
						v-if="selectedDay"
						:key="selectedDay.stamp"
						:date="selectedDay.date"
						:fallbackStatus="selectedDay.status"
						:employee="calendarEmployee"
						@create-leave="onCreateLeave"
					/>
				</ion-modal>

				<Dialog v-model="showSandwichDialog">
					<template #body-title>
						<h2 class="text-xl font-bold">{{ __("Sandwich Rule Warning") }}</h2>
					</template>
					<template #body-content>
						<p class="text-sm text-gray-700">{{ sandwichInfo?.message }}</p>
					</template>
					<template #actions>
						<div class="flex flex-row gap-4">
							<Button
								variant="outline"
								class="py-5 w-full"
								@click="showSandwichDialog = false"
							>
								{{ __("Cancel") }}
							</Button>
							<Button
								variant="solid"
								:theme="sandwichInfo?.block ? 'red' : 'gray'"
								class="py-5 w-full"
								@click="proceedWithLeave"
							>
								{{ __("Proceed Anyway") }}
							</Button>
						</div>
					</template>
				</Dialog>

				<!-- Late / Early pool — coloured, above applications -->
				<div
					v-if="poolSummary.data"
					class="bg-white border border-gray-100 rounded-lg shadow-sm p-3 flex flex-col gap-2"
				>
					<div class="text-sm font-semibold text-gray-800">
						{{ periodLabel ? __("Late / Early · {0}", [periodLabel]) : __("Late / Early") }}
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
							<div class="text-amber-600">{{ __("½P so far") }}</div>
						</div>
						<div
							v-if="poolSummary.data.full_days_so_far"
							class="rounded-md bg-red-50 px-2 py-1.5 text-center"
						>
							<div class="text-red-700 font-semibold">
								{{ poolSummary.data.full_days_so_far }}
							</div>
							<div class="text-red-600">{{ __("1P so far") }}</div>
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

				<!-- Applications this month: compact rows -->
				<div
					v-if="monthAppRows.length"
					class="bg-white border border-gray-100 rounded-lg shadow-sm px-3 py-2"
				>
					<div
						class="grid grid-cols-[minmax(0,1fr)_3.5rem_3.5rem_3.5rem] items-end gap-1 text-[9px] font-semibold text-gray-400 mb-1 leading-tight"
					>
						<span>{{ periodLabel || __("This period") }}</span>
						<span class="text-center text-green-600">{{ __("Approved") }}</span>
						<span class="text-center text-red-600">{{ __("Rejected") }}</span>
						<span class="text-center text-amber-600">{{ __("Pending") }}</span>
					</div>
					<div
						v-for="row in monthAppRows"
						:key="row.key"
						class="grid grid-cols-[minmax(0,1fr)_3.5rem_3.5rem_3.5rem] items-center gap-1 py-0.5 text-[11px]"
					>
						<span class="min-w-0 truncate text-gray-700 font-medium">
							{{ __(row.label) }}
							<span class="text-gray-400 font-normal">({{ row.total }})</span>
						</span>
						<span class="text-center rounded bg-green-50 text-green-700 font-semibold py-0.5">
							{{ row.approved }}
						</span>
						<span class="text-center rounded bg-red-50 text-red-700 font-semibold py-0.5">
							{{ row.rejected }}
						</span>
						<span class="text-center rounded bg-amber-50 text-amber-700 font-semibold py-0.5">
							{{ row.pending }}
						</span>
					</div>
					<div
						v-if="leaveCounts.data?.days"
						class="text-[10px] text-gray-500 pt-0.5"
					>
						{{ __("Approved leave days") }}:
						<span class="font-semibold text-gray-700">{{ leaveCounts.data.days }}</span>
					</div>
				</div>

				<div class="w-full grid grid-cols-2 gap-2" v-if="isSelf">
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
				<div v-if="isSelf">
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
				<template v-if="isSelf">
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
								<span class="text-xs text-gray-500">
									{{ formatNepaliDate(log.time) }}
									· {{ formatDaysFromToday(log.time) }}
								</span>
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
				</template>
				</template>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, inject, markRaw, ref, onMounted, watch } from "vue"
import { createResource, createListResource, Badge, Dialog, Button, call, Autocomplete, debounce, toast } from "frappe-ui"
import { useRouter } from "vue-router"
import { IonModal } from "@ionic/vue"

import BaseLayout from "@/components/BaseLayout.vue"
import AttendanceRequestItem from "@/components/AttendanceRequestItem.vue"
import AttendanceItem from "@/components/AttendanceItem.vue"
import ShiftRequestItem from "@/components/ShiftRequestItem.vue"
import ShiftAssignmentItem from "@/components/ShiftAssignmentItem.vue"
import RequestList from "@/components/RequestList.vue"
import AttendanceCalendar from "@/components/AttendanceCalendar.vue"
import NepaliAttendanceCalendar from "@/components/NepaliAttendanceCalendar.vue"
import AttendanceDaySheet from "@/components/AttendanceDaySheet.vue"
import LiveAttendanceBoard from "@/components/LiveAttendanceBoard.vue"
import { formatNepaliDate, formatDaysFromToday, formatNepaliMonthYear } from "@/utils/nepali_date"
import { ensureNepaliDateLib } from "@/utils/nepali_calendar"
import { encodeLeaveRanges } from "@/utils/leave_ranges"
import { consumeAttendanceRefresh } from "@/utils/attendance_refresh"
import { pwaAccess } from "@/data/pwa_access"

const activeCalendar = ref("Nepali")
const attendanceView = ref("calendar")
const adCalendar = ref(null)
const bsCalendar = ref(null)
const employee = inject("$employee")
const dayjs = inject("$dayjs")
const socket = inject("$socket")
const __ = inject("$translate")
const router = useRouter()

const calendarEmployee = ref(employee.data?.name)
const employeeQuery = ref("")
const selectedEmployeeOption = ref(
	employee.data
		? {
				label: `${employee.data.employee_name} (${__("Me")})`,
				value: employee.data.name,
		  }
		: null
)

const canViewOthers = computed(() => !!pwaAccess.data?.can_view_others_calendar)
const showLiveToggle = computed(
	() => !!pwaAccess.data?.can_view_live_board || !!pwaAccess.data?.can_view_leave_board
)
const leaveBoardOnly = computed(
	() => !pwaAccess.data?.can_view_live_board && !!pwaAccess.data?.can_view_leave_board
)
const isSelf = computed(
	() => !calendarEmployee.value || calendarEmployee.value === employee.data?.name
)

const viewableEmployees = createResource({
	url: "nepal_hrms.api.pwa_access.get_calendar_viewable_employees",
	makeParams: () => ({ search_text: employeeQuery.value || undefined }),
})

const employeeOptions = computed(() => {
	const meValue = employee.data?.name
	const meLabel = employee.data?.employee_name
		? `${employee.data.employee_name} (${__("Me")})`
		: __("Me")
	const rows = viewableEmployees.data || []
	const options = rows.map((r) => ({
		label: r.value === meValue ? meLabel : r.label,
		value: r.value,
	}))
	if (meValue && !options.some((o) => o.value === meValue)) {
		options.unshift({ label: meLabel, value: meValue })
	}
	return options
})

const onEmployeeQuery = debounce((query) => {
	employeeQuery.value = query || ""
	if (canViewOthers.value) viewableEmployees.reload()
}, 300)

watch(
	() => pwaAccess.data?.can_view_others_calendar,
	(ok) => {
		if (ok) viewableEmployees.reload()
	},
	{ immediate: true }
)

watch(selectedEmployeeOption, (opt) => {
	const value =
		opt && typeof opt === "object" && opt.value !== undefined ? opt.value : opt
	if (value) calendarEmployee.value = value
})

const showDaySheet = ref(false)
const selectedDay = ref(null)
const showSandwichDialog = ref(false)
const sandwichInfo = ref(null)
const pendingLeaveRange = ref(null)

// The window is resolved server-side, from the configured payroll period, so all
// of these agree with the attendance summary and with the desk report. Doing the
// date maths here in JS is what let the dashboard drift out of step.
//
// Which period, though, is the calendar's business: these panels used to be
// pinned to whatever period contains today, so paging the calendar back left
// them describing a different month than the grid above them — reading 0
// applications for a period full of them.
const visiblePeriod = ref(null)

/** Employee plus the window, so paging cannot serve another period's cached rows. */
function periodCacheKey() {
	const p = visiblePeriod.value
	return `${calendarEmployee.value || ""}:${p ? `${p.from_date}..${p.to_date}` : "current"}`
}

function periodParams() {
	const params = { employee: calendarEmployee.value }
	if (visiblePeriod.value) {
		params.from_date = visiblePeriod.value.from_date
		params.to_date = visiblePeriod.value.to_date
	}
	return params
}

const poolSummary = createResource({
	url: "nepal_hrms.api.cnr_applications.get_late_early_pool_summary",
	makeParams: periodParams,
	auto: true,
	cache: ["hrms:late-early-pool", periodCacheKey],
})

const appCounts = createResource({
	url: "nepal_hrms.api.cnr_applications.get_cnr_application_counts",
	makeParams: periodParams,
	auto: true,
	cache: ["nepal_hrms:cnr-app-counts", periodCacheKey],
})

const leaveCounts = createResource({
	url: "nepal_hrms.api.attendance_calendar.get_leave_application_counts",
	makeParams: periodParams,
	auto: true,
	cache: ["nepal_hrms:leave-app-counts", periodCacheKey],
})

const attRequestCounts = createResource({
	url: "nepal_hrms.api.attendance_calendar.get_attendance_request_counts",
	makeParams: periodParams,
	auto: true,
	cache: ["nepal_hrms:att-request-counts", periodCacheKey],
})

function reloadPeriodPanels() {
	poolSummary.reload()
	appCounts.reload()
	leaveCounts.reload()
	attRequestCounts.reload()
}

function onCalendarPeriodChange(period) {
	if (!period?.from_date || !period?.to_date) return
	const current = visiblePeriod.value
	if (current?.from_date === period.from_date && current?.to_date === period.to_date) return
	visiblePeriod.value = period
	// On first paint the calendar reports the same period these already fetched
	// by default; refetching all four for nothing is four round trips per load.
	const fetched = poolSummary.data
	if (fetched?.from_date === period.from_date && fetched?.to_date === period.to_date) return
	reloadPeriodPanels()
}

const libLoaded = ref(0)

/** BS month naming the visible period, e.g. "Bhadra 2083". */
const periodLabel = computed(() => {
	void libLoaded.value
	const p = visiblePeriod.value
	if (!p?.to_date) return ""
	return formatNepaliMonthYear(p.to_date) || ""
})

const monthAppRows = computed(() => {
	const rows = []
	if (appCounts.data) {
		for (const key of ["late_entry", "early_exit", "out_of_office"]) {
			const d = appCounts.data[key]
			if (d) {
				rows.push({
					key,
					...d,
					label: d.doctype || __("{0} Application", [d.label]),
				})
			}
		}
	}
	if (leaveCounts.data) {
		rows.push({
			key: "leave",
			label: __("Leave Application"),
			total: leaveCounts.data.total,
			approved: leaveCounts.data.approved,
			rejected: leaveCounts.data.rejected,
			pending: leaveCounts.data.pending,
		})
	}
	if (attRequestCounts.data) {
		rows.push({
			key: "attendance_request",
			label: __("Attendance Request"),
			total: attRequestCounts.data.total,
			approved: attRequestCounts.data.approved,
			rejected: attRequestCounts.data.rejected,
			pending: attRequestCounts.data.pending,
		})
	}
	return rows
})

watch(calendarEmployee, () => {
	// A different employee may sit in a different period; let the calendar say so.
	visiblePeriod.value = null
	reloadPeriodPanels()
})

function refreshAttendanceView() {
	adCalendar.value?.reload?.()
	bsCalendar.value?.reload?.()
	reloadPeriodPanels()
	myAttendanceRequests?.reload?.()
	recentAttendance?.reload?.()
}

function onCalendarDaySelect({ date, late, early, status }) {
	if (!date) return
	selectedDay.value = {
		date,
		late: !!late,
		early: !!early,
		status: status || null,
		stamp: Date.now(),
	}
	showDaySheet.value = true
}

function onDaySheetDismiss() {
	showDaySheet.value = false
	selectedDay.value = null
}

async function onCreateLeave({ from_date, to_date, half_day, ranges }) {
	const leaveRanges = (
		ranges?.length
			? ranges
			: from_date && to_date
				? [{ from_date, to_date }]
				: []
	).filter((r) => r.from_date && r.to_date)
	if (!leaveRanges.length) return
	showDaySheet.value = false
	const singleDay =
		leaveRanges.length === 1 && leaveRanges[0].from_date === leaveRanges[0].to_date
	pendingLeaveRange.value = {
		ranges: leaveRanges,
		half_day: singleDay && half_day ? 1 : 0,
	}

	let worst = null
	let edgeWarning = null
	for (const range of leaveRanges) {
		let response = null
		try {
			response = await call("nepal_hrms.api.attendance_calendar.check_leave_sandwich", {
				from_date: range.from_date,
				to_date: range.to_date,
			})
		} catch (error) {
			console.warn("Leave sandwich precheck failed", error)
		}
		if (response?.enabled && response?.violation && !response?.escape) {
			if (!worst || (response.block && !worst.block)) {
				worst = response
			}
		} else if (response?.enabled && response?.warning && !response?.escape) {
			edgeWarning = response
		}
	}
	if (worst) {
		sandwichInfo.value = worst
		showSandwichDialog.value = true
		return
	}
	if (edgeWarning?.message) {
		toast({
			title: __("Sandwich Rule"),
			text: edgeWarning.message,
			icon: "alert-circle",
			position: "bottom-center",
		})
	}
	proceedWithLeave()
}

function proceedWithLeave() {
	showSandwichDialog.value = false
	const range = pendingLeaveRange.value
	if (!range?.ranges?.length) return
	const first = range.ranges[0]
	const query = {
		prefill: "1",
		from_date: first.from_date,
		to_date: first.to_date,
	}
	if (range.ranges.length > 1) {
		query.ranges = encodeLeaveRanges(range.ranges)
	}
	if (range.half_day) {
		query.half_day = "1"
		query.half_day_date = first.from_date
	}
	pendingLeaveRange.value = null
	router.push({ name: "LeaveApplicationFormView", query })
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
	// periodLabel reads the BS month name off window.NepaliDateLib, which only the
	// BS calendar loads — the panels are labelled in AD mode too.
	ensureNepaliDateLib().then(() => libLoaded.value++)
	if (consumeAttendanceRefresh()) refreshAttendanceView()
	useListUpdate(socket, "Attendance", () => {
		recentAttendance.reload()
		poolSummary.reload()
	})
	useListUpdate(socket, "Employee Checkin", () => recentCheckins.reload())
	useListUpdate(socket, "Late Entry Application", () => appCounts.reload())
	useListUpdate(socket, "Early Exit Application", () => appCounts.reload())
	useListUpdate(socket, "Out of Office Application", () => appCounts.reload())
	useListUpdate(socket, "Leave Application", () => refreshAttendanceView())
	useListUpdate(socket, "Attendance Request", () => {
		attRequestCounts.reload()
		myAttendanceRequests.reload()
	})
})
</script>
