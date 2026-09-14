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
						class="p-1 text-gray-400 hover:text-gray-700"
						:title="__('Refresh')"
						:aria-label="__('Refresh')"
						@click.stop="reloadCalendar"
					>
						<FeatherIcon
							name="refresh-cw"
							class="h-3.5 w-3.5"
							:class="calendarEvents.loading ? 'animate-spin' : ''"
						/>
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
						<i v-if="dayMarkers(getEventOnDate(index)).leave" class="marker-dot" :class="dayMarkers(getEventOnDate(index)).pending ? 'pending' : 'leave'" />
						<i v-if="dayMarkers(getEventOnDate(index)).sandwich" class="marker-dot sandwich" />
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
					<i class="marker-dot leave" />{{ __("Approved") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<i class="marker-dot pending" />{{ __("Pending") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<i class="marker-dot late" />{{ __("Late") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<i class="marker-dot early" />{{ __("Early exit") }}
				</span>
				<span class="inline-flex items-center gap-1">
					<i class="marker-dot sandwich" />{{ __("Sandwich") }}
				</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"
import { groupContiguousDates } from "@/utils/leave_ranges"

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
	if (status && colorMap[status]) return status
	const m = dayMarkers(info)
	if (!m.leave) return status
	if (m.rejected) return "Leave Rejected"
	if (m.pending) return "Leave Pending"
	return "On Leave"
}

const hasMarkers = (info) => {
	const m = dayMarkers(info)
	return m.leave || m.sandwich || m.late || m.early
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
	emit("select-day", { date, late: m.late, early: m.early, status: resolvePaintStatus(info) })
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

function reloadCalendar() {
	calendarEvents.reload()
	emit("refresh")
}

defineExpose({ reload: () => calendarEvents.reload() })

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

.marker-dot.late {
	background-color: #ea580c;
}

.marker-dot.early {
	background-color: #7c3aed;
}

.marker-dot.sandwich {
	background-color: #be123c;
}
</style>
