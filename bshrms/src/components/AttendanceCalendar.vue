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
				<span class="text-base text-gray-800 font-bold">
					{{ firstOfMonth.format("MMMM") }} {{ firstOfMonth.format("YYYY") }}
				</span>
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
					class="relative flex flex-col items-center"
					@click="onDayClick(index)"
				>
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
						class="flex gap-0.5 mt-0.5 h-1.5 items-center justify-center"
					>
						<i v-if="dayMarkers(getEventOnDate(index)).leave" class="marker-dot leave" />
						<i v-if="dayMarkers(getEventOnDate(index)).late" class="marker-dot late" />
						<i v-if="dayMarkers(getEventOnDate(index)).early" class="marker-dot early" />
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
			<div class="grid grid-cols-4 mx-1">
				<div v-for="status in summaryStatuses" :key="status" class="flex flex-col gap-0.5">
					<div class="flex flex-row gap-1 items-center">
						<span class="rounded-full h-2.5 w-2.5 shrink-0" :class="colorMap[status]" />
						<span class="text-gray-600 text-[11px] font-medium leading-4">
							{{ __(status) }}
						</span>
					</div>
					<span class="text-gray-800 text-sm font-semibold leading-5 mx-auto">
						{{ summary[status] || 0 }}
					</span>
				</div>
			</div>

			<div class="flex flex-wrap gap-x-3 gap-y-1 mx-1 text-[11px] text-gray-600">
				<span class="inline-flex items-center gap-1">
					<i class="marker-dot leave" />{{ __("Leave") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<i class="marker-dot late" />{{ __("Late") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<i class="marker-dot early" />{{ __("Early exit") }}
				</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { createResource } from "frappe-ui"

const emit = defineEmits(["select-day", "create-leave"])

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
	Holiday: "bg-gray-200 ring-1 ring-inset ring-gray-300",
	"Weekly Off": "bg-gray-200 ring-1 ring-inset ring-gray-300",
}

const summaryStatuses = ["Present", "Half Day", "Absent", "On Leave"]
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
			late: false,
			early: false,
		}
	}
	return {
		leave: !!info.leave || info.status === "On Leave",
		late: !!info.late,
		early: !!info.early,
	}
}

const hasMarkers = (info) => {
	const m = dayMarkers(info)
	return m.leave || m.late || m.early
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
	const sorted = [...selectedDates.value].sort()
	emit("create-leave", { from_date: sorted[0], to_date: sorted[sorted.length - 1] })
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
	const status = dayStatus(info)
	emit("select-day", { date, late: m.late, early: m.early, status })
}

const statusColor = (info) => {
	const status = dayStatus(info)
	return status ? colorMap[status] : ""
}

const summary = computed(() => {
	const counts = {}
	if (!calendarEvents.data) return counts

	for (const info of Object.values(calendarEvents.data)) {
		let status = dayStatus(info)
		if (!status) continue
		if (status === "Work From Home") status = "Present"
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
	cache: [
		"nepal_hrms:attendance_calendar_details",
		() => props.employee,
		() => firstOfMonth.value.format("YYYY-MM-DD"),
	],
	makeParams() {
		const params = {
			from_date: firstOfMonth.value.format("YYYY-MM-DD"),
			to_date: firstOfMonth.value.endOf("M").format("YYYY-MM-DD"),
		}
		if (props.employee) params.employee = props.employee
		return params
	},
})

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

.marker-dot.late {
	background-color: #ea580c;
}

.marker-dot.early {
	background-color: #7c3aed;
}
</style>
