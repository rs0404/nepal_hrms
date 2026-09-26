<template>
	<div class="flex w-full flex-col gap-3">
		<div class="flex items-center justify-between gap-2">
			<div class="text-lg font-bold text-gray-800">{{ __("Shift Roster") }}</div>
			<div v-if="hasTeam.data" class="grid grid-cols-2 gap-1 rounded-full bg-gray-100 p-1 text-xs font-semibold">
				<button
					v-for="option in SCOPES"
					:key="option.value"
					type="button"
					class="rounded-full px-3 py-1"
					:class="scope === option.value ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'"
					@click="scope = option.value"
				>
					{{ __(option.label) }}
				</button>
			</div>
		</div>

		<div class="flex flex-col gap-3 rounded-2xl bg-white p-4 shadow-sm">
			<!-- BS month -->
			<div class="flex items-center justify-between">
				<button type="button" class="rounded-full p-1.5 active:bg-gray-100" @click="shiftMonth(-1)">
					<FeatherIcon name="chevron-left" class="h-5 w-5 text-gray-600" />
				</button>
				<div class="text-center">
					<div class="text-base font-semibold text-gray-900" lang="ne">{{ monthLabel }}</div>
					<div class="text-xs text-gray-600" lang="ne">{{ bsRangeLabel }}</div>
					<div class="text-[11px] text-gray-400">{{ adRangeLabel }}</div>
				</div>
				<button type="button" class="rounded-full p-1.5 active:bg-gray-100" @click="shiftMonth(1)">
					<FeatherIcon name="chevron-right" class="h-5 w-5 text-gray-600" />
				</button>
			</div>

			<div v-if="roster.loading && !roster.data" class="py-8 text-center text-sm text-gray-500">
				{{ __("Loading roster…") }}
			</div>
			<div v-else-if="roster.error" class="py-8 text-center text-sm text-red-600">
				{{ __("Could not load the roster") }}
			</div>

			<!-- Mine: a BS month calendar -->
			<template v-else-if="scope === 'self' && myRow">
				<div class="grid grid-cols-7 gap-1 text-center text-[10px] font-semibold text-gray-400" lang="ne">
					<div v-for="w in weekdayShort" :key="w">{{ w }}</div>
				</div>
				<div class="grid grid-cols-7 gap-1">
					<div v-for="n in leadingBlanks" :key="`b${n}`" />
					<button
						v-for="day in roster.data.days"
						:key="day"
						type="button"
						class="flex min-h-[4.25rem] flex-col items-center gap-0.5 rounded-lg border p-1 text-left"
						:class="[
							myRow.cells[day]?.holiday ? 'border-red-100 bg-red-50' : 'border-gray-100 bg-white',
							selectedDay === day ? 'ring-2 ring-gray-900' : '',
							day === todayIso ? 'border-gray-900' : '',
						]"
						@click="selectDay(day)"
					>
						<span
							class="text-sm font-semibold leading-none"
							:class="myRow.cells[day]?.holiday ? 'text-red-600' : 'text-gray-900'"
							lang="ne"
						>
							{{ bsDay(day) }}
						</span>
						<span class="text-[9px] leading-none text-gray-400">{{ adDay(day) }}</span>
						<span
							v-for="shift in myRow.cells[day]?.shifts || []"
							:key="shift"
							class="mt-0.5 w-full truncate rounded px-0.5 text-center text-[9px] font-semibold leading-tight text-white"
							:style="chipStyle(shift, myRow.cells[day])"
						>
							{{ shiftShort(shift) }}
						</span>
						<span
							v-for="shift in myRow.cells[day]?.requested || []"
							:key="`r-${shift}`"
							class="mt-0.5 w-full truncate rounded border border-dashed px-0.5 text-center text-[9px] font-semibold leading-tight"
							:style="requestedStyle(shift)"
						>
							{{ shiftShort(shift) }}
						</span>
						<span
							v-if="myRow.cells[day]?.leave"
							class="w-full truncate rounded px-0.5 text-center text-[9px] font-semibold leading-tight"
							:class="leaveClass(myRow.cells[day].leave)"
						>
							{{ myRow.cells[day].leave.half_day ? __("½ Leave") : __("Leave") }}
						</span>
					</button>
				</div>

				<!-- The tapped day, in full -->
				<div v-if="selectedDay && myRow.cells[selectedDay]" class="rounded-xl bg-gray-50 p-3 text-sm">
					<div class="font-semibold text-gray-900">
						<span lang="ne">{{ bsLong(selectedDay) }}</span>
						<span class="ml-1 text-xs font-normal text-gray-500">{{ adLong(selectedDay) }}</span>
					</div>
					<div v-if="myRow.cells[selectedDay].holiday" class="mt-1 text-xs font-medium text-red-600">
						{{ myRow.cells[selectedDay].holiday.description || __("Holiday") }}
					</div>
					<div
						v-for="shift in myRow.cells[selectedDay].shifts"
						:key="shift"
						class="mt-1.5 flex items-center gap-2"
					>
						<span class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ background: shiftColor(shift) }" />
						<span class="text-gray-800">{{ shift }}</span>
						<span class="text-xs text-gray-500">{{ shiftTimes(shift) }}</span>
						<span v-if="myRow.cells[selectedDay].default" class="text-[10px] text-gray-400">
							{{ __("(default)") }}
						</span>
					</div>
					<div v-if="!myRow.cells[selectedDay].shifts.length" class="mt-1 text-xs text-gray-500">
						{{ __("No shift") }}
					</div>
					<div v-if="myRow.cells[selectedDay].leave" class="mt-1.5 text-xs text-blue-700">
						{{ myRow.cells[selectedDay].leave.leave_type }}
						· {{ __(myRow.cells[selectedDay].leave.status) }}
						<span v-if="myRow.cells[selectedDay].leave.half_day">· {{ __("Half Day") }}</span>
					</div>
					<div
						v-for="shift in myRow.cells[selectedDay].requested || []"
						:key="`req-${shift}`"
						class="mt-1.5 flex items-center gap-2 text-xs"
					>
						<span class="h-2.5 w-2.5 shrink-0 rounded-full border border-dashed" :style="{ borderColor: shiftColor(shift) }" />
						<span class="text-gray-700">{{ shift }}</span>
						<span class="text-gray-500">{{ shiftTimes(shift) }}</span>
						<span class="rounded bg-amber-50 px-1.5 text-[10px] font-semibold text-amber-700">{{ __("Requested") }}</span>
					</div>

					<button
						v-if="!requesting"
						type="button"
						class="mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg bg-gray-900 py-2 text-sm font-semibold text-white"
						@click="openRequest"
					>
						<FeatherIcon name="repeat" class="h-4 w-4" />
						{{ __("Request Shift") }}
					</button>

					<!-- Request one or two shifts for this day (or a run of days) -->
					<div v-else class="mt-3 flex flex-col gap-2.5 border-t border-gray-200 pt-3">
						<div class="text-xs font-semibold text-gray-700">
							{{ __("Pick up to two shifts") }}
						</div>
						<div v-if="frequentShifts.data?.length" class="flex flex-wrap gap-1.5">
							<button
								v-for="option in frequentShifts.data"
								:key="option.shift_type"
								type="button"
								class="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold"
								:class="chosen.includes(option.shift_type) ? 'border-gray-900 bg-gray-900 text-white' : 'border-gray-200 bg-white text-gray-800'"
								@click="toggleShift(option.shift_type)"
							>
								<span class="h-2 w-2 rounded-full" :style="{ background: COLORS[option.color] || FALLBACK_COLOR }" />
								{{ option.shift_type }}
								<span class="font-normal opacity-70">{{ option.start }}–{{ option.end }}</span>
							</button>
						</div>
						<select
							class="form-select w-full rounded border-gray-300 text-sm"
							:value="''"
							@change="toggleShift($event.target.value); $event.target.value = ''"
						>
							<option value="">
								{{ frequentShifts.data?.length ? __("Other shift…") : __("Choose a shift…") }}
							</option>
							<option
								v-for="name in otherShiftTypes"
								:key="name"
								:value="name"
							>
								{{ name }}
							</option>
						</select>
						<div v-if="chosen.length" class="flex flex-wrap gap-1.5">
							<span
								v-for="name in chosen"
								:key="name"
								class="flex items-center gap-1 rounded-full bg-gray-900 px-2.5 py-1 text-xs font-semibold text-white"
							>
								{{ name }}
								<button type="button" class="opacity-70" @click="toggleShift(name)">
									<FeatherIcon name="x" class="h-3 w-3" />
								</button>
							</span>
						</div>
						<label class="flex items-center justify-between gap-2 text-xs text-gray-600">
							{{ __("Until") }}
							<input v-model="untilDate" type="date" :min="selectedDay" class="form-input rounded border-gray-300 text-sm" />
						</label>
						<p v-if="requestError" class="text-xs text-red-600">{{ requestError }}</p>
						<div class="flex gap-2">
							<button
								type="button"
								class="flex-1 rounded-lg border border-gray-300 py-2 text-sm font-semibold text-gray-700"
								@click="requesting = false"
							>
								{{ __("Cancel") }}
							</button>
							<button
								type="button"
								class="flex-1 rounded-lg bg-gray-900 py-2 text-sm font-semibold text-white disabled:opacity-50"
								:disabled="!chosen.length || sending"
								@click="sendRequest"
							>
								{{ sending ? __("Sending…") : __("Send request") }}
							</button>
						</div>
					</div>
				</div>
			</template>

			<!-- Team: employees down, days across, like the HRMS roster -->
			<div v-else-if="scope === 'team' && roster.data" class="-mx-4 overflow-x-auto">
				<table class="border-separate border-spacing-0 text-[10px]">
					<thead>
						<tr>
							<th class="sticky left-0 z-10 min-w-[7.5rem] bg-white px-2 py-1 text-left text-xs font-semibold text-gray-500">
								{{ __("Employee") }}
							</th>
							<th
								v-for="day in roster.data.days"
								:key="day"
								class="min-w-[2.6rem] border-b border-gray-100 px-0.5 py-1 text-center font-semibold"
								:class="isWeekend(day) ? 'text-red-500' : 'text-gray-500'"
							>
								<div lang="ne" class="text-xs">{{ bsDay(day) }}</div>
								<div class="font-normal text-gray-400">{{ weekdayOf(day) }}</div>
							</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="row in roster.data.employees" :key="row.employee">
							<td class="sticky left-0 z-10 max-w-[7.5rem] border-b border-gray-100 bg-white px-2 py-1">
								<div class="truncate text-xs font-semibold text-gray-900">{{ row.employee_name }}</div>
								<div class="truncate text-[10px] text-gray-400">{{ row.designation }}</div>
							</td>
							<td
								v-for="day in roster.data.days"
								:key="day"
								class="border-b border-gray-100 px-0.5 py-1 align-top"
								:class="row.cells[day]?.holiday ? 'bg-red-50' : ''"
							>
								<div class="flex flex-col gap-0.5">
									<span
										v-for="shift in row.cells[day]?.shifts || []"
										:key="shift"
										class="truncate rounded px-0.5 text-center font-semibold leading-tight text-white"
										:style="chipStyle(shift, row.cells[day])"
										:title="`${shift} ${shiftTimes(shift)}`"
									>
										{{ shiftShort(shift) }}
									</span>
									<span
										v-for="shift in row.cells[day]?.requested || []"
										:key="`r-${shift}`"
										class="truncate rounded border border-dashed px-0.5 text-center font-semibold leading-tight"
										:style="requestedStyle(shift)"
										:title="`${__('Requested')}: ${shift} ${shiftTimes(shift)}`"
									>
										{{ shiftShort(shift) }}
									</span>
									<span
										v-if="row.cells[day]?.leave"
										class="truncate rounded px-0.5 text-center font-semibold leading-tight"
										:class="leaveClass(row.cells[day].leave)"
									>
										{{ row.cells[day].leave.half_day ? "½L" : "L" }}
									</span>
								</div>
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<div
				v-else-if="!roster.loading"
				class="py-8 text-center text-sm text-gray-500"
			>
				{{ __("No shifts to show for this month") }}
			</div>

			<!-- Legend -->
			<div v-if="legend.length" class="flex flex-wrap gap-x-3 gap-y-1.5 border-t border-gray-100 pt-3 text-[11px] text-gray-600">
				<span v-for="item in legend" :key="item.name" class="flex items-center gap-1.5">
					<span class="h-2.5 w-2.5 rounded-sm" :style="{ background: item.color }" />
					<span class="font-semibold">{{ shiftShort(item.name) }}</span>
					<span class="text-gray-400">{{ item.times }}</span>
				</span>
				<span class="flex items-center gap-1.5">
					<span class="h-2.5 w-2.5 rounded-sm bg-blue-100 ring-1 ring-blue-300" />
					{{ __("Leave") }}
				</span>
				<span class="flex items-center gap-1.5">
					<span class="h-2.5 w-2.5 rounded-sm bg-red-50 ring-1 ring-red-200" />
					{{ __("Holiday") }}
				</span>
				<span class="flex items-center gap-1.5">
					<span class="h-2.5 w-2.5 rounded-sm opacity-50" style="background: #6b7280" />
					{{ __("Default shift") }}
				</span>
				<span class="flex items-center gap-1.5">
					<span class="h-2.5 w-2.5 rounded-sm border border-dashed border-gray-500" />
					{{ __("Requested") }}
				</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { call, createListResource, createResource, FeatherIcon, toast } from "frappe-ui"

