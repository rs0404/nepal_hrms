<template>
	<div class="flex w-full flex-col gap-5 rounded-2xl bg-white p-5 shadow-sm">
		<div class="flex items-center justify-between gap-3">
			<h2 class="text-lg font-bold text-gray-900">{{ __("Check-in") }}</h2>
			<span
				class="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"
				:class="isCheckedIn ? TYPE_STYLE[sessionType].badge : 'bg-gray-100 text-gray-600'"
			>
				<span
					class="h-1.5 w-1.5 rounded-full"
					:class="isCheckedIn ? TYPE_STYLE[sessionType].dot : 'bg-gray-400'"
				/>
				{{ isCheckedIn ? __("Checked in · {0}", [__(sessionType)]) : __("Not checked in") }}
			</span>
		</div>

		<!-- Live clock: seconds tick so it reads as "now", not as a log time. -->
		<div class="rounded-xl bg-gray-50 px-4 py-3.5 text-center">
			<div class="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
				{{ __("Now") }}
			</div>
			<div class="mt-0.5 font-bold tabular-nums text-gray-900">
				<span class="text-4xl">{{ clockHm }}</span><span class="text-xl text-gray-400">:{{ clockSec }}</span>
				<span class="ml-1 text-base font-semibold text-gray-500">{{ clockAmPm }}</span>
			</div>
			<!-- Nepali date leads, in Nepali; the English date follows, quieter. -->
			<div class="mt-2 flex flex-wrap items-center justify-center gap-x-2 gap-y-1">
				<span
					class="rounded-md px-2 py-0.5 text-[15px] font-semibold"
					:class="isHolidayToday ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'"
					lang="ne"
				>
					{{ todayNe || todayBs }}
				</span>
				<span class="text-xs text-gray-500">{{ todayAd }}</span>
			</div>
			<!-- A named holiday says which; a weekly off is already plain from the weekday. -->
			<div
				v-if="isHolidayToday && !todayHoliday.data?.weekly_off && todayHoliday.data?.description"
				class="mt-1 text-xs font-medium text-red-600"
			>
				{{ todayHoliday.data.description }}
			</div>
		</div>

		<template v-if="settings.data?.allow_employee_checkin_from_mobile_app">
			<!-- Choosing the type here rather than in the sheet: it is the one thing
			     you decide before checking in, and the sheet still owns the OOO
			     reason. Locked while a session is open -- you leave the way you
			     arrived, so checking out cannot switch type. -->
			<div class="grid grid-cols-2 gap-1 rounded-full bg-gray-100 p-1">
				<button
					v-for="type in ATTENDANCE_TYPES"
					:key="type"
					type="button"
					class="rounded-full py-2 text-sm font-semibold transition-colors"
					:class="[
						sessionType === type ? TYPE_STYLE[type].selected : 'text-gray-600',
						isCheckedIn ? 'cursor-default' : '',
						isCheckedIn && sessionType !== type ? 'opacity-50' : '',
					]"
					:disabled="isCheckedIn"
					@click="selectedAttendanceType = type"
				>
					{{ __(type) }}
				</button>
			</div>

			<button
				type="button"
				id="open-checkin-modal"
				class="flex h-14 w-full items-center justify-center gap-2 rounded-xl text-base font-semibold text-white shadow-sm transition-colors"
				:class="isCheckedIn ? TYPE_STYLE[sessionType].buttonOut : TYPE_STYLE[sessionType].button"
				@click="handleEmployeeCheckin"
			>
				<FeatherIcon :name="isCheckedIn ? 'log-out' : 'log-in'" class="h-5 w-5" />
				{{ nextAction.label }}
			</button>

			<router-link
				v-if="lastLog?.time"
				:to="{ name: 'EmployeeCheckinListView' }"
				class="flex items-center justify-between gap-3 rounded-xl bg-gray-50 px-3.5 py-3"
			>
				<div class="flex min-w-0 items-center gap-2.5">
					<span
						class="rounded-full px-2 py-0.5 text-xs font-bold"
						:class="lastLog.log_type === 'OUT' ? TYPE_STYLE[lastLogType].badgeOut : TYPE_STYLE[lastLogType].badge"
					>
						{{ lastLog.log_type }}
					</span>
					<div class="min-w-0">
						<div class="text-sm font-semibold tabular-nums text-gray-900">
							{{ dayjs(lastLog.time).format("h:mm A") }}
							<span class="font-normal text-gray-500">· {{ lastLogBs }}</span>
						</div>
						<div class="text-xs text-gray-400">
							{{ __("Last log") }} · {{ lastLogAd }}
						</div>
					</div>
				</div>
				<span class="flex shrink-0 items-center gap-0.5 text-sm text-gray-500">
					{{ __("View List") }}
					<FeatherIcon name="chevron-right" class="h-4 w-4" />
				</span>
			</router-link>
		</template>
	</div>

	<ion-modal
		v-if="settings.data?.allow_employee_checkin_from_mobile_app"
		ref="modal"
		trigger="open-checkin-modal"
		:initial-breakpoint="1"
		:breakpoints="[0, 1]"
	>
		<div class="h-120 w-full flex flex-col items-center justify-center gap-5 p-4 mb-5">
			<div class="flex flex-col gap-1.5 mt-2 items-center justify-center">
				<div class="font-bold text-xl">
					{{ dayjs(checkinTimestamp).format("hh:mm:ss a") }}
				</div>
				<div class="font-medium text-gray-500 text-sm">
					{{ todayBs }}
				</div>
				<div class="text-xs text-gray-400">
					{{ dayjs().format("D MMM YYYY") }} · {{ formatDaysFromToday(dayjs().format("YYYY-MM-DD")) }}
				</div>
			</div>

			<template v-if="settings.data?.allow_geolocation_tracking">
				<span v-if="locationStatus" class="font-medium text-gray-500 text-sm">
					{{ locationStatus }}
				</span>

				<div class="rounded border-4 translate-z-0 block overflow-hidden w-full h-170">
					<iframe
						width="100%"
						height="170"
						frameborder="0"
						scrolling="no"
						marginheight="0"
						marginwidth="0"
						style="border: 0"
						:src="`https://maps.google.com/maps?q=${latitude},${longitude}&hl=en&z=15&amp;output=embed`"
					>
					</iframe>
				</div>
			</template>
			<div class="flex flex-col gap-2 w-full mt-4">
				<div class="text-xs font-medium text-gray-500 px-1">{{ __("Attendance Type") }}</div>
				<div v-if="isCheckedIn" class="w-full bg-gray-50 border border-gray-200 rounded-lg p-3.5 text-center text-sm font-semibold text-gray-700">
					{{ __("Active Session:") }}
					<span class="font-bold ml-1" :class="TYPE_STYLE[sessionType].text">{{ __(sessionType) }}</span>
				</div>
				<div v-else class="grid grid-cols-2 gap-1 rounded-full bg-gray-100 p-1">
					<button
						v-for="type in ATTENDANCE_TYPES"
						:key="type"
						type="button"
						class="rounded-full py-2 text-sm font-semibold transition-colors"
						:class="sessionType === type ? TYPE_STYLE[type].selected : 'text-gray-600'"
						@click="selectedAttendanceType = type"
					>
						{{ __(type) }}
					</button>
				</div>
			</div>

			<div class="flex flex-col gap-2 w-full" v-if="selectedAttendanceType === 'OOO Work'">
				<div class="text-xs font-medium text-gray-500 px-1">{{ __("OOO Reason") }}</div>
				<textarea 
					v-model="customReason" 
					class="w-full p-3 border rounded-lg text-sm focus:ring-2 focus:ring-gray-200 outline-none min-h-24 bg-gray-50 transition-all border-gray-200"
					:placeholder="__('Explain why you are working out of office...')"
				></textarea>
			</div>

			<Button
				:loading="checkins.insert.loading"
				:disabled="selectedAttendanceType === 'OOO Work' && !customReason.trim()"
				variant="solid"
				class="w-full py-5 text-sm !text-white disabled:opacity-50"
				:class="isCheckedIn ? TYPE_STYLE[sessionType].confirmOut : TYPE_STYLE[sessionType].confirm"
				@click="submitLog(nextAction.action)"
			>
				{{ __("Confirm {0}", [nextAction.label]) }}
			</Button>
		</div>
	</ion-modal>
