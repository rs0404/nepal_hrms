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
				<span class="status-swatch" style="background:#dcfce7;box-shadow:inset 0 0 0 1px #4ade80" />
				{{ __("Present") }}
			</span>
			<span class="inline-flex items-center gap-1">
				<span class="status-swatch" style="background:#fef9c3;box-shadow:inset 0 0 0 1px #facc15" />
				{{ __("Half Day") }}
			</span>
			<span class="inline-flex items-center gap-1">
				<span class="status-swatch" style="background:#dbeafe;box-shadow:inset 0 0 0 1px #60a5fa" />
				{{ __("Approved") }}
			</span>
			<span class="inline-flex items-center gap-1">
				<span
					class="status-swatch"
					style="background:#fff7ed;box-shadow:inset 0 0 0 1px #fb923c;background-image:repeating-linear-gradient(-45deg,transparent,transparent 2px,rgba(245,158,11,.2) 2px,rgba(245,158,11,.2) 4px)"
				/>
				{{ __("Pending") }}
			</span>
			<span class="inline-flex items-center gap-1">
				<span class="status-swatch" style="background:#fee2e2;box-shadow:inset 0 0 0 1px #f87171" />
				{{ __("Absent") }}
			</span>
			<span class="inline-flex items-center gap-1">
				<i class="marker-dot late" />{{ __("Late") }}
			</span>
			<span class="inline-flex items-center gap-1">
				<i class="marker-dot early" />{{ __("Early") }}
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
		</div>
	</div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, inject, watch, computed, nextTick, toRaw } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"
import { ensureNepaliCalendar } from "@/utils/nepali_calendar"
import { groupContiguousDates } from "@/utils/leave_ranges"
import { leaveDayMarks, leaveMarkClass } from "@/utils/leave_marks"

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
			late: false,
			early: false,
		}
	}
	const status = info.status || null
	const app = info.leave_app_status
	const leave =
		!!info.leave ||
		status === "On Leave" ||
		status === "Leave Pending" ||
		status === "Leave Rejected"
	return {
		leave,
		pending: leave && (app === "Pending" || status === "Leave Pending"),
		rejected: leave && (app === "Rejected" || status === "Leave Rejected"),
		sandwich: !!info.sandwich,
		late: !!info.late,
		early: !!info.early,
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

function syncLeaveSelection() {
	const root = calendarContainer.value
	if (!root) return
	root.querySelectorAll(".days-grid .day[data-ad]").forEach((button) => {
		const date = button.getAttribute("data-ad")
		button.classList.toggle("leave-selected", selectedDates.value.has(date))
		const marks = leaveDayMarks(attendanceEvents.data?.[date])
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
				late: m.late,
				early: m.early,
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

.marker-dot.late {
	background-color: #ea580c;
}

.marker-dot.early {
	background-color: #7c3aed;
}

.marker-dot.sandwich {
	background-color: #be123c;
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

:deep(.leave-mark-badge.lwp) {
	color: #334155;
	background: #e2e8f0;
}
</style>
