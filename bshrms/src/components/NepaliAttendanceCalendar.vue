<!--
  Attendance calendar drawn over the PAYROLL PERIOD, not the BS month.

  Under a Custom Day Range basis the period that payroll calls "Bhadra" runs
  Shrawan 29 - Bhadra 28. A BS month grid cannot show that: it draws Bhadra 1-31,
  which both hides the three Shrawan days the totals count and shows three Bhadra
  days they do not. Shading only ever fixed the second half of that.

  So the grid is built here from the window the server resolved, rather than by
  nepal_compliance's NepaliCalendarLib, which renders whole BS months only. Every
  day on screen is a day the totals below count, and paging moves by period.

  The day numbers stay BS-first with the AD day underneath, so it still reads as
  a Nepali calendar.
-->
<template>
	<div class="flex flex-col w-full gap-3">
		<div class="bg-white rounded-lg p-2 shadow-sm border border-gray-100">
			<div class="flex items-center justify-between gap-1 px-1 pt-1">
				<button
					type="button"
					class="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 disabled:opacity-30"
					:aria-label="__('Previous period')"
					:disabled="!periodWindow"
					@click="stepPeriod(-1)"
				>
					<FeatherIcon name="chevron-left" class="h-4 w-4" />
				</button>

				<div class="flex flex-col items-center leading-tight min-w-0">
					<span class="text-sm font-bold text-gray-800 truncate">{{ periodTitle }}</span>
					<span class="text-[11px] text-gray-500 truncate">{{ periodSubtitle }}</span>
				</div>

				<div class="flex items-center gap-0.5 shrink-0">
					<button
						type="button"
						class="p-1.5 rounded-md text-gray-500 hover:bg-gray-100"
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
					</button>
					<button
						type="button"
						class="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 disabled:opacity-30"
						:aria-label="__('Next period')"
						:disabled="!periodWindow"
						@click="stepPeriod(1)"
					>
						<FeatherIcon name="chevron-right" class="h-4 w-4" />
					</button>
				</div>
			</div>

			<div v-if="!periodDays.length" class="py-8 text-center text-xs text-gray-400">
				{{ __("Loading calendar…") }}
			</div>

			<div v-else class="grid grid-cols-7 gap-0.5 mt-2">
				<div
					v-for="(label, i) in WEEKDAYS"
					:key="'wd-' + i"
					class="text-center text-[11px] font-medium pb-1"
					:class="i === 6 ? 'text-rose-500' : 'text-gray-500'"
				>
					{{ label }}
				</div>

				<div v-for="n in leadingBlanks" :key="'pad-' + n" />

				<button
					v-for="day in periodDays"
					:key="day.ad"
					type="button"
					class="day-cell"
					:class="{
						'is-today': day.ad === todayStr,
						'is-selected': selectedDates.has(day.ad),
						'is-saturday': day.weekday === 6,
						'is-rest': day.outcome === 'holiday',
						'month-edge': day.monthEdge,
					}"
					:style="day.fill"
					:title="day.holidayName"
					@click="onDayClick(day)"
				>
					<!-- Bottom-left: what the day was, and where its leave stands (✓, pending clock, ✕).
					     Top-right stays for the late / early / OOO dots, so the two
					     never meet. -->
					<span v-if="day.codes.length || day.leaveApp" class="day-codes" aria-hidden="true">
						<span v-for="code in day.codes" :key="code" :class="dayCodeClass(code)">
							{{ code }}
						</span>
						<i
							v-if="day.leaveApp"
							class="att-appmark"
							:class="appStatusClass(day.leaveApp)"
							:title="appStatusTitle(__('Leave'), day.leaveApp)"
						/>
					</span>

					<span class="bs-day">{{ day.bsLabel }}</span>
					<span class="ad-day">{{ day.adDay }}</span>

					<span
						v-if="day.dots.length || day.appOnlyMarks.length"
						class="day-markers"
						aria-hidden="true"
					>
						<span v-for="dot in day.dots" :key="dot.kind" class="marker-stack">
							<i class="att-dot" :class="dot.cls" :title="dot.title" />
							<i
								v-if="dot.app"
								class="att-appmark"
								:class="appStatusClass(dot.app)"
							/>
						</span>
						<i
							v-for="m in day.appOnlyMarks"
							:key="m.kind"
							class="att-appmark"
							:class="appStatusClass(m.status)"
							:title="appStatusTitle(m.kind, m.status)"
						/>
					</span>
				</button>
			</div>

			<div class="flex justify-center pt-1.5">
				<button
					type="button"
					class="text-[11px] font-semibold text-blue-600 px-2 py-1 rounded-md hover:bg-blue-50"
					@click="goToToday"
				>
					{{ __("आज") }}
				</button>
			</div>

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

		<!-- Totals for exactly the days drawn above, computed server-side so they
		     match the Monthly Attendance Sheet BS report. -->
		<AttendancePeriodSummary :resource="periodSummary" />
		<div v-if="attendanceEvents.loading" class="text-xs text-gray-400 mx-1">
			{{ __("Loading attendance…") }}
		</div>
		<div v-else-if="attendanceEvents.error" class="text-xs text-red-500 mx-1">
			{{ __("Could not load attendance markers") }}
		</div>

		<!-- Outcome first, because it is the only thing carrying a hue; the letters
		     and glyphs under it are the other channels. -->
		<div class="flex flex-col gap-1 mx-1 text-[11px] text-gray-600">
			<div class="flex flex-wrap gap-x-3 gap-y-1">
				<span v-for="o in OUTCOME_LEGEND" :key="o.key" class="inline-flex items-center gap-1">
					<i class="legend-cell" :style="o.style" />{{ __(o.label) }}
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
					<i class="att-dot att-dot-ooo" />{{ __("Out of Office · office work") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<i class="att-dot att-dot-ooo att-dot-grace" />{{ __("Out of Office · applied, or gap to explain") }}
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
</template>

<script setup>
import { onMounted, ref, inject, watch, computed } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"
import { ensureNepaliDateLib } from "@/utils/nepali_calendar"
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

const props = defineProps({
	employee: { type: String, default: null },
})

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const sessionEmployee = inject("$employee")
const isSelf = computed(() => !props.employee || props.employee === sessionEmployee.data?.name)
const todayStr = dayjs().format("YYYY-MM-DD")
const selectMode = ref(false)
const selectedDates = ref(new Set())
const selectedCount = computed(() => selectedDates.value.size)
// Bumped once the date library is on the page, purely to re-run the day builder.
const libReady = ref(0)


// Which payroll period to show, as the BS month that NAMES it (the month it ends
// in). null means "whatever period contains today" — the server decides, so the
// payroll cycle is never reimplemented here.
const visibleBs = ref(null)

const periodSummary = createResource({
	url: "nepal_hrms.api.attendance_calendar.get_attendance_period_summary",
	auto: true,
	makeParams() {
		const params = {}
		if (props.employee) params.employee = props.employee
		if (visibleBs.value) {
			params.bs_year = visibleBs.value.year
			params.bs_month = visibleBs.value.month
		}
		return params
	},
})

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
})

