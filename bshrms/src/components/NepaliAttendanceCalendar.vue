<template>
	<div class="flex flex-col w-full gap-3">
		<div class="bg-white rounded-lg p-2 shadow-sm border border-gray-100">
			<div class="flex items-center justify-end px-2 pt-1 pb-0.5">
				<button
					type="button"
					class="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-semibold text-gray-600 hover:bg-gray-100"
					:title="__('Refresh')"
					:aria-label="__('Refresh')"
					:disabled="attendanceEvents.loading"
					@click="reloadCalendar"
				>
					<FeatherIcon
						name="refresh-cw"
						class="h-3.5 w-3.5"
						:class="attendanceEvents.loading ? 'animate-spin' : ''"
					/>
					{{ __("Refresh") }}
				</button>
			</div>
			<div ref="calendarContainer"></div>

			<div
				class="flex items-center justify-between gap-2 px-2 py-1.5 border-t"
				:class="selectMode ? 'bg-blue-50 border-blue-200 rounded-b-md' : 'border-gray-100'"
			>
				<template v-if="!selectMode">
					<span class="text-[11px] text-gray-400">{{ __("Tap a day for details") }}</span>
					<div class="flex items-center gap-2 shrink-0">
						<button
							v-if="isSelf"
							type="button"
							class="text-[11px] font-semibold text-blue-600 py-1"
							@click="startSelectMode"
						>
							{{ __("Select days for leave") }}
						</button>
					</div>
				</template>
				<template v-else>
					<span class="text-[11px] font-medium text-blue-800">
						{{
							selectedCount
								? __("{0} day(s) selected — tap more to add", [selectedCount])
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
							:class="selectedCount ? 'text-blue-700' : 'text-blue-300 pointer-events-none'"
							@click="applyLeaveSelection"
						>
							{{ __("Apply for Leave") }}
						</button>
					</div>
				</template>
			</div>
		</div>

		<!-- Status summary — visible month only -->
		<div class="grid grid-cols-5 gap-1 mx-1" v-if="hasSummary">
			<div v-for="status in summaryStatuses" :key="status" class="flex flex-col gap-0.5">
				<div class="flex flex-row gap-1 items-center">
					<span
						class="h-2.5 w-2.5 shrink-0 rounded-md"
						:style="{ backgroundColor: STATUS_FILL[status]?.backgroundColor }"
					/>
					<span class="text-gray-600 text-[11px] font-medium leading-4 whitespace-nowrap">
						{{ __(summaryLabels[status] || status) }}
					</span>
				</div>
				<span class="text-gray-800 text-sm font-semibold leading-5 mx-auto">
					{{ summary[status] || 0 }}
				</span>
			</div>
		</div>
		<div v-else-if="attendanceEvents.loading" class="text-xs text-gray-400 mx-1">
			{{ __("Loading attendance…") }}
		</div>
		<div
			v-else-if="attendanceEvents.error"
			class="text-xs text-red-500 mx-1"
		>
			{{ __("Could not load attendance markers") }}
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
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, inject, watch, computed, nextTick, toRaw } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"
import { ensureNepaliCalendar } from "@/utils/nepali_calendar"
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

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const sessionEmployee = inject("$employee")
const isSelf = computed(
	() => !props.employee || props.employee === sessionEmployee.data?.name
)
const calendarContainer = ref(null)
const todayStr = dayjs().format("YYYY-MM-DD")
const visibleRange = ref({
	from_date: dayjs().subtract(20, "day").format("YYYY-MM-DD"),
	to_date: dayjs().add(15, "day").format("YYYY-MM-DD"),
})
const selectMode = ref(false)
const selectedDates = ref(new Set())
const selectedCount = computed(() => selectedDates.value.size)

const STATUS_FILL = {
	Present: { backgroundColor: "#dcfce7", boxShadow: "inset 0 0 0 1.5px #4ade80" },
	"Work From Home": { backgroundColor: "#ccfbf1", boxShadow: "inset 0 0 0 1.5px #2dd4bf" },
	"Half Day": { backgroundColor: "#fef9c3", boxShadow: "inset 0 0 0 1.5px #facc15" },
	Absent: { backgroundColor: "#fee2e2", boxShadow: "inset 0 0 0 1.5px #f87171" },
	"On Leave": { backgroundColor: "#dbeafe", boxShadow: "inset 0 0 0 1.5px #60a5fa" },
	"Leave Pending": { backgroundColor: "#fed7aa", boxShadow: "inset 0 0 0 1.5px #fb923c" },
	"Leave Rejected": { backgroundColor: "#ffe4e6", boxShadow: "inset 0 0 0 1.5px #fda4af" },
	Holiday: { backgroundColor: "#f3e8ff", boxShadow: "inset 0 0 0 1.5px #d8b4fe" },
	"Weekly Off": { backgroundColor: "#f3e8ff", boxShadow: "inset 0 0 0 1.5px #d8b4fe" },
}

const PAINTABLE = new Set(Object.keys(STATUS_FILL))
const summaryStatuses = ["Present", "Half Day", "Absent", "On Leave", "Leave Pending"]
const summaryLabels = {
	"On Leave": "Leave",
	"Leave Pending": "Pending",
}

const attendanceEvents = createResource({
	url: "nepal_hrms.api.attendance_calendar.get_attendance_calendar_details",
	auto: true,
	makeParams() {
		const params = {
			from_date: dayjs().subtract(6, "month").startOf("month").format("YYYY-MM-DD"),
			to_date: dayjs().add(3, "month").endOf("month").format("YYYY-MM-DD"),
		}
		if (props.employee) params.employee = props.employee
		return params
	},
	onSuccess() {
		syncLeaveSelection()
	},
})

async function reloadCalendar() {
	await attendanceEvents.reload()
	await renderCalendar()
	emit("refresh")
}

defineExpose({ reload: reloadCalendar })

watch(
	() => props.employee,
	() => {
		cancelSelectMode()
		attendanceEvents.reload()
	}
)

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
		oooDelay: !!info.ooo_required,
		ooo_app,
	}
}

