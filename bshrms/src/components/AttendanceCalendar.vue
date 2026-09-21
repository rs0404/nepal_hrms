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
					:class="isOutsidePeriod(index) ? 'outside-period' : ''"
					:title="getEventOnDate(index)?.holiday_name || ''"
					@click="onDayClick(index)"
				>
					<div
						v-if="dayCodes(getEventOnDate(index)).length"
						class="absolute top-0 left-1/2 -translate-x-1/2 z-10 flex gap-px"
					>
						<span
							v-for="code in dayCodes(getEventOnDate(index))"
							:key="code"
							:class="dayCodeClass(code)"
						>
							{{ code }}
						</span>
					</div>
					<div
						class="h-9 w-9 flex rounded-lg mx-auto cursor-pointer"
						:class="isSelected(index) ? 'ring-2 ring-offset-1' : ''"
						:style="statusStyle(getEventOnDate(index))"
					>
						<span
							class="text-sm font-medium m-auto"
							:style="{
								color: isRestDay(index) ? 'var(--att-rest-text)' : '#1c1917',
							}"
						>
							{{ index }}
						</span>
					</div>
					<div
						v-if="hasMarkers(getEventOnDate(index))"
						class="flex gap-0.5 mt-0.5 min-h-[14px] items-start justify-center"
					>
						<i v-if="dayMarkers(getEventOnDate(index)).leave" class="att-dot att-dot-leave" />
						<i v-if="dayMarkers(getEventOnDate(index)).sandwich" class="att-dot att-dot-sandwich" />
						<span
							v-if="
								dayMarkers(getEventOnDate(index)).lateDelay ||
								dayMarkers(getEventOnDate(index)).late_app
							"
							class="marker-stack"
						>
							<i
								v-if="dayMarkers(getEventOnDate(index)).lateDelay"
								class="att-dot att-dot-late"
								:class="dayMarkers(getEventOnDate(index)).late_grace ? 'att-dot-grace' : ''"
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
								class="att-appmark"
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
								class="att-dot att-dot-early"
								:class="dayMarkers(getEventOnDate(index)).early_grace ? 'att-dot-grace' : ''"
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
								class="att-appmark"
								:class="appStatusClass(dayMarkers(getEventOnDate(index)).early_app)"
							/>
						</span>
						<span v-if="dayMarkers(getEventOnDate(index)).ooo" class="marker-stack">
							<i
								class="att-dot att-dot-ooo"
								:title="appStatusTitle(__('Out of Office'), dayMarkers(getEventOnDate(index)).ooo_app)"
							/>
							<i
								v-if="dayMarkers(getEventOnDate(index)).ooo_app"
								class="att-appmark"
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

			<!-- Totals for the payroll period, computed server-side. The grid above is
			     an English month; the label inside says which window these cover. -->
			<AttendancePeriodSummary :resource="periodSummary" />

			<!-- Same three channels as the BS calendar, in the same order: outcome
			     first, then exceptions, then the letters. -->
			<div class="flex flex-col gap-1 mx-1 text-[11px] text-gray-600">
				<div class="flex flex-wrap gap-x-3 gap-y-1">
					<span v-for="o in OUTCOME_LEGEND" :key="o.key" class="inline-flex items-center gap-1">
						<i class="legend-cell" :style="o.style" />{{ __(o.label) }}
					</span>
					<span v-if="hasOutsidePeriodDays" class="inline-flex items-center gap-1">
						<i class="outside-period-swatch" />{{ __("Outside the payroll period") }}
					</span>
				</div>
				<div class="flex flex-wrap gap-x-3 gap-y-1">
					<span class="inline-flex items-center gap-1">
						<i class="att-dot att-dot-late att-dot-grace" />{{ __("Late · within grace") }}
					</span>
					<span class="inline-flex items-center gap-1">
						<i class="att-dot att-dot-late" />{{ __("Late · after grace") }}
					</span>
					<span class="inline-flex items-center gap-1">
						<i class="att-dot att-dot-early" />{{ __("Early exit") }}
					</span>
					<span class="inline-flex items-center gap-1">
						<i class="att-dot att-dot-ooo" />{{ __("Out of Office") }}
					</span>
					<span class="inline-flex items-center gap-1">
						<i class="att-dot att-dot-sandwich" />{{ __("Sandwich") }}
					</span>
					<span class="inline-flex items-center gap-1">
						<i class="att-appmark approved" />{{ __("Approved") }}
					</span>
					<span class="inline-flex items-center gap-1">
						<i class="att-appmark rejected" />{{ __("Rejected") }}
					</span>
					<span class="inline-flex items-center gap-1">
						<i class="att-appmark draft" />{{ __("Pending") }}
					</span>
				</div>
				<div class="flex flex-wrap gap-x-3 gap-y-1">
					<span class="inline-flex items-center gap-1">
						<span class="att-code">½</span>{{ __("Half day") }}
					</span>
					<span class="inline-flex items-center gap-1">
						<span class="att-code">SL</span>{{ __("Sick") }}
					</span>
					<span class="inline-flex items-center gap-1">
						<span class="att-code">HL</span>{{ __("Home") }}
					</span>
					<span class="inline-flex items-center gap-1">
						<span class="att-code">LWP</span>{{ __("Without pay") }}
					</span>
					<span class="inline-flex items-center gap-1">
						<span class="att-code att-code-penalty">½P</span>{{ __("Half-day penalty") }}
					</span>
					<span class="inline-flex items-center gap-1">
						<span class="att-code att-code-penalty">1P</span>{{ __("Full-day penalty") }}
					</span>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"
