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
				:label="displayStatusLabel"
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

				<!-- Which holiday it actually is. "Holiday" alone leaves the reader
				     guessing, and the name is already on the Holiday List row. -->
				<div
					v-if="holidayName"
					class="flex items-center gap-2 rounded-lg px-3 py-2"
					style="background: #eceae6"
				>
					<i class="flag-dot" style="background: #a32d2d" />
					<div class="min-w-0">
						<div class="text-sm font-medium" style="color: #a32d2d">
							{{ holidayName }}
						</div>
						<div v-if="details.holiday?.holiday_list" class="text-[11px] text-gray-500 truncate">
							{{ details.holiday.holiday_list }}
						</div>
					</div>
				</div>

				<div v-if="hasFlags" class="flex flex-wrap gap-1.5">
					<span
						v-if="lateChip"
						class="flag-chip"
						:class="
							lateChip.after
								? 'bg-orange-100 text-orange-800 ring-orange-300'
								: 'bg-orange-50 text-orange-600 ring-orange-200'
						"
					>
						<i
							class="chip-delay-dot late"
							:class="lateChip.after ? 'after' : 'grace'"
						/>
						{{ lateChip.label }}
						<i
							v-if="lateChip.app"
							class="att-appmark"
							:class="appStatusClass(lateChip.app)"
							:title="__(lateChip.app)"
						/>
					</span>
					<span
						v-if="earlyChip"
						class="flag-chip"
						:class="
							earlyChip.after
								? 'bg-violet-100 text-violet-800 ring-violet-300'
								: 'bg-violet-50 text-violet-600 ring-violet-200'
						"
					>
						<i
							class="chip-delay-dot early"
							:class="earlyChip.after ? 'after' : 'grace'"
						/>
						{{ earlyChip.label }}
						<i
							v-if="earlyChip.app"
							class="att-appmark"
							:class="appStatusClass(earlyChip.app)"
							:title="__(earlyChip.app)"
						/>
					</span>
					<span
						v-if="oooChip"
						class="flag-chip bg-teal-50 text-teal-700 ring-teal-200"
					>
						<i class="flag-dot bg-teal-600" />{{ oooChip.label }}
						<i v-if="oooChip.app" class="att-appmark" :class="appStatusClass(oooChip.app)" />
					</span>
					<span
						v-if="details.flags.sandwich"
						class="flag-chip bg-rose-50 text-rose-700 ring-rose-200"
					>
						<i class="flag-dot bg-rose-600" />
						{{
							details.status === "On Leave"
								? __("Sandwich Leave")
								: __("Sandwich Absence")
						}}
					</span>
					<span
						v-if="leaveChip"
						class="flag-chip"
						:class="leaveChip.className"
					>
						<i class="flag-dot" :class="leaveChip.dot" />{{ leaveChip.label }}
						<template v-if="details.flags.leave_type">
							· {{ __(details.flags.leave_type) }}
						</template>
					</span>
					<span
						v-for="mark in dayLeaveMarks"
						:key="mark"
						:class="dayCodeClass(mark)"
					>
						{{ mark }}
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
						<div class="flex items-start justify-between gap-2">
							<div class="min-w-0">
								<div class="text-sm font-medium text-blue-800">{{ __(app.doctype) }}</div>
								<div class="text-xs text-blue-600 truncate">{{ app.name }}</div>
							</div>
							<span
								v-if="app.status"
								class="inline-flex items-center gap-1 shrink-0 text-xs font-semibold"
								:class="relatedStatusClass(app.status)"
							>
								<i class="att-appmark" :class="appStatusClass(app.status)" />
								{{ __(app.status) }}
							</span>
						</div>
						<!-- Why it was raised, and — when it was turned down — why that too;
						     a reason without the rejection note reads as if it was accepted. -->
						<div v-if="app.reason" class="mt-1 text-xs text-blue-900/80 whitespace-pre-line">
							{{ app.reason }}
						</div>
						<div
							v-if="app.rejection_reason && app.status === 'Rejected'"
							class="mt-1 text-xs text-red-700 whitespace-pre-line"
						>
							<span class="font-semibold">{{ __("Rejected") }}:</span>
							{{ app.rejection_reason }}
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
			<div class="grid grid-cols-2 gap-2">
				<button
					v-for="action in details.actions"
					:key="`${action.doctype}-${action.half_day || 0}`"
					type="button"
					class="flex min-h-[4.5rem] flex-col items-start justify-between gap-2 rounded-xl border p-3 text-left text-sm font-semibold leading-tight transition-colors"
					:class="actionStyle(action).button"
					@click="openForm(action)"
				>
					<span
						class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
						:class="actionStyle(action).icon"
					>
						<FeatherIcon :name="actionStyle(action).feather" class="h-4 w-4" />
					</span>
					<span>{{ action.label }}</span>
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, watch } from "vue"
import { createResource, Badge, FeatherIcon } from "frappe-ui"
import { modalController } from "@ionic/vue"
import { useRouter } from "vue-router"