async function reloadCalendar() {
	await attendanceEvents.reload()
	periodSummary.reload()
	emit("refresh")
}

defineExpose({ reload: reloadCalendar })

watch(
	() => props.employee,
	() => {
		cancelSelectMode()
		attendanceEvents.reload()
		periodSummary.reload()
	}
)

onMounted(async () => {
	await ensureNepaliDateLib()
	libReady.value++
})

/* ---------------------------------------------------------------- BS helpers */

// Date strings are parsed as UTC midnight and read back with UTC getters
// throughout: NepaliDate.fromAD converts against a UTC reference, so mixing in
// local getters shifts a day either side of midnight depending on the timezone.
function utcDate(ad) {
	return new Date(`${ad}T00:00:00Z`)
}

function adString(date) {
	return date.toISOString().slice(0, 10)
}

function neNum(n) {
	const lib = window.NepaliDateLib
	return lib?.formatNumber ? lib.formatNumber(n, "ne") : String(n)
}

const WEEKDAYS = computed(() => {
	void libReady.value
	return (
		window.NepaliDateLib?.WEEKDAY_SHORT_NE || ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
	)
})

function bsMonthName(monthIndex) {
	const lib = window.NepaliDateLib
	return lib?.MONTH_NAMES_NE_BS?.[monthIndex] || lib?.MONTH_NAMES_EN_BS?.[monthIndex] || ""
}

/* ------------------------------------------------------------------ the grid */

/** One entry per day of the payroll period, in order, ready to render. */
const periodDays = computed(() => {
	void libReady.value
	const w = periodWindow.value
	const NepaliDate = window.NepaliDateLib?.NepaliDate
	if (!w || !NepaliDate) return []

	const days = []
	const end = utcDate(w.to_date)
	let cursor = utcDate(w.from_date)
	let prevMonthIndex = null
	// A period spans two BS months; guard against a malformed window rather than
	// spinning forever building cells.
	while (cursor <= end && days.length < 40) {
		const ad = adString(cursor)
		const nd = NepaliDate.fromAD(cursor)
		const info = attendanceEvents.data?.[ad]
		const m = dayMarkers(info)
		days.push({
			ad,
			adDay: cursor.getUTCDate(),
			weekday: cursor.getUTCDay(),
			bsLabel: neNum(nd.day),
			bsMonthIndex: nd.monthIndex,
			// The first day of the period's second BS month gets a divider, so the
			// Shrawan/Bhadra handover is visible rather than implied.
			monthEdge: prevMonthIndex !== null && nd.monthIndex !== prevMonthIndex,
			fill: dayCellStyle(info),
			outcome: dayOutcome(info),
			holidayName: (info && info.holiday_name) || "",
			status: resolvePaintStatus(info),
			codes: dayCodes(info),
			dots: markerDots(m),
			appOnlyMarks: appOnlyMarks(m),
			leaveApp: m.leave_app,
			late: m.lateDelay,
			early: m.earlyDelay,
		})
		prevMonthIndex = nd.monthIndex
		cursor = new Date(cursor.getTime() + 86400000)
	}
	return days
})

