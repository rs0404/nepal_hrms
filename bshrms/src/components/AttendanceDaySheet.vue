<template>
	<div class="bg-white w-full flex flex-col pb-5 max-h-[calc(100vh-5rem)]">
		<div
			class="w-full flex flex-col gap-1 pt-8 pb-4 px-4 border-b items-center justify-center sticky top-0 z-[100]"
		>
			<span class="text-gray-900 font-bold text-lg text-center">
				{{ formatNepaliDate(props.date) }}
			</span>
			<span class="text-xs text-gray-500">
				{{ dayjs(props.date).format("dddd, D MMM YYYY") }}
			</span>
			<span class="text-xs text-gray-500">{{ formatDaysFromToday(props.date) }}</span>
			<Badge
				v-if="displayStatus"
				variant="outline"
				:theme="statusTheme[displayStatus] || 'gray'"
				:label="__(displayStatus)"
				size="md"
				class="mt-1"
			/>
		</div>

		<div class="w-full p-4 overflow-auto flex flex-col gap-4">
			<div v-if="dayDetails.loading" class="text-sm text-gray-400 text-center py-6">
				{{ __("Loading day details…") }}
			</div>

			<template v-else-if="details">
				<div class="grid grid-cols-3 gap-2 text-center">
					<div class="rounded-lg bg-green-50 px-2 py-2.5 ring-1 ring-inset ring-green-200">
						<div class="text-green-800 font-semibold text-sm leading-5">
							{{ formatTime(details.attendance?.in_time) }}
						</div>
						<div class="text-green-600 text-[11px]">{{ __("Check In") }}</div>
					</div>
					<div class="rounded-lg bg-orange-50 px-2 py-2.5 ring-1 ring-inset ring-orange-200">
						<div class="text-orange-800 font-semibold text-sm leading-5">
							{{ formatTime(details.attendance?.out_time) }}
						</div>
						<div class="text-orange-600 text-[11px]">{{ __("Check Out") }}</div>
					</div>
					<div class="rounded-lg bg-blue-50 px-2 py-2.5 ring-1 ring-inset ring-blue-200">
						<div class="text-blue-800 font-semibold text-sm leading-5">
							{{
								details.attendance?.working_hours != null
									? Number(details.attendance.working_hours).toFixed(1) + "h"
									: "—"
							}}
						</div>
						<div class="text-blue-600 text-[11px]">{{ __("Work Hours") }}</div>
					</div>
				</div>

				<div v-if="hasFlags" class="flex flex-wrap gap-1.5">
					<span
						v-if="details.flags.late"
						class="flag-chip bg-orange-50 text-orange-700 ring-orange-200"
					>
						<i class="flag-dot bg-orange-600" />{{ __("Late Entry") }}
					</span>
					<span
						v-if="details.flags.early"
						class="flag-chip bg-violet-50 text-violet-700 ring-violet-200"
					>
						<i class="flag-dot bg-violet-600" />{{ __("Early Exit") }}
					</span>
					<span
						v-if="details.flags.ooo_required"
						class="flag-chip bg-teal-50 text-teal-700 ring-teal-200"
					>
						<i class="flag-dot bg-teal-600" />{{ __("Out of Office required") }}
					</span>
					<span
						v-if="details.flags.leave"
						class="flag-chip bg-blue-50 text-blue-700 ring-blue-200"
					>
						<i class="flag-dot bg-blue-600" />{{ __("On Leave") }}
						<template v-if="details.flags.leave_type">
							· {{ __(details.flags.leave_type) }}
						</template>
					</span>
					<span
						v-if="details.attendance?.shift"
						class="flag-chip bg-gray-50 text-gray-600 ring-gray-200"
					>
						{{ details.attendance.shift }}
					</span>
				</div>

				<div class="flex flex-col gap-1">
					<div class="text-sm font-semibold text-gray-800">
						{{ __("Check-in / Check-out Logs") }}
					</div>
					<div
						v-if="details.checkins?.length"
						class="flex flex-col bg-gray-50 rounded-lg border border-gray-100 divide-y divide-gray-100"
					>
						<div
							v-for="log in details.checkins"
							:key="log.name"
							class="flex justify-between items-center px-3 py-2"
						>
							<div class="flex flex-col">
								<span class="text-sm font-medium text-gray-800">
									{{ dayjs(log.time).format("hh:mm a") }}
								</span>
								<span
									v-if="log.custom_attendance_type === 'OOO Work' && log.custom_reason"
									class="text-[11px] text-gray-500 max-w-[220px] truncate"
								>
									{{ log.custom_reason }}
								</span>
							</div>
							<Badge
								:label="
									log.custom_attendance_type === 'OOO Work'
										? 'OOO ' + __(log.log_type)
										: __(log.log_type)
								"
								:theme="log.log_type === 'IN' ? 'green' : 'orange'"
								size="sm"
							/>
						</div>
					</div>
					<div v-else class="text-xs text-gray-400 italic">
						{{ __("No check-in logs for this day") }}
					</div>
				</div>

				<div v-if="details.links?.length" class="flex flex-col gap-2">
					<div class="text-sm font-semibold text-gray-800">
						{{ __("Related Applications") }}
					</div>
					<button
						v-for="app in details.links"
						:key="app.doctype + app.name"
						type="button"
						class="w-full text-left bg-blue-50 border border-blue-100 rounded-lg px-3 py-2"
						@click="openRelatedApplication(app)"
					>
						<div class="text-sm font-medium text-blue-800">{{ __(app.doctype) }}</div>
						<div class="text-xs text-blue-600 truncate">
							{{ app.name }}
							<span v-if="app.status" class="text-blue-400"> · {{ __(app.status) }}</span>
						</div>
					</button>
				</div>
			</template>

			<div v-else-if="dayDetails.error" class="text-sm text-red-500 text-center py-6">
				{{ __("Could not load day details") }}
			</div>
		</div>

		<div
			v-if="details?.actions?.length"
			class="flex w-full flex-col gap-2 sticky bottom-0 border-t z-[100] p-4 bg-white"
		>
			<div class="text-xs font-medium text-gray-500">
				{{ __("Forms available for this day") }}
			</div>
			<Button
				v-for="action in details.actions"
				:key="action.doctype"
				variant="solid"
				class="w-full py-4 text-sm"
				@click="openForm(action)"
			>
				{{ action.label }}
			</Button>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, watch } from "vue"