</template>

<script setup>
import { createResource, createListResource, toast, FeatherIcon } from "frappe-ui"
import { computed, inject, ref, watch, onMounted, onBeforeUnmount } from "vue"
import { IonModal, modalController } from "@ionic/vue"

import {
	formatDaysFromToday,
	formatNepaliDateLong,
	formatNepaliDateNe,
	formatEnglishDate,
} from "@/utils/nepali_date"

const DOCTYPE = "Employee Checkin"

const socket = inject("$socket")
const employee = inject("$employee")
const dayjs = inject("$dayjs")
const __ = inject("$translate")
const checkinTimestamp = ref(null)
const latitude = ref(0)
const longitude = ref(0)
const locationStatus = ref("")
const selectedAttendanceType = ref("Normal")
const customReason = ref("")
const settings = createResource({
	url: "hrms.api.get_hr_settings",
	auto: true,
})

const checkins = createListResource({
	doctype: DOCTYPE,
	fields: ["name", "employee", "employee_name", "log_type", "time", "device_id", "custom_attendance_type"],
	filters: {
		employee: employee.data.name,
	},
	orderBy: "time desc",
})
checkins.reload()

const lastLog = computed(() => {
	if (checkins.list.loading || !checkins.data) return {}
	return checkins.data[0]
})