import { formatNepaliDate, formatDaysFromToday } from "@/utils/nepali_date"
import { dayCodeClass, dayCodes } from "@/utils/attendance_colors"
import { appStatusClass, normalizeAppStatus } from "@/utils/app_status"

const props = defineProps({
	date: { type: String, required: true },
	fallbackStatus: { type: String, default: null },
	employee: { type: String, default: null },
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
	makeParams: () => {
		const params = { date: props.date }
		if (props.employee) params.employee = props.employee
		return params
	},
	auto: true,
})

watch(
	() => [props.date, props.employee],
	() => dayDetails.reload()
)

const details = computed(() => dayDetails.data || null)
const displayStatus = computed(() => details.value?.status || props.fallbackStatus)
const displayStatusLabel = computed(() => {
	const status = displayStatus.value
	if (status === "Leave Pending") return __("Pending Leave")
	if (status === "On Leave") return __("Approved Leave")
	if (status === "Leave Rejected") return __("Rejected Leave")
	return status ? __(status) : ""
})
const leaveChip = computed(() => {
	if (!details.value) return null
	const app = details.value.flags?.leave_app_status
	const status = details.value.status
	const isLeave =
		details.value.flags?.leave ||
		["On Leave", "Leave Pending", "Leave Rejected"].includes(status)
	if (!isLeave) return null
	if (app === "Pending" || status === "Leave Pending") {
		return {
			label: __("Pending Leave"),
			className: "bg-orange-50 text-orange-700 ring-orange-200",
			dot: "bg-orange-600",
		}
	}
	if (app === "Rejected" || status === "Leave Rejected") {
		return {
			label: __("Rejected Leave"),
			className: "bg-rose-50 text-rose-700 ring-rose-200",
			dot: "bg-rose-600",
		}
	}
	return {
		label: __("Approved Leave"),
		className: "bg-blue-50 text-blue-700 ring-blue-200",
		dot: "bg-blue-600",
	}
})
/** Holiday name, falling back to the kind when the list row has no description. */
const holidayName = computed(() => {
	const h = details.value?.holiday
	if (!h?.is_holiday) return ""
	return h.description || (h.weekly_off ? __("Weekly Off") : __("Holiday"))
})

const dayLeaveMarks = computed(() => {
	if (!details.value) return []
	return dayCodes({
		status: details.value.status,
		leave: details.value.flags?.leave,
		half_day: details.value.flags?.half_day,
		leave_type: details.value.flags?.leave_type,
		is_lwp: details.value.flags?.is_lwp,
		pool_penalty: details.value.flags?.pool_penalty,
		penalty_mark: details.value.flags?.penalty_mark,
	})
})

function delayChip(mins, grace, appStatus, afterLabel, withinLabel, appOnlyLabel) {
	const minutes = Number(mins) || 0
	const app = normalizeAppStatus(appStatus)
	if (minutes <= 0 && !app) return null
	const after = minutes > (Number(grace) || 15)
	let label = appOnlyLabel
	if (minutes > 0) label = after ? afterLabel : withinLabel
	return { after, app, label }
}