const leadingBlanks = computed(() => (periodDays.value.length ? periodDays.value[0].weekday : 0))

const periodTitle = computed(() => {
	void libReady.value
	const w = periodWindow.value
	if (!w) return ""
	// Named by the month the period ends in, which is the server's own convention.
	if (w.bs_year && w.bs_month) return `${bsMonthName(w.bs_month - 1)} ${neNum(w.bs_year)}`
	return `${w.bs_from} – ${w.bs_to}`
})

const periodSubtitle = computed(() => {
	void libReady.value
	const days = periodDays.value
	if (!days.length) return ""
	const first = days[0]
	const last = days[days.length - 1]
	const span = `${bsMonthName(first.bsMonthIndex)} ${first.bsLabel} – ${bsMonthName(
		last.bsMonthIndex
	)} ${last.bsLabel}`
	const adSpan = `${dayjs(first.ad).format("D MMM")} – ${dayjs(last.ad).format("D MMM YYYY")}`
	return `${span} · ${adSpan}`
})

/** Step to the neighbouring payroll period by stepping the month that names it. */
function stepPeriod(delta) {
	const w = periodWindow.value
	if (!w?.bs_year || !w?.bs_month) return
	let year = w.bs_year
	let month = w.bs_month + delta
	if (month < 1) {
		month = 12
		year -= 1
	} else if (month > 12) {
		month = 1
		year += 1
	}
	visibleBs.value = { year, month }
	periodSummary.reload()
}

function goToToday() {
	visibleBs.value = null
	periodSummary.reload()
}

/* ------------------------------------------------------------- day rendering */

const dayStatus = (info) => {
	if (!info) return null
	if (typeof info === "string") return info
	return info.status || null
}