import {
	formatNepaliDateNe,
	formatNepaliDatePeriodNe,
	formatNepaliMonthPeriodNe,
	toNepaliDigits,
} from "@/utils/nepali_date"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const SCOPES = [
	{ value: "self", label: "Mine" },
	{ value: "team", label: "Team" },
]
// Shift Type's colour options, as Frappe HR's roster paints them.
const COLORS = {
	Blue: "#3b82f6",
	Cyan: "#06b6d4",
	Fuchsia: "#d946ef",
	Green: "#22c55e",
	Lime: "#65a30d",
	Orange: "#f97316",
	Pink: "#ec4899",
	Red: "#ef4444",
	Violet: "#8b5cf6",
	Yellow: "#ca8a04",
}
const FALLBACK_COLOR = "#6b7280"

const scope = ref("self")
const selectedDay = ref("")
const requesting = ref(false)
const chosen = ref([])
const untilDate = ref("")
const sending = ref(false)
const requestError = ref("")
const MAX_SHIFTS = 2
const todayIso = dayjs().format("YYYY-MM-DD")

const lib = () => window.NepaliDateLib

// Paged by payroll period (Nepal HRMS Settings decides the window); 0 = current.
const periodOffset = ref(0)

function shiftMonth(step) {
	selectedDay.value = ""
	requesting.value = false
	periodOffset.value += step
}

