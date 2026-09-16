<template>
	<div class="flex flex-col w-full gap-3" v-if="calendarEvents.data">
		<div class="flex flex-col gap-4 bg-white py-4 px-3 rounded-lg border border-gray-100 shadow-sm">
			<!-- Month Change -->
			<div class="flex flex-row justify-between items-center px-2">
				<Button
					icon="chevron-left"
					variant="ghost"
					@click="firstOfMonth = firstOfMonth.subtract(1, 'M')"
				/>
				<div class="flex items-center gap-1">
					<span class="text-base text-gray-800 font-bold">
						{{ firstOfMonth.format("MMMM") }} {{ firstOfMonth.format("YYYY") }}
					</span>
					<button
						type="button"
						class="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-semibold text-gray-600 hover:bg-gray-100"
						:title="__('Refresh')"
						:aria-label="__('Refresh')"
						:disabled="calendarEvents.loading"
						@click.stop="reloadCalendar"
					>
						<FeatherIcon
							name="refresh-cw"
							class="h-3.5 w-3.5"
							:class="calendarEvents.loading ? 'animate-spin' : ''"
						/>
						{{ __("Refresh") }}
					</button>
				</div>
				<Button
					icon="chevron-right"
					variant="ghost"
					@click="firstOfMonth = firstOfMonth.add(1, 'M')"
				/>
			</div>

			<!-- Calendar -->
			<div class="grid grid-cols-7 gap-y-2">
				<div
					v-for="day in DAYS"
					:key="day"
					class="flex justify-center text-gray-600 text-xs font-medium leading-5"
				>
					{{ day }}
				</div>
				<div v-for="n in firstOfMonth.get('d')" :key="'pad-' + n" />
				<div
					v-for="index in firstOfMonth.endOf('M').get('D')"
					:key="'day-' + index"
					class="relative flex flex-col items-center pt-2"
					@click="onDayClick(index)"
				>
					<div
						v-if="leaveDayMarks(getEventOnDate(index)).length"
						class="absolute top-0 left-1/2 -translate-x-1/2 z-10 flex gap-px"
					>
						<span
							v-for="mark in leaveDayMarks(getEventOnDate(index))"
							:key="mark"
							class="leave-mark-badge"
							:class="leaveMarkClass(mark)"
						>
							{{ mark }}
						</span>
					</div>
					<div
						class="h-9 w-9 flex rounded-lg mx-auto cursor-pointer"
						:class="[
							statusColor(getEventOnDate(index)),
							isSelected(index) ? 'ring-2 ring-blue-600 ring-offset-1' : '',
						]"
					>
						<span class="text-gray-800 text-sm font-medium m-auto">
							{{ index }}
						</span>
					</div>
					<div
						v-if="hasMarkers(getEventOnDate(index))"
						class="flex gap-0.5 mt-0.5 min-h-[14px] items-start justify-center"
					>
						<i v-if="dayMarkers(getEventOnDate(index)).leave" class="marker-dot" :class="dayMarkers(getEventOnDate(index)).pending ? 'pending' : 'leave'" />
						<i v-if="dayMarkers(getEventOnDate(index)).sandwich" class="marker-dot sandwich" />
						<span
							v-if="
								dayMarkers(getEventOnDate(index)).lateDelay ||
								dayMarkers(getEventOnDate(index)).late_app
							"
							class="marker-stack"
						>
							<i
								v-if="dayMarkers(getEventOnDate(index)).lateDelay"
								class="marker-dot late"
								:class="
									dayMarkers(getEventOnDate(index)).late_grace ? 'grace' : 'after'
								"
								:title="
									appStatusTitle(
										dayMarkers(getEventOnDate(index)).late_grace
											? __('Late (within grace)')
											: __('Late (after grace)'),
										dayMarkers(getEventOnDate(index)).late_app
									)
								"
							/>
							<i
								v-if="dayMarkers(getEventOnDate(index)).late_app"
								class="app-mark"
								:class="appStatusClass(dayMarkers(getEventOnDate(index)).late_app)"
							/>
						</span>
						<span
							v-if="
								dayMarkers(getEventOnDate(index)).earlyDelay ||
								dayMarkers(getEventOnDate(index)).early_app
							"
							class="marker-stack"
						>
							<i
								v-if="dayMarkers(getEventOnDate(index)).earlyDelay"
								class="marker-dot early"
								:class="
									dayMarkers(getEventOnDate(index)).early_grace ? 'grace' : 'after'
								"
								:title="
									appStatusTitle(
										dayMarkers(getEventOnDate(index)).early_grace
											? __('Early (within grace)')
											: __('Early (after grace)'),
										dayMarkers(getEventOnDate(index)).early_app
									)
								"
							/>
							<i
								v-if="dayMarkers(getEventOnDate(index)).early_app"
								class="app-mark"
								:class="appStatusClass(dayMarkers(getEventOnDate(index)).early_app)"
							/>
						</span>
						<span v-if="dayMarkers(getEventOnDate(index)).ooo" class="marker-stack">
							<i
								class="marker-dot ooo"
								:title="appStatusTitle(__('Out of Office'), dayMarkers(getEventOnDate(index)).ooo_app)"
							/>
							<i
								v-if="dayMarkers(getEventOnDate(index)).ooo_app"
								class="app-mark"
								:class="appStatusClass(dayMarkers(getEventOnDate(index)).ooo_app)"
							/>
						</span>
					</div>
				</div>
			</div>

			<div
				class="flex items-center justify-between gap-2 px-1 pt-1 border-t border-gray-100"
			>
				<template v-if="!selectMode">
					<span class="text-[11px] text-gray-400">{{ __("Tap a day for details") }}</span>
					<button
						v-if="isSelf"
						type="button"
						class="text-[11px] font-semibold text-blue-600 py-1"
						@click="startSelectMode"
					>
						{{ __("Select days for leave") }}
					</button>
				</template>
				<template v-else>
					<span class="text-[11px] text-gray-500">
						{{
							selectedCount
								? __("{0} day(s) selected — tap more future days", [selectedCount])
								: __("Tap future working days to select")
						}}
					</span>
					<div class="flex items-center gap-3 shrink-0">
						<button
							type="button"
							class="text-[11px] font-semibold text-gray-500 py-1"
							@click="cancelSelectMode"
						>
							{{ __("Cancel") }}
						</button>
						<button
							type="button"
							class="text-[11px] font-semibold py-1"
							:class="selectedCount ? 'text-blue-600' : 'text-gray-300 pointer-events-none'"
							@click="applyLeaveSelection"
						>
							{{ __("Apply for Leave") }}
						</button>
					</div>
				</template>
			</div>

			<hr class="border-gray-100" />

			<!-- Summary -->
			<div class="grid grid-cols-5 mx-1">
				<div v-for="status in summaryStatuses" :key="status" class="flex flex-col gap-0.5">
					<div class="flex flex-row gap-1 items-center">
						<span class="rounded-full h-2.5 w-2.5 shrink-0" :class="colorMap[status]" />
						<span class="text-gray-600 text-[11px] font-medium leading-4">
							{{ __(summaryLabels[status] || status) }}
						</span>
					</div>
					<span class="text-gray-800 text-sm font-semibold leading-5 mx-auto">
						{{ summary[status] || 0 }}
					</span>
				</div>
			</div>

			<div class="flex flex-wrap gap-x-3 gap-y-1 mx-1 text-[11px] text-gray-600">
				<span class="inline-flex items-center gap-1">
					<i class="marker-dot late grace" />{{ __("Late · grace") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<i class="marker-dot late after" />{{ __("Late · after grace") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<i class="marker-dot early grace" />{{ __("Early · grace") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<i class="marker-dot early after" />{{ __("Early · after grace") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<i class="marker-dot ooo" />{{ __("Out of Office") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<i class="app-mark approved" />{{ __("Approved application") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<i class="app-mark rejected" />{{ __("Rejected application") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<i class="app-mark draft" />{{ __("Draft application") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<i class="marker-dot sandwich" />{{ __("Sandwich") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<span class="leave-mark-badge half">1/2</span>{{ __("Half day leave") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<span class="leave-mark-badge sick">SL</span>{{ __("Sick leave") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<span class="leave-mark-badge home">HL</span>{{ __("Home leave") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<span class="leave-mark-badge lwp">LWP</span>{{ __("Leave without pay") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<span class="leave-mark-badge penalty-half">½P</span>{{ __("Half-day pool penalty") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<span class="leave-mark-badge penalty-full">1P</span>{{ __("Full-day pool penalty") }}
				</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"
import { groupContiguousDates } from "@/utils/leave_ranges"
import { leaveDayMarks, leaveMarkClass } from "@/utils/leave_marks"
import {
	appStatusClass,
	appStatusTitle,
	hasDelayGraceAfter,
	normalizeAppStatus,
} from "@/utils/app_status"

const emit = defineEmits(["select-day", "create-leave", "refresh"])

const props = defineProps({
	employee: { type: String, default: null },
})

const dayjs = inject("$dayjs")
const __ = inject("$translate")
const sessionEmployee = inject("$employee")
const isSelf = computed(
	() => !props.employee || props.employee === sessionEmployee.data?.name
)
const firstOfMonth = ref(dayjs().date(1).startOf("D"))
const todayStr = dayjs().format("YYYY-MM-DD")

const colorMap = {
	Present: "bg-green-200 ring-1 ring-inset ring-green-400",
	"Work From Home": "bg-teal-200 ring-1 ring-inset ring-teal-400",
	"Half Day": "bg-yellow-200 ring-1 ring-inset ring-yellow-400",
	Absent: "bg-red-200 ring-1 ring-inset ring-red-400",
	"On Leave": "bg-blue-200 ring-1 ring-inset ring-blue-400",
	"Leave Pending": "bg-orange-100 ring-1 ring-inset ring-orange-400",
	"Leave Rejected": "bg-rose-100 ring-1 ring-inset ring-rose-300",
	Holiday: "bg-gray-200 ring-1 ring-inset ring-gray-300",
	"Weekly Off": "bg-gray-200 ring-1 ring-inset ring-gray-300",
}

const summaryStatuses = ["Present", "Half Day", "Absent", "On Leave", "Leave Pending"]
const summaryLabels = {
	"On Leave": "Leave",
	"Leave Pending": "Pending",
}
const selectMode = ref(false)
const selectedDates = ref(new Set())
const selectedCount = computed(() => selectedDates.value.size)

const dayStatus = (info) => {
	if (!info) return null
	if (typeof info === "string") return info
	return info.status || null
}

const dayMarkers = (info) => {
	if (!info || typeof info === "string") {
		return {
			leave: info === "On Leave",
			pending: false,
			rejected: false,
			sandwich: false,
			lateDelay: false,
			late_grace: false,
			late_after: false,
			late_app: "",
			earlyDelay: false,
			early_grace: false,
			early_after: false,
			early_app: "",
			ooo: false,
			oooDelay: false,
			ooo_app: "",
		}
	}
	const status = info.status || null
	const app = info.leave_app_status
	const leave =
		!!info.leave ||
		status === "On Leave" ||
		status === "Leave Pending" ||
		status === "Leave Rejected"
	const lateDelay = hasDelayGraceAfter(info, "late")
	const earlyDelay = hasDelayGraceAfter(info, "early")
	const late_app = normalizeAppStatus(info.late_app_status)
	const early_app = normalizeAppStatus(info.early_app_status)
	const ooo_app = normalizeAppStatus(info.ooo_app_status)
	return {
		leave,
		pending: leave && (app === "Pending" || status === "Leave Pending"),
		rejected: leave && (app === "Rejected" || status === "Leave Rejected"),
		sandwich: !!info.sandwich,
		lateDelay: lateDelay.delay,
		late_grace: lateDelay.grace,
		late_after: lateDelay.after,
		late_app,
		earlyDelay: earlyDelay.delay,
		early_grace: earlyDelay.grace,
		early_after: earlyDelay.after,
		early_app,
		ooo: !!(info.ooo_required || ooo_app),
		oooDelay: !!info.ooo_required,
		ooo_app,
	}
}

function resolvePaintStatus(info) {
	const status = dayStatus(info)
	if (status && colorMap[status]) return status
	const m = dayMarkers(info)
	if (!m.leave) return status
	if (m.rejected) return "Leave Rejected"
	if (m.pending) return "Leave Pending"
	return "On Leave"
}

const hasMarkers = (info) => {
	const m = dayMarkers(info)
	return (
		m.leave ||
		m.sandwich ||
		m.lateDelay ||
		m.earlyDelay ||
		m.oooDelay ||
		m.late_app ||
		m.early_app ||
		m.ooo_app
	)
}

const isDaySelectable = (date) => {
	if (!date || date <= todayStr) return false
	const status = dayStatus(calendarEvents.data?.[date])
	return !["Holiday", "Weekly Off", "On Leave", "Leave Pending"].includes(status)
}

function startSelectMode() {
	selectMode.value = true
}

function cancelSelectMode() {
	selectMode.value = false
	selectedDates.value = new Set()
}

function isSelected(index) {
	return selectedDates.value.has(firstOfMonth.value.date(index).format("YYYY-MM-DD"))
}

function toggleDaySelection(date) {
	const next = new Set(selectedDates.value)
	if (next.has(date)) next.delete(date)
	else next.add(date)
	selectedDates.value = next
}

function applyLeaveSelection() {
	if (!selectedDates.value.size) return
	const ranges = groupContiguousDates([...selectedDates.value])
	if (!ranges.length) return
	emit("create-leave", {
		from_date: ranges[0].from_date,
		to_date: ranges[ranges.length - 1].to_date,
		ranges,
	})
	cancelSelectMode()
}

const onDayClick = (index) => {
	const date = firstOfMonth.value.date(index).format("YYYY-MM-DD")
	if (selectMode.value) {
		if (isDaySelectable(date)) toggleDaySelection(date)
		return
	}
	const info = getEventOnDate(index)
	const m = dayMarkers(info)
	emit("select-day", {
		date,
		late: m.lateDelay,
		early: m.earlyDelay,
		status: resolvePaintStatus(info),
	})
}

const statusColor = (info) => {
	const status = resolvePaintStatus(info)
	return status ? colorMap[status] : ""
}

const summary = computed(() => {
	const counts = {}
	if (!calendarEvents.data) return counts

	for (const info of Object.values(calendarEvents.data)) {
		let status = resolvePaintStatus(info)
		if (!status) continue
		if (status === "Work From Home") status = "Present"
		if (!summaryStatuses.includes(status)) continue
		counts[status] = (counts[status] || 0) + 1
	}

	return counts
})

watch(
	() => firstOfMonth.value,
	() => {
		calendarEvents.fetch()
	}
)

const getEventOnDate = (date) => {
	return calendarEvents.data?.[firstOfMonth.value.date(date).format("YYYY-MM-DD")]
}

const getFirstLetter = (s) => Array.from(s.trim())[0]

const DAYS = [
	getFirstLetter(__("Sunday")),
	getFirstLetter(__("Monday")),
	getFirstLetter(__("Tuesday")),
	getFirstLetter(__("Wednesday")),
	getFirstLetter(__("Thursday")),
	getFirstLetter(__("Friday")),
	getFirstLetter(__("Saturday")),
]

const calendarEvents = createResource({
	url: "nepal_hrms.api.attendance_calendar.get_attendance_calendar_details",
	auto: true,
	makeParams() {
		const params = {
			from_date: firstOfMonth.value.format("YYYY-MM-DD"),
			to_date: firstOfMonth.value.endOf("M").format("YYYY-MM-DD"),
		}
		if (props.employee) params.employee = props.employee
		return params
	},
})

async function reloadCalendar() {
	await calendarEvents.reload()
	emit("refresh")
}

defineExpose({ reload: reloadCalendar })

watch(
	() => props.employee,
	() => {
		cancelSelectMode()
		calendarEvents.reload()
	}
)
</script>

<style scoped>
.marker-dot {
	display: inline-block;
	width: 5px;
	height: 5px;
	border-radius: 50%;
	flex-shrink: 0;
}

.marker-dot.leave {
	background-color: #2563eb;
}

.marker-dot.pending {
	background-color: #d97706;
}

.marker-dot.late.after,
.marker-dot.late:not(.grace) {
	background-color: #ea580c;
}

.marker-dot.early.after,
.marker-dot.early:not(.grace) {
	background-color: #7c3aed;
}

.marker-dot.late.grace {
	background-color: #fff;
	box-shadow: inset 0 0 0 1.5px #fb923c;
}

.marker-dot.early.grace {
	background-color: #fff;
	box-shadow: inset 0 0 0 1.5px #a78bfa;
}

.marker-dot.ooo {
	background-color: #0f766e;
}

.marker-dot.sandwich {
	background-color: #be123c;
}

.marker-stack {
	display: inline-flex;
	flex-direction: column;
	align-items: center;
	line-height: 1;
}

.app-mark {
	display: inline-block;
	font-size: 8px;
	font-weight: 800;
	line-height: 1;
	font-style: normal;
}

.app-mark.approved {
	color: #16a34a;
}

.app-mark.approved::before {
	content: "✓";
}

.app-mark.rejected {
	color: #dc2626;
}

.app-mark.rejected::before {
	content: "✕";
}

.app-mark.draft {
	color: #d97706;
}

.app-mark.draft::before {
	content: "○";
}

.leave-mark-badge {
	display: inline-block;
	font-size: 8px;
	font-weight: 700;
	line-height: 1;
	padding: 1px 2px;
	border-radius: 3px;
	letter-spacing: -0.02em;
	white-space: nowrap;
}

.leave-mark-badge.half {
	color: #1d4ed8;
	background: #dbeafe;
}

.leave-mark-badge.sick {
	color: #9a3412;
	background: #ffedd5;
}

.leave-mark-badge.home {
	color: #065f46;
	background: #d1fae5;
}

.leave-mark-badge.penalty-half {
	background: #f59e0b;
	color: #451a03;
}
.leave-mark-badge.penalty-full {
	background: #dc2626;
	color: #fff7ed;
}
.leave-mark-badge.lwp {
	color: #334155;
	background: #e2e8f0;
}
</style>