const isCheckedIn = computed(() => lastLog?.value?.log_type === "IN")

const ATTENDANCE_TYPES = ["Normal", "OOO Work"]
// Normal is green, OOO Work red, everywhere the type shows; Check Out is a
// darker shade of the same colour than Check In. Spelled out so Tailwind keeps
// the classes.
const TYPE_STYLE = {
	Normal: {
		selected: "bg-green-600 text-white shadow-sm",
		button: "bg-green-600 active:bg-green-700",
		buttonOut: "bg-green-800 active:bg-green-900",
		confirmOut: "!bg-green-800 hover:!bg-green-900",
		badgeOut: "bg-green-700 text-white",
		dot: "bg-green-600",
		confirm: "!bg-green-600 hover:!bg-green-700",
		badge: "bg-green-100 text-green-700",
		text: "text-green-700",
	},
	"OOO Work": {
		selected: "bg-red-600 text-white shadow-sm",
		button: "bg-red-600 active:bg-red-700",
		buttonOut: "bg-red-800 active:bg-red-900",
		confirmOut: "!bg-red-800 hover:!bg-red-900",
		badgeOut: "bg-red-700 text-white",
		dot: "bg-red-600",
		confirm: "!bg-red-600 hover:!bg-red-700",
		badge: "bg-red-100 text-red-700",
		text: "text-red-700",
	},
}

// While checked in, the session's own type; otherwise what the toggle picked.
const sessionType = computed(() => {
	const type = isCheckedIn.value
		? lastLog.value.custom_attendance_type || "Normal"
		: selectedAttendanceType.value
	return TYPE_STYLE[type] ? type : "Normal"
})

const lastLogType = computed(() =>
	lastLog.value?.custom_attendance_type === "OOO Work" ? "OOO Work" : "Normal"
)
const lastLogDate = computed(() => (lastLog.value?.time ? String(lastLog.value.time).slice(0, 10) : ""))
const lastLogBs = computed(() => formatNepaliDateLong(lastLogDate.value))
const lastLogAd = computed(() => formatEnglishDate(lastLogDate.value))