const periodFrom = computed(() => roster.data?.from_date)
const periodTo = computed(() => roster.data?.to_date)
const monthLabel = computed(() =>
	periodFrom.value ? formatNepaliMonthPeriodNe(periodFrom.value, periodTo.value) : " "
)
const bsRangeLabel = computed(() =>
	periodFrom.value ? formatNepaliDatePeriodNe(periodFrom.value, periodTo.value) : ""
)
const adRangeLabel = computed(() =>
	periodFrom.value
		? `${dayjs(periodFrom.value).format("D MMM")} – ${dayjs(periodTo.value).format("D MMM YYYY")}`
		: ""
)

const hasTeam = createResource({ url: "nepal_hrms.api.shift_roster.has_team_roster", auto: true })

const roster = createResource({
	url: "nepal_hrms.api.shift_roster.get_shift_roster",
	makeParams: () => ({ period_offset: periodOffset.value, scope: scope.value }),
	auto: true,
})
watch([periodOffset, scope], () => roster.reload())

const myRow = computed(() => roster.data?.employees?.[0])

const weekdayShort = computed(
	() => lib()?.WEEKDAY_SHORT_NE || ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
)
const leadingBlanks = computed(() => (roster.data?.days?.length ? dayjs(roster.data.days[0]).day() : 0))