function resolvePaintStatus(info) {
	const status = dayStatus(info)
	if (PAINTABLE.has(status)) return status
	const m = dayMarkers(info)
	if (!m.leave) return status
	if (m.rejected) return "Leave Rejected"
	if (m.pending) return "Leave Pending"
	return "On Leave"
}

const summary = computed(() => {
	if (!attendanceEvents.data) return {}
	const from = visibleRange.value.from_date
	const to = visibleRange.value.to_date
	const counts = {}
	for (const [date, info] of Object.entries(attendanceEvents.data)) {
		if (from && date < from) continue
		if (to && date > to) continue
		let status = resolvePaintStatus(info)
		if (!status || status === "Holiday" || status === "Weekly Off" || status === "Leave Rejected")
			continue
		if (status === "Work From Home") status = "Present"
		if (!summaryStatuses.includes(status)) continue
		counts[status] = (counts[status] || 0) + 1
	}
	return counts
})

const hasSummary = computed(() => Object.keys(summary.value).length > 0)

const isDaySelectable = (ad) => {
	if (!ad || ad <= todayStr) return false
	const status = dayStatus(attendanceEvents.data?.[ad])
	return !["Holiday", "Weekly Off", "On Leave", "Leave Pending"].includes(status)
}

function startSelectMode() {
	selectMode.value = true
}

function cancelSelectMode() {
	selectMode.value = false
	selectedDates.value = new Set()
	syncLeaveSelection()
}