const dayMarkers = (info) => {
	if (!info || typeof info === "string") {
		return {
			leave: info === "On Leave",
			leave_app: "",
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
			oooPunched: false,
			oooDelay: false,
			ooo_app: "",
			ooo_log: "",
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
	const ooo_log = normalizeAppStatus(info.ooo_log_status)
	// OOO Work punches are only for office work, so the filled dot means that.
	// A mid-day gap with no form is not office work: it joins the hollow dot,
	// marked by nothing until an application covers it.
	const oooPunched = !!ooo_log
	return {
		leave,
		// Approval state of the leave, marked like a Late Entry's: ✓, pending clock, ✕.
		leave_app: leave ? normalizeAppStatus(app) : "",
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
		// Any Out of Office on the day: an application, OOO Work punches, or a
		// gap that still needs one.
		ooo: oooPunched || !!ooo_app,
		oooPunched,
		oooDelay: !!info.ooo_required,
		ooo_app,
		ooo_log,
	}
}

/** Dots under the day number, in the order the legend lists them. */
function markerDots(m) {
	const dots = []
	// Sandwich is a property of the leave, not an exception of its own; it rides
	// the leave hue rather than claiming a seventh colour.
	if (m.sandwich) dots.push({ kind: "sandwich", cls: "att-dot-sandwich", title: __("Sandwich"), app: "" })
	if (m.lateDelay) {
		dots.push({
			kind: "late",
			cls: `att-dot-late${m.late_grace ? " att-dot-grace" : ""}`,
			title: appStatusTitle(
				m.late_grace ? __("Late (within grace)") : __("Late (after grace)"),
				m.late_app
			),
			app: m.late_app,
		})
	}
	if (m.earlyDelay) {
		dots.push({
			kind: "early",
			cls: `att-dot-early${m.early_grace ? " att-dot-grace" : ""}`,
			title: appStatusTitle(
				m.early_grace ? __("Early (within grace)") : __("Early (after grace)"),
				m.early_app
			),
			app: m.early_app,
		})
	}
	if (m.ooo) {
		// Filled: out on office work (OOO punches). Hollow: an application, or a
		// gap still to explain. The punches are what get paid, so theirs is the mark.
		const app = m.oooPunched ? m.ooo_log || m.ooo_app : m.ooo_app
		dots.push({
			kind: "ooo",
			cls: m.oooPunched ? "att-dot-ooo" : "att-dot-ooo att-dot-grace",
			title: appStatusTitle(
				m.oooPunched
					? __("Out of Office · office work")
					: m.ooo_app
						? __("Out of Office · applied")
						: __("Out of Office · gap to explain"),
				app
			),
			app,
		})
	}
	return dots
}

/** An application with no delay behind it still has to show, or an approved
 *  request on an otherwise clean day would look like nothing happened. */
function appOnlyMarks(m) {
	const marks = []
	if (m.late_app && !m.lateDelay) marks.push({ kind: __("Late"), status: m.late_app })
	if (m.early_app && !m.earlyDelay) marks.push({ kind: __("Early exit"), status: m.early_app })
	return marks
}

// Statuses the day sheet knows how to title. Leave variants are derived below
// when the raw status is something else (e.g. a pending application on a blank day).
const KNOWN_STATUSES = new Set([
	"Present", "Work From Home", "Half Day", "Absent",
	"On Leave", "Leave Pending", "Leave Rejected", "Holiday", "Weekly Off",
])

function resolvePaintStatus(info) {
	const status = dayStatus(info)
	if (KNOWN_STATUSES.has(status)) return status
	const m = dayMarkers(info)
	if (!m.leave) return status
	if (m.rejected) return "Leave Rejected"
	if (m.pending) return "Leave Pending"
	return "On Leave"
}

/* ------------------------------------------------------------ leave selection */

const isDaySelectable = (ad) => {
	if (!ad || ad <= todayStr) return false
	const status = dayStatus(attendanceEvents.data?.[ad])
	return !["Holiday", "Weekly Off", "On Leave", "Leave Pending"].includes(status)
}

function onDayClick(day) {
	if (selectMode.value) {
		if (isDaySelectable(day.ad)) toggleDaySelection(day.ad)
		return
	}
	emit("select-day", {
		date: day.ad,
		late: day.late,
		early: day.early,
		status: day.status,
	})
}

function startSelectMode() {
	selectMode.value = true
}

function cancelSelectMode() {
	selectMode.value = false
	selectedDates.value = new Set()
}

function toggleDaySelection(ad) {
	const next = new Set(selectedDates.value)
	if (next.has(ad)) next.delete(ad)
	else next.add(ad)
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
</script>

<style scoped>
.day-cell {
	position: relative;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	min-height: 44px;
	padding: 4px 2px 12px;
	border-radius: 6px;
	background-color: #fff;
	cursor: pointer;
}

.day-cell .bs-day {
	font-size: 0.8rem;
	font-weight: 600;
	line-height: 1.1;
	color: #1c1917;
}

/* Saturdays and holidays alike — the red numeral is how a Nepali calendar says
   "not a working day", independent of the fill behind it. */
.day-cell.is-saturday .bs-day,
.day-cell.is-rest .bs-day {
	color: var(--att-rest-text);
}

.day-cell.is-saturday .ad-day,
.day-cell.is-rest .ad-day {
	color: var(--att-rest-text);
	opacity: 0.8;
}

.day-cell .ad-day {
	position: absolute;
	right: 5px;
	bottom: 3px;
	font-size: 0.58rem;
	line-height: 1;
	opacity: 0.6;
	color: #1c1917;
}

.day-cell.is-today {
	outline: 1.5px solid #1c1917;
	outline-offset: -1.5px;
}

.day-cell.is-selected {
	outline: 2px solid #2a78d6;
	outline-offset: -2px;
}

/* The period crosses from one BS month into the next; mark the handover so the
   Shrawan days at the start do not read as part of Bhadra. */
.day-cell.month-edge::before {
	content: "";
	position: absolute;
	inset: 2px auto 2px -2px;
	width: 2px;
	border-radius: 1px;
	background: #cbd5e1;
}

.day-cell .day-codes {
	position: absolute;
	bottom: 2px;
	left: 2px;
	align-items: center;
	z-index: 3;
	display: flex;
	gap: 1px;
	pointer-events: none;
}

.day-cell .day-markers {
	position: absolute;
	top: 3px;
	right: 4px;
	z-index: 2;
	display: flex;
	gap: 2px;
	align-items: flex-start;
	pointer-events: none;
}

.marker-stack {
	display: inline-flex;
	flex-direction: column;
	align-items: center;
	gap: 1px;
}

/* Sandwich rides the leave hue rather than claiming a colour of its own. */
.att-dot-sandwich {
	color: #2a78d6;
	box-shadow: inset 0 0 0 1.5px #fff;
}

.legend-cell {
	display: inline-block;
	width: 12px;
	height: 12px;
	border-radius: 3px;
	flex-shrink: 0;
}
</style>