function bsParts(day) {
	try {
		return lib().NepaliDate.fromAD(new Date(`${day}T12:00:00`))
	} catch (e) {
		return null
	}
}
const bsDay = (day) => {
	const nd = bsParts(day)
	return nd ? toNepaliDigits(nd.day) : dayjs(day).format("D")
}
const adDay = (day) => dayjs(day).format("D MMM")
const bsLong = (day) => formatNepaliDateNe(day, { withWeekday: true }) || day
const adLong = (day) => dayjs(day).format("ddd, D MMM YYYY")
const weekdayOf = (day) => weekdayShort.value[dayjs(day).day()]
const isWeekend = (day) => dayjs(day).day() === 6

function shiftColor(shift) {
	return COLORS[roster.data?.shift_types?.[shift]?.color] || FALLBACK_COLOR
}
function shiftTimes(shift) {
	const type = roster.data?.shift_types?.[shift]
	return type ? `${type.start}–${type.end}` : ""
}
// "A - 09:30-17:30" -> "A"; "Full Time 2" -> "FT2".
function shiftShort(shift) {
	const head = String(shift).split(" - ")[0].trim()
	if (head.length <= 4) return head
	return head
		.split(/\s+/)
		.map((word) => (/^\d+$/.test(word) ? word : word[0]))
		.join("")
		.toUpperCase()
}
function chipStyle(shift, cell) {
	// A default shift is only a fallback, so it is drawn fainter than a planned one.
	return { background: shiftColor(shift), opacity: cell?.default ? 0.5 : 1 }
}
function requestedStyle(shift) {
	// Asked for, not yet approved: the shift's colour as an outline only.
	const color = shiftColor(shift)
	return { borderColor: color, color }
}