const lateChip = computed(() => {
	if (!details.value) return null
	return delayChip(
		details.value.late_mins,
		details.value.grace_mins,
		details.value.flags?.late_app_status,
		__("Late Entry · after grace"),
		__("Late Entry · within grace"),
		__("Late Entry")
	)
})

const earlyChip = computed(() => {
	if (!details.value) return null
	return delayChip(
		details.value.early_mins,
		details.value.grace_mins,
		details.value.flags?.early_app_status,
		__("Early Exit · after grace"),
		__("Early Exit · within grace"),
		__("Early Exit")
	)
})

const oooChip = computed(() => {
	if (!details.value) return null
	const app = normalizeAppStatus(details.value.flags?.ooo_app_status)
	if (!details.value.flags?.ooo_required && !app) return null
	const label = details.value.flags?.ooo_required
		? __("Out of Office required")
		: __("Out of Office")
	return { app, label }
})

function relatedStatusClass(status) {
	const value = normalizeAppStatus(status)
	if (value === "Approved") return "text-green-700"
	if (value === "Rejected") return "text-red-600"
	if (value === "Draft") return "text-amber-600"
	return "text-blue-500"
}

const hasFlags = computed(
	() =>
		details.value &&
		(lateChip.value ||
			earlyChip.value ||
			oooChip.value ||
			details.value.flags?.sandwich ||
			leaveChip.value ||
			dayLeaveMarks.value.length ||
			details.value.attendance?.shift)
)

const formatTime = (time) => {
	if (!time) return "—"
	return dayjs(time).isValid() ? dayjs(time).format("hh:mm a") : String(time).slice(0, 5)
}

// Same icon and colour per request type as the request rows and Quick Links.
// Spelled out so Tailwind keeps the classes; frappe-ui's palette has no slate
// or indigo, so those would render colourless.
const ACTION_STYLES = {
	"Leave Application": {
		feather: "calendar",
		button: "border-blue-200 bg-blue-50 text-blue-800 active:bg-blue-100",
		icon: "bg-blue-600 text-white",
	},
	"Late Entry Application": {
		feather: "clock",
		button: "border-orange-200 bg-orange-50 text-orange-800 active:bg-orange-100",
		icon: "bg-orange-500 text-white",
	},
	"Early Exit Application": {
		feather: "log-out",
		button: "border-purple-200 bg-purple-50 text-purple-800 active:bg-purple-100",
		icon: "bg-purple-600 text-white",
	},
	"Out of Office Application": {
		feather: "briefcase",
		button: "border-teal-200 bg-teal-50 text-teal-800 active:bg-teal-100",
		icon: "bg-teal-600 text-white",
	},
	"Attendance Request": {
		feather: "user-check",
		button: "border-red-200 bg-red-50 text-red-800 active:bg-red-100",
		icon: "bg-red-600 text-white",
	},
	"Compensatory Leave Request": {
		feather: "gift",
		button: "border-cyan-200 bg-cyan-50 text-cyan-800 active:bg-cyan-100",
		icon: "bg-cyan-600 text-white",
	},
	"Shift Request": {
		feather: "repeat",
		button: "border-gray-200 bg-gray-50 text-gray-800 active:bg-gray-100",
		icon: "bg-gray-600 text-white",
	},
}

function actionStyle(action) {
	return ACTION_STYLES[action.doctype] || ACTION_STYLES["Shift Request"]
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

.chip-delay-dot {
	display: inline-block;
	width: 8px;
	height: 8px;
	border-radius: 50%;
	flex-shrink: 0;
	box-sizing: border-box;
}

.chip-delay-dot.late.grace {
	background-color: #fff;
	box-shadow: inset 0 0 0 1.5px #ea580c;
}

.chip-delay-dot.late.after {
	background-color: #ea580c;
}

.chip-delay-dot.early.grace {
	background-color: #fff;
	box-shadow: inset 0 0 0 1.5px #7c3aed;
}

.chip-delay-dot.early.after {
	background-color: #7c3aed;
}

/* The sheet is a full-width panel, so the shared marks get a size bump here —
   size only; the colours stay in main.css. */
.att-code {
	font-size: 10px;
	padding: 2px 5px;
}

.att-appmark {
	font-size: 11px;
}
</style>
