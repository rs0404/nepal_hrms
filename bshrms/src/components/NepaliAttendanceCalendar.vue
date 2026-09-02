<template>
	<div class="flex flex-col w-full gap-3">
		<div class="bg-white rounded-lg p-2 shadow-sm border border-gray-100">
			<div ref="calendarContainer"></div>

			<div
				class="flex items-center justify-between gap-2 px-2 pt-2 pb-1 border-t border-gray-100"
			>
				<template v-if="!selectMode">
					<span class="text-[11px] text-gray-400">{{ __("Tap a day for details") }}</span>
					<button
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
		</div>

		<!-- Status summary — visible month only -->
		<div class="grid grid-cols-4 gap-1 mx-1" v-if="hasSummary">
			<div v-for="status in summaryStatuses" :key="status" class="flex flex-col gap-0.5">
				<div class="flex flex-row gap-1 items-center">
					<span
						class="h-2.5 w-2.5 shrink-0 rounded-md"
						:style="{ backgroundColor: STATUS_FILL[status]?.backgroundColor }"
					/>
					<span class="text-gray-600 text-[11px] font-medium leading-4 whitespace-nowrap">
						{{ __(status) }}
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
				{{ __("Leave") }}
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
		</div>
	</div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, inject, watch, computed, nextTick } from "vue"
import { createResource } from "frappe-ui"

const emit = defineEmits(["select-day", "create-leave"])

const __ = inject("$translate")
const dayjs = inject("$dayjs")
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
	Holiday: { backgroundColor: "#f3f4f6", boxShadow: "inset 0 0 0 1.5px #d1d5db" },
	"Weekly Off": { backgroundColor: "#f3f4f6", boxShadow: "inset 0 0 0 1.5px #d1d5db" },
}

const summaryStatuses = ["Present", "Half Day", "Absent", "On Leave"]

const attendanceEvents = createResource({
	url: "nepal_hrms.api.attendance_calendar.get_attendance_calendar_details",
	auto: true,
	makeParams() {
		// Keep range modest so holiday resolution stays fast/reliable
		return {
			from_date: dayjs().subtract(6, "month").startOf("month").format("YYYY-MM-DD"),
			to_date: dayjs().add(3, "month").endOf("month").format("YYYY-MM-DD"),
		}
	},
	onSuccess() {
		paintAttendanceDays()
		syncLeaveSelection()
	},
})

const dayStatus = (info) => {
	if (!info) return null
	if (typeof info === "string") return info
	return info.status || null
}

const dayMarkers = (info) => {
	if (!info || typeof info === "string") {
		return { leave: info === "On Leave", late: false, early: false }
	}
	return {
		leave: !!info.leave || info.status === "On Leave",
		late: !!info.late,
		early: !!info.early,
	}
}