const now = ref(new Date())
let clockTimer = null
const clockHm = computed(() => dayjs(now.value).format("h:mm"))
const clockSec = computed(() => dayjs(now.value).format("ss"))
const clockAmPm = computed(() => dayjs(now.value).format("A"))
const todayIso = computed(() => dayjs(now.value).format("YYYY-MM-DD"))
const todayBs = computed(() => formatNepaliDateLong(todayIso.value))
const todayNe = computed(() => formatNepaliDateNe(todayIso.value, { withWeekday: true }))

// Red on a holiday or weekly off, green on a working day. Green until it loads.
const todayHoliday = createResource({
	url: "nepal_hrms.api.attendance_calendar.get_day_holiday",
	makeParams: () => ({ date: todayIso.value, employee: employee.data?.name }),
	auto: true,
})
const isHolidayToday = computed(() => Boolean(todayHoliday.data?.is_holiday))
// The card stays open past midnight; ask again for the new day.
watch(todayIso, () => todayHoliday.reload())
const todayAd = computed(() => dayjs(now.value).format("ddd, D MMM YYYY"))

const nextAction = computed(() => {
	return lastLog?.value?.log_type === "IN"
		? { action: "OUT", label: __("Check Out") }
		: { action: "IN", label: __("Check In") }
})

function handleLocationSuccess(position) {
	latitude.value = position.coords.latitude
	longitude.value = position.coords.longitude

	locationStatus.value = [
		__("Latitude: {0}°", [Number(latitude.value).toFixed(5)]),
		__("Longitude: {0}°", [Number(longitude.value).toFixed(5)]),
	].join(", ")
}

function handleLocationError(error) {
	locationStatus.value = "Unable to retrieve your location"
	if (error) locationStatus.value += `: ERROR(${error.code}): ${error.message}`
}

const fetchLocation = () => {
	if (!navigator.geolocation) {
		locationStatus.value = __("Geolocation is not supported by your current browser")
	} else {
		locationStatus.value = __("Locating...")
		navigator.geolocation.getCurrentPosition(handleLocationSuccess, handleLocationError)
	}
}

const handleEmployeeCheckin = () => {
	checkinTimestamp.value = dayjs().format("YYYY-MM-DD HH:mm:ss")

	// Checking out is locked to how the session started. Checking in keeps what
	// the card toggle chose -- resetting here would silently discard it.
	if (isCheckedIn.value) {
		selectedAttendanceType.value = lastLog.value.custom_attendance_type || "Normal"
	}

	if (settings.data?.allow_geolocation_tracking) {
		fetchLocation()
	}
}

const submitLog = (logType) => {
	const actionLabel = logType === "IN" ? __("Check-in") : __("Check-out")

	checkins.insert.submit(
		{
			employee: employee.data.name,
			log_type: logType,
			time: checkinTimestamp.value,
			latitude: latitude.value,
			longitude: longitude.value,
			custom_attendance_type: selectedAttendanceType.value,
			custom_reason: customReason.value,
		},
		{
			onSuccess() {
				modalController.dismiss()
				toast({
					title: __("Success"),
					text: __("{0} successful!", [actionLabel]),
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
			},
			onError(error) {
				let messages = error.messages || []

				for (const message of messages) {
					toast({
						title: __("Error"),
						text: message || __("{0} failed!", [actionLabel]),
						icon: "alert-circle",
						position: "bottom-center",
						iconClasses: "text-red-500",
					})
				}
			},
		}
	)
}

onMounted(() => {
	clockTimer = setInterval(() => (now.value = new Date()), 1000)
	socket.emit("doctype_subscribe", DOCTYPE)
	socket.on("list_update", (data) => {
		if (data.doctype == DOCTYPE) {
			checkins.reload()
		}
	})
})

onBeforeUnmount(() => {
	clearInterval(clockTimer)
	socket.emit("doctype_unsubscribe", DOCTYPE)
	socket.off("list_update")
})
</script>
