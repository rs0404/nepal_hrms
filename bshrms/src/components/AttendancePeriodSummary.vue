<!--
  Attendance totals for one payroll period.

  Every number here is computed on the server by the same code that builds the
  Monthly Attendance Sheet BS report, so the two can no longer disagree. Do not
  reintroduce counting in this component — that drift is the bug it replaces.

  Shared by both calendars on purpose: the previous per-calendar copies had already
  diverged from each other as well as from the report.
-->
<template>
	<div v-if="resource?.loading && !totals" class="text-xs text-gray-400 mx-1">
		{{ __("Loading summary…") }}
	</div>
	<div v-else-if="resource?.error" class="text-xs text-red-500 mx-1">
		{{ __("Could not load attendance summary") }}
	</div>
	<div v-else-if="notFound" class="text-xs text-gray-400 mx-1">
		{{ __("No attendance record for this period") }}
	</div>
	<div v-else-if="totals" class="flex flex-col gap-1 mx-1">
		<!-- Which window these numbers describe. Without this the AD calendar shows
		     an English-month grid above payroll-period totals with no explanation. -->
		<div class="flex flex-row items-center gap-1 text-[11px] text-gray-500">
			<span>{{ periodLabel }}</span>
			<span v-if="auditLabel" class="text-gray-400">· {{ auditLabel }}</span>
			<span
				v-if="mismatch"
				class="text-amber-600 font-semibold cursor-help"
				:title="__('Paid-day checks do not reconcile — contact HR')"
				>!</span
			>
		</div>

		<div class="grid grid-cols-6 gap-1">
			<div v-for="tile in tiles" :key="tile.key" class="flex flex-col gap-0.5">
				<div class="flex flex-row gap-1 items-center">
					<span
						v-if="tile.swatch"
						class="h-2.5 w-2.5 shrink-0 rounded-[3px]"
						:style="{
							backgroundColor: tile.swatch.fill,
							boxShadow: `inset 0 0 0 1.5px ${tile.swatch.ring}`,
						}"
					/>
					<span v-else-if="tile.chip" class="att-code att-code-penalty shrink-0">
						{{ tile.chip }}
					</span>
					<span class="text-gray-600 text-[11px] font-medium leading-4 whitespace-nowrap">
						{{ __(tile.label) }}
					</span>
				</div>
				<span
					class="text-sm leading-5 mx-auto"
					:class="tile.key === 'payable' ? 'text-gray-900 font-bold' : 'text-gray-800 font-semibold'"
				>
					{{ fmtDays(tile.value) }}
				</span>
			</div>
		</div>

		<div v-if="hasUpcoming" class="text-[11px] text-gray-500">
			{{ __("Upcoming (not counted above)") }}:
			<span v-if="upcoming.approved_leave_days">
				{{ fmtDays(upcoming.approved_leave_days) }} {{ __("approved") }}
			</span>
			<span v-if="upcoming.approved_leave_days && upcoming.pending_leave_days">·</span>
			<span v-if="upcoming.pending_leave_days">
				{{ fmtDays(upcoming.pending_leave_days) }} {{ __("pending") }}
			</span>
			{{ __("leave day(s)") }}
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue"
import { formatNepaliMonthYearPeriod } from "@/utils/nepali_date"
import { OUTCOME } from "@/utils/attendance_colors"

const props = defineProps({
	// A createResource on nepal_hrms.api.attendance_calendar.get_attendance_period_summary
	resource: { type: Object, default: null },
})

const data = computed(() => props.resource?.data || null)
const notFound = computed(() => !!data.value && data.value.found === false)
const totals = computed(() => (data.value && data.value.found ? data.value.totals : null))
const period = computed(() => data.value?.period || {})
const upcoming = computed(() => data.value?.upcoming || {})

const mismatch = computed(() => Number(totals.value?.payable_days_mismatch || 0) === 1)

const hasUpcoming = computed(
	() =>
		Number(upcoming.value.approved_leave_days || 0) > 0 ||
		Number(upcoming.value.pending_leave_days || 0) > 0,
)

const periodLabel = computed(() => {
	const { from_date, to_date } = period.value
	if (!from_date) return ""
	return formatNepaliMonthYearPeriod(from_date, to_date) || `${from_date} – ${to_date}`
})

const auditLabel = computed(() => {
	const through = period.value.audit_through_date
	if (!through || through === period.value.to_date) return ""
	return `${__("counted through")} ${through}`
})

const tiles = computed(() => {
	const t = totals.value || {}
	// No "Half Day" tile: there is no such report count — a half day is 0.5 in two
	// of these instead, which is the whole point of matching the report.
	//
	// Only the four outcome tiles carry a swatch, and it is the same token the day
	// cells use, so the strip and the grid read as one thing. Penalty shows its own
	// chip instead: it is not an outcome, and as a sixth pale red square it sat at
	// ΔE 5.8 from Absent right beside it. Payable has no swatch at all — it is the
	// total of the others, not a category, so it reads as the row's headline.
	return [
		{ key: "present", label: "Present", value: t.total_present, swatch: OUTCOME.present },
		{ key: "leave", label: "Leave", value: t.paid_leave_days, swatch: OUTCOME.leave },
		// Shares the Leave swatch on purpose: LWP is leave, and the label is the
		// distinction. Same reason the calendar gives it a letter, not a hue.
		{ key: "lwp", label: "LWP", value: t.lwp_days, swatch: OUTCOME.leave },
		{ key: "absent", label: "Absent", value: t.total_absent, swatch: OUTCOME.absent },
		{ key: "penalty", label: "Penalty", value: t.penalty_days, chip: "1P" },
		{ key: "payable", label: "Payable", value: t.payable_days },
	]
})

/** 18 -> "18", 18.5 -> "18.5". Never an unconditional toFixed: "18.0" reads as a
 *  rounding artefact rather than a whole day. */
function fmtDays(n) {
	const v = Number(n || 0)
	if (Number.isNaN(v)) return "0"
	return Number.isInteger(v) ? String(v) : v.toFixed(1)
}
</script>