import { createResource, Badge, Button } from "frappe-ui"
import { modalController } from "@ionic/vue"
import { useRouter } from "vue-router"

import { formatNepaliDate, formatDaysFromToday } from "@/utils/nepali_date"

const props = defineProps({
	date: { type: String, required: true },
	fallbackStatus: { type: String, default: null },
})

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const router = useRouter()

const statusTheme = {
	Present: "green",
	"Work From Home": "green",
	"Half Day": "orange",
	Absent: "red",
	"On Leave": "blue",
	"Leave Pending": "orange",
	"Leave Rejected": "red",
	Holiday: "gray",
	"Weekly Off": "gray",
}

const dayDetails = createResource({
	url: "nepal_hrms.api.attendance_calendar.get_attendance_day_details",
	makeParams: () => ({ date: props.date }),
	auto: true,
})

watch(
	() => props.date,
	() => dayDetails.reload()
)

const details = computed(() => dayDetails.data || null)
const displayStatus = computed(() => details.value?.status || props.fallbackStatus)
const hasFlags = computed(
	() =>
		details.value &&
		(details.value.flags?.late ||
			details.value.flags?.early ||
			details.value.flags?.ooo_required ||
			details.value.flags?.leave ||
			details.value.attendance?.shift)
)

const formatTime = (time) => {
	if (!time) return "—"
	return dayjs(time).isValid() ? dayjs(time).format("hh:mm a") : String(time).slice(0, 5)
}

function openForm(action) {
	const query = { prefill: "1" }
	if (
		["LateEntryApplicationFormView", "EarlyExitApplicationFormView", "OutOfOfficeApplicationFormView"].includes(
			action.route_name
		)
	) {
		query.attendance_date = props.date
	} else {
		query.from_date = props.date
		query.to_date = props.date
		if (action.half_day) {
			query.half_day = "1"
			query.half_day_date = props.date
		}
	}
	modalController.dismiss()
	router.push({ name: action.route_name, query })
}

function openRelatedApplication(app) {
	const routeName = app.route_name || `${String(app.doctype).replace(/\s+/g, "")}DetailView`
	modalController.dismiss()
	router.push({ name: routeName, params: { id: app.name } })
}
</script>

<style scoped>
.flag-chip {
	@apply inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium ring-1 ring-inset;
}

.flag-dot {
	display: inline-block;
	width: 6px;
	height: 6px;
	border-radius: 50%;
	flex-shrink: 0;
}
</style>