const frequentShifts = createResource({ url: "nepal_hrms.api.shift_roster.get_frequent_shift_types", auto: true })
const allShiftTypes = createListResource({
	doctype: "Shift Type",
	fields: ["name"],
	orderBy: "name asc",
	pageLength: 200,
	auto: true,
})
const otherShiftTypes = computed(() => {
	const frequent = new Set((frequentShifts.data || []).map((row) => row.shift_type))
	return (allShiftTypes.data || []).map((row) => row.name).filter((name) => !frequent.has(name))
})

function selectDay(day) {
	selectedDay.value = selectedDay.value === day ? "" : day
	requesting.value = false
}

function openRequest() {
	chosen.value = []
	untilDate.value = selectedDay.value
	requestError.value = ""
	requesting.value = true
}

function toggleShift(name) {
	if (!name) return
	requestError.value = ""
	if (chosen.value.includes(name)) {
		chosen.value = chosen.value.filter((n) => n !== name)
	} else if (chosen.value.length >= MAX_SHIFTS) {
		requestError.value = __("Pick at most {0} shifts for a day.", [MAX_SHIFTS])
	} else {
		chosen.value = [...chosen.value, name]
	}
}

async function sendRequest() {
	sending.value = true
	requestError.value = ""
	try {
		const result = await call("nepal_hrms.api.shift_roster.request_shifts", {
			shift_types: JSON.stringify(chosen.value),
			from_date: selectedDay.value,
			to_date: untilDate.value || selectedDay.value,
		})
		toast({
			title: __("Requested"),
			text: __("{0} shift request(s) sent for approval.", [result?.created?.length || chosen.value.length]),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
		requesting.value = false
		roster.reload()
	} catch (e) {
		requestError.value = e?.messages?.[0]?.replace(/<[^>]+>/g, "") || e?.message || __("Could not send the request.")
	} finally {
		sending.value = false
	}
}

function leaveClass(leave) {
	return leave.status === "Approved"
		? "bg-blue-100 text-blue-800"
		: "bg-white text-blue-700 ring-1 ring-inset ring-blue-300"
}

const legend = computed(() =>
	Object.entries(roster.data?.shift_types || {}).map(([name, type]) => ({
		name,
		color: COLORS[type.color] || FALLBACK_COLOR,
		times: `${type.start}–${type.end}`,
	}))
)
</script>