import { groupContiguousDates } from "@/utils/leave_ranges"
import {
	OUTCOME,
	dayCellStyle,
	dayCodeClass,
	dayCodes,
	dayOutcome,
} from "@/utils/attendance_colors"
import AttendancePeriodSummary from "@/components/AttendancePeriodSummary.vue"
import {
	appStatusClass,
	appStatusTitle,
	hasDelayGraceAfter,
	normalizeAppStatus,
} from "@/utils/app_status"

const emit = defineEmits(["select-day", "create-leave", "refresh", "period-change"])

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

// Same tokens as the BS grid, applied as a style rather than Tailwind classes so
// the two calendars cannot drift apart again.
const OUTCOME_LEGEND = [
	{ key: "present", label: "Present" },
	{ key: "leave", label: "Leave" },
	{ key: "absent", label: "Absent" },
	{ key: "penalty", label: "Penalty (½P / 1P)" },
	{ key: "holiday", label: "Holiday / weekly off" },
].map((o) => ({
	...o,
	style: {
		backgroundColor: OUTCOME[o.key].fill,
		boxShadow: `inset 0 0 0 1.5px ${OUTCOME[o.key].ring}`,
	},
}))

const KNOWN_STATUSES = new Set([
	"Present", "Work From Home", "Half Day", "Absent",
	"On Leave", "Leave Pending", "Leave Rejected", "Holiday", "Weekly Off",
])

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
	if (status && KNOWN_STATUSES.has(status)) return status
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

const statusStyle = (info) => dayCellStyle(info)

/** Holidays and weekly offs get red numerals, matching the BS calendar. */
const isRestDay = (index) => dayOutcome(getEventOnDate(index)) === "holiday"

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

// Anchored on the visible month's first day: this calendar has no BS month to
// name, and its grid is an English month anyway. The summary's own label says
// which payroll period the numbers describe.
const periodSummary = createResource({
	url: "nepal_hrms.api.attendance_calendar.get_attendance_period_summary",
	auto: true,
	makeParams() {
		const params = { ref_date: firstOfMonth.value.format("YYYY-MM-DD") }
		if (props.employee) params.employee = props.employee
		return params
	},
})

// The grid is an English month; the totals under it are a payroll period. Shade
// the days the totals leave out instead of letting the two quietly disagree.
const periodWindow = computed(() => {
	const p = periodSummary.data?.period
	if (!p?.from_date || !p?.to_date) return null
	return p
})

// The dashboard's late/early and application panels describe a period too, and
// there is no reason for them to describe a different one from this calendar.
// `immediate` makes this run during setup, so periodWindow -- and therefore
// periodSummary -- must already be declared above: reading a `const` before its
// initializer throws, and a throw in setup renders the calendar not at all.
watch(periodWindow, (w) => w && emit("period-change", { ...w }), { immediate: true })

const isOutsidePeriod = (index) => {
	const w = periodWindow.value
	if (!w) return false
	const date = firstOfMonth.value.date(index).format("YYYY-MM-DD")
	return date < w.from_date || date > w.to_date
}

// An English month never lines up with a BS payroll period, so unlike the Nepali
// calendar this is essentially always true -- it is still a computed so the
// legend stays quiet until the summary has actually loaded.
const hasOutsidePeriodDays = computed(() => {
	const w = periodWindow.value
	if (!w) return false
	return (
		firstOfMonth.value.format("YYYY-MM-DD") < w.from_date ||
		firstOfMonth.value.endOf("M").format("YYYY-MM-DD") > w.to_date
	)
})

async function reloadCalendar() {
	await calendarEvents.reload()
	periodSummary.reload()
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
/* Outside the payroll period the totals describe. Still readable and still
   tappable -- the day's own record is unchanged, it just is not counted here. */
.outside-period {
	opacity: 0.4;
	background-image: repeating-linear-gradient(
		135deg,
		rgba(100, 116, 139, 0.11) 0 4px,
		transparent 4px 8px
	);
}

.outside-period-swatch,
.legend-cell {
	display: inline-block;
	width: 12px;
	height: 12px;
	border-radius: 3px;
	flex-shrink: 0;
}

.outside-period-swatch {
	opacity: 0.4;
	background-color: #f1f5f9;
	background-image: repeating-linear-gradient(
		135deg,
		rgba(100, 116, 139, 0.45) 0 2px,
		transparent 2px 4px
	);
}

.marker-stack {
	display: inline-flex;
	flex-direction: column;
	align-items: center;
	gap: 1px;
}

/* Leave and sandwich ride the leave hue; neither is an outcome of its own. */
.att-dot-leave,
.att-dot-sandwich {
	color: #2a78d6;
}

.att-dot-sandwich {
	box-shadow: inset 0 0 0 1.5px #fff;
}
</style>