function toggleDaySelection(ad) {
	const next = new Set(selectedDates.value)
	if (next.has(ad)) next.delete(ad)
	else next.add(ad)
	selectedDates.value = next
	syncLeaveSelection()
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

function ensureNepaliMarker(button, kind, shouldShow, title) {
	let wrap = button.querySelector(".day-markers")
	let el = wrap?.querySelector(`.${kind}`)
	if (!shouldShow) {
		el?.remove()
		if (wrap && !wrap.querySelector(".marker")) {
			wrap.remove()
			button.classList.remove("has-markers")
		}
		return null
	}
	if (el) return el
	if (!wrap) {
		wrap = document.createElement("span")
		wrap.className = "day-markers"
		wrap.setAttribute("aria-hidden", "true")
		button.appendChild(wrap)
		button.classList.add("has-markers")
	}
	el = document.createElement("i")
	el.className = `marker ${kind}`
	el.title = title
	wrap.appendChild(el)
	return el
}

function applyNepaliAppMark(el, status, title) {
	el.classList.toggle("app-approved", status === "Approved")
	el.classList.toggle("app-rejected", status === "Rejected")
	el.classList.toggle("app-draft", status === "Draft")
	if (title) el.setAttribute("title", title)
}

function syncNepaliAppOnlyMark(button, className, show, status, kind) {
	let el = button.querySelector(`.${className}`)
	if (!show || !status) {
		el?.remove()
		return
	}
	if (!el) {
		el = document.createElement("i")
		el.className = `${className} app-mark ${appStatusClass(status)}`
		el.setAttribute("aria-hidden", "true")
		button.appendChild(el)
	} else {
		el.className = `${className} app-mark ${appStatusClass(status)}`
	}
	el.setAttribute("title", appStatusTitle(kind, status))
}

function syncLeaveSelection() {
	const root = calendarContainer.value
	if (!root) return
	root.querySelectorAll(".days-grid .day[data-ad]").forEach((button) => {
		const date = button.getAttribute("data-ad")
		const info = attendanceEvents.data?.[date]
		button.classList.toggle("leave-selected", selectedDates.value.has(date))
		const delay = dayMarkers(info)
		const lateDot = ensureNepaliMarker(button, "late", delay.lateDelay, "Late")
		if (lateDot) {
			lateDot.classList.toggle("grace", delay.late_grace)
			lateDot.classList.toggle("after", delay.late_after)
			applyNepaliAppMark(
				lateDot,
				delay.late_app,
				appStatusTitle(
					delay.late_grace
						? "Late (within grace)"
						: delay.late_after
							? "Late (after grace)"
							: "Late",
					delay.late_app
				)
			)
		}
		syncNepaliAppOnlyMark(button, "late-app", delay.late_app && !delay.lateDelay, delay.late_app, "Late")
		const earlyDot = ensureNepaliMarker(button, "early", delay.earlyDelay, "Early exit")
		if (earlyDot) {
			earlyDot.classList.toggle("grace", delay.early_grace)
			earlyDot.classList.toggle("after", delay.early_after)
			applyNepaliAppMark(
				earlyDot,
				delay.early_app,
				appStatusTitle(
					delay.early_grace
						? "Early (within grace)"
						: delay.early_after
							? "Early (after grace)"
							: "Early exit",
					delay.early_app
				)
			)
		}
		const oooDot = ensureNepaliMarker(button, "ooo", delay.oooDelay, "Out of office")
		if (oooDot) {
			applyNepaliAppMark(oooDot, delay.ooo_app, appStatusTitle("Out of office", delay.ooo_app))
		}
		syncNepaliAppOnlyMark(
			button,
			"early-app",
			delay.early_app && !delay.earlyDelay,
			delay.early_app,
			"Early exit"
		)
		syncNepaliAppOnlyMark(
			button,
			"ooo-app",
			delay.ooo_app && !delay.oooDelay,
			delay.ooo_app,
			"Out of office"
		)
		const marks = leaveDayMarks(info)
		let wrap = button.querySelector(".leave-marks")
		if (!marks.length) {
			wrap?.remove()
			return
		}
		if (!wrap) {
			wrap = document.createElement("span")
			wrap.className = "leave-marks"
			wrap.setAttribute("aria-hidden", "true")
			button.appendChild(wrap)
		}
		wrap.replaceChildren(
			...marks.map((mark) => {
				const el = document.createElement("span")
				el.className = `leave-mark-badge ${leaveMarkClass(mark)}`
				el.textContent = mark
				return el
			})
		)
	})
}

const handleMonthChange = (range) => {
	if (!range?.from_date || !range?.to_date) return
	visibleRange.value = {
		from_date: range.from_date,
		to_date: range.to_date,
	}
	requestAnimationFrame(() => syncLeaveSelection())
	setTimeout(syncLeaveSelection, 80)
}

const renderCalendar = async () => {
	await ensureNepaliCalendar()
	await nextTick()
	if (!calendarContainer.value || !window.NepaliCalendarLib) return

	const events = attendanceEvents.data ? { ...toRaw(attendanceEvents.data) } : {}
	window.NepaliCalendarLib.render(calendarContainer.value, {
		events,
		onSelect: (nepaliDate) => {
			if (!nepaliDate) return
			const ad = nepaliDate.format({ format: "YYYY-MM-DD", calendar: "AD" })
			if (selectMode.value) {
				if (isDaySelectable(ad)) toggleDaySelection(ad)
				return
			}
			const info = attendanceEvents.data?.[ad]
			const m = dayMarkers(info)
			const status = resolvePaintStatus(info)
			emit("select-day", {
				date: ad,
				late: m.lateDelay,
				early: m.earlyDelay,
				status,
			})
		},
		onMonthChange: handleMonthChange,
	})
	requestAnimationFrame(() => syncLeaveSelection())
	setTimeout(syncLeaveSelection, 80)
}

onMounted(() => {
	renderCalendar()
})

onBeforeUnmount(() => {
	if (calendarContainer.value && window.NepaliCalendarLib) {
		window.NepaliCalendarLib.unmount(calendarContainer.value)
	}
})

watch(selectMode, () => {
	nextTick(() => syncLeaveSelection())
})

watch(
	() => attendanceEvents.data,
	() => {
		renderCalendar()
	}
)
</script>

<style scoped>
:deep(.calendar-wrapper) {
	@apply w-full border-none shadow-none max-w-none;
}

:deep(.days-grid) {
	gap: 2px;
}

:deep(.days-grid .day) {
	overflow: visible;
	padding: 5px 2px 10px;
}

:deep(.days-grid .day .ad) {
	left: auto;
	right: 7px;
	bottom: 5px;
	transform: none;
	font-size: 0.58rem;
	opacity: 0.65;
}

.status-swatch {
	display: inline-block;
	width: 10px;
	height: 10px;
	border-radius: 3px;
	flex-shrink: 0;
}

.marker-dot {
	display: inline-block;
	width: 6px;
	height: 6px;
	border-radius: 50%;
	flex-shrink: 0;
}

.marker-dot.late.after,
.marker-dot.late:not(.grace),
:deep(.days-grid .day .marker.late.after),
:deep(.days-grid .day .marker.late:not(.grace)) {
	background-color: #ea580c;
}

.marker-dot.early.after,
.marker-dot.early:not(.grace),
:deep(.days-grid .day .marker.early.after),
:deep(.days-grid .day .marker.early:not(.grace)) {
	background-color: #7c3aed;
}

.marker-dot.late.grace,
:deep(.days-grid .day .marker.late.grace) {
	background-color: #fff !important;
	box-shadow: inset 0 0 0 1.5px #fb923c !important;
}

.marker-dot.early.grace,
:deep(.days-grid .day .marker.early.grace) {
	background-color: #fff !important;
	box-shadow: inset 0 0 0 1.5px #a78bfa !important;
}

.marker-dot.ooo {
	background-color: #0f766e;
}

.marker-dot.sandwich {
	background-color: #be123c;
}

.app-mark {
	display: inline-block;
	font-size: 8px;
	font-weight: 800;
	line-height: 1;
	font-style: normal;
}

:deep(.days-grid .day .marker.late),
:deep(.days-grid .day .marker.early),
:deep(.days-grid .day .marker.ooo) {
	position: relative;
}

:deep(.days-grid .day .marker.app-approved),
:deep(.days-grid .day .marker.app-rejected),
:deep(.days-grid .day .marker.app-draft) {
	margin-bottom: 7px;
}

.app-mark.approved,
:deep(.days-grid .day .marker.app-approved)::after {
	color: #16a34a;
}

.app-mark.approved::before {
	content: "✓";
}

.app-mark.rejected,
:deep(.days-grid .day .marker.app-rejected)::after {
	color: #dc2626;
}

.app-mark.rejected::before {
	content: "✕";
}

.app-mark.draft,
:deep(.days-grid .day .marker.app-draft)::after {
	color: #d97706;
}

.app-mark.draft::before {
	content: "○";
}

:deep(.days-grid .day .marker.app-approved)::after,
:deep(.days-grid .day .marker.app-rejected)::after,
:deep(.days-grid .day .marker.app-draft)::after {
	position: absolute;
	top: calc(100% + 1px);
	left: 50%;
	transform: translateX(-50%);
	font-size: 8px;
	font-weight: 800;
	font-style: normal;
	line-height: 1;
}

:deep(.days-grid .day .marker.app-approved)::after {
	content: "✓";
}

:deep(.days-grid .day .marker.app-rejected)::after {
	content: "✕";
}

:deep(.days-grid .day .marker.app-draft)::after {
	content: "○";
}

:deep(.days-grid .day .late-app),
:deep(.days-grid .day .early-app),
:deep(.days-grid .day .ooo-app) {
	position: absolute;
	top: 4px;
	right: 5px;
	z-index: 2;
	pointer-events: none;
}

:deep(.days-grid .day .leave-marks) {
	position: absolute;
	top: 2px;
	left: 2px;
	z-index: 3;
	display: flex;
	gap: 1px;
	pointer-events: none;
}

:deep(.leave-mark-badge) {
	display: inline-block;
	font-size: 8px;
	font-weight: 700;
	line-height: 1;
	padding: 1px 2px;
	border-radius: 3px;
	letter-spacing: -0.02em;
	white-space: nowrap;
}

:deep(.leave-mark-badge.half) {
	color: #1d4ed8;
	background: #dbeafe;
}

:deep(.leave-mark-badge.sick) {
	color: #9a3412;
	background: #ffedd5;
}

:deep(.leave-mark-badge.home) {
	color: #065f46;
	background: #d1fae5;
}

:deep(.leave-mark-badge.penalty-half) {
	background: #f59e0b;
	color: #451a03;
}
:deep(.leave-mark-badge.penalty-full) {
	background: #dc2626;
	color: #fff7ed;
}
:deep(.leave-mark-badge.lwp) {
	color: #334155;
	background: #e2e8f0;
}
</style>