const summary = computed(() => {
	if (!attendanceEvents.data) return {}
	const from = visibleRange.value.from_date
	const to = visibleRange.value.to_date
	const counts = {}
	for (const [date, info] of Object.entries(attendanceEvents.data)) {
		if (from && date < from) continue
		if (to && date > to) continue
		let status = dayStatus(info)
		if (!status || status === "Holiday" || status === "Weekly Off") continue
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
	const sorted = [...selectedDates.value].sort()
	emit("create-leave", { from_date: sorted[0], to_date: sorted[sorted.length - 1] })
	cancelSelectMode()
}

function syncLeaveSelection() {
	const root = calendarContainer.value
	if (!root) return
	root.querySelectorAll(".days-grid .day[data-ad]").forEach((button) => {
		const date = button.getAttribute("data-ad")
		button.classList.toggle("leave-selected", selectedDates.value.has(date))
	})
}

const handleMonthChange = (range) => {
	if (!range?.from_date || !range?.to_date) return
	visibleRange.value = {
		from_date: range.from_date,
		to_date: range.to_date,
	}
	requestAnimationFrame(() => {
		paintAttendanceDays()
		syncLeaveSelection()
	})
	setTimeout(() => {
		paintAttendanceDays()
		syncLeaveSelection()
	}, 80)
}

function clearDayPaint(btn) {
	// Color fill is CSS ::before — only sync classes / markers here
	btn.style.backgroundColor = ""
	btn.style.boxShadow = ""
	btn.style.borderRadius = ""
	btn.removeAttribute("data-painted-status")
	const markers = btn.querySelector(":scope > .day-markers")
	if (markers) markers.remove()
	;[...btn.classList].forEach((c) => {
		if (c.startsWith("status-") || c === "has-markers") btn.classList.remove(c)
	})
}

function paintAttendanceDays() {
	const root = calendarContainer.value
	const events = attendanceEvents.data
	if (!root || !events) return

	const buttons = root.querySelectorAll(".days-grid .day[data-ad]")
	if (!buttons.length) {
		// Old calendar build without data-ad — try again shortly after React paints
		setTimeout(() => {
			const retry = root.querySelectorAll(".days-grid .day[data-ad]")
			if (retry.length) paintAttendanceDays()
		}, 50)
		return
	}

	buttons.forEach((btn) => {
		clearDayPaint(btn)
		const key = btn.getAttribute("data-ad")
		const info = events[key]
		if (!info) return

		const status = dayStatus(info)
		if (status && STATUS_FILL[status]) {
			btn.dataset.paintedStatus = status
			btn.classList.add(
				`status-${String(status).toLowerCase().replace(/ /g, "-")}`
			)
		}

		const m = dayMarkers(info)
		if (m.leave || m.late || m.early) {
			btn.classList.add("has-markers")
			const wrap = document.createElement("span")
			wrap.className = "day-markers"
			wrap.setAttribute("aria-hidden", "true")
			if (m.leave) {
				const i = document.createElement("i")
				i.className = "marker leave"
				i.title = "Leave"
				wrap.appendChild(i)
			}
			if (m.late) {
				const i = document.createElement("i")
				i.className = "marker late"
				i.title = "Late"
				wrap.appendChild(i)
			}
			if (m.early) {
				const i = document.createElement("i")
				i.className = "marker early"
				i.title = "Early exit"
				wrap.appendChild(i)
			}
			btn.appendChild(wrap)
		}
	})
	syncLeaveSelection()
}

const renderCalendar = async () => {
	await nextTick()
	if (!calendarContainer.value || !window.NepaliCalendarLib) return

	window.NepaliCalendarLib.render(calendarContainer.value, {
		events: attendanceEvents.data || {},
		onSelect: (nepaliDate) => {
			if (!nepaliDate) return
			const ad = nepaliDate.format({ format: "YYYY-MM-DD", calendar: "AD" })
			if (selectMode.value) {
				if (isDaySelectable(ad)) toggleDaySelection(ad)
				return
			}
			const info = attendanceEvents.data?.[ad]
			const m = dayMarkers(info)
			const status = dayStatus(info)
			emit("select-day", {
				date: ad,
				late: m.late,
				early: m.early,
				status,
			})
		},
		onMonthChange: handleMonthChange,
	})
	// Paint after React commit
	requestAnimationFrame(() => paintAttendanceDays())
	setTimeout(paintAttendanceDays, 80)
}

onMounted(() => {
	renderCalendar()
})

onBeforeUnmount(() => {
	if (calendarContainer.value && window.NepaliCalendarLib) {
		window.NepaliCalendarLib.unmount(calendarContainer.value)
	}
})

watch(
	() => attendanceEvents.data,
	() => {
		renderCalendar()
	},
	{ deep: true }
)
</script>

<style scoped>
:deep(.calendar-wrapper) {
	@apply w-full border-none shadow-none max-w-none;
}

:deep(.days-grid .day.leave-selected) {
	outline: 2px solid #2563eb;
	outline-offset: 1px;
	border-radius: 0.5rem;
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
</style>
