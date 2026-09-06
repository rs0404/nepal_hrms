<template>
	<div class="flex flex-col bg-white rounded w-full py-6 px-4 border-none">
		<h2 class="text-lg font-bold text-gray-900">
			{{ __("Hey, {0} 👋", [employee?.data?.first_name]) }}
		</h2>

		<template v-if="settings.data?.allow_employee_checkin_from_mobile_app">
			<div class="font-medium text-sm text-gray-500 mt-1.5" v-if="lastLog">
				<span>{{ __("Last {0} was at {1}", [__(lastLogType), formatTimestamp(lastLog.time)]) }}</span>
				<span class="whitespace-pre"> &middot; </span>
				<router-link :to="{ name: 'EmployeeCheckinListView' }" v-slot="{ navigate }">
					<span @click="navigate" class="underline">View List</span>
				</router-link>
			</div>
			<Button
				class="mt-4 mb-1 drop-shadow-sm py-5 text-base"
				id="open-checkin-modal"
				@click="handleEmployeeCheckin"
			>
				<template #prefix>
					<FeatherIcon
						:name="nextAction.action === 'IN' ? 'arrow-right-circle' : 'arrow-left-circle'"
						class="w-4"
					/>
				</template>
				{{ nextAction.label }}
			</Button>
		</template>

		<div v-else class="font-medium text-sm text-gray-500 mt-1.5">
			{{ formatNepaliDate(dayjs().format("YYYY-MM-DD")) }}
			· {{ dayjs().format("ddd, D MMM YYYY") }}
			· {{ formatDaysFromToday(dayjs().format("YYYY-MM-DD")) }}
		</div>
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
					{{ formatNepaliDate(dayjs().format("YYYY-MM-DD")) }}
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
				<div v-if="lastLog && lastLog.log_type === 'IN'" class="w-full bg-gray-50 border border-gray-200 rounded-lg p-3.5 text-center text-sm font-semibold text-gray-700">
					{{ __("Active Session:") }} <span class="text-blue-600 font-bold ml-1">{{ lastLog.custom_attendance_type === 'OOO Work' ? __("OOO Work") : __("Normal") }}</span>
				</div>
				<div v-else class="flex gap-2">
					<Button 
						class="flex-1" 
						:variant="selectedAttendanceType === 'Normal' ? 'solid' : 'outline'" 
						@click="selectedAttendanceType = 'Normal'"
					>
						{{ __("Normal") }}
					</Button>
					<Button 
						class="flex-1" 
						:variant="selectedAttendanceType === 'OOO Work' ? 'solid' : 'outline'" 
						@click="selectedAttendanceType = 'OOO Work'"
					>
						{{ __("OOO Work") }}
					</Button>
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
				class="w-full py-5 text-sm disabled:bg-gray-700" 
				@click="submitLog(nextAction.action)"
			>
				{{ __("Confirm {0}", [nextAction.label]) }}
			</Button>
		</div>
	</ion-modal>
</template>

<script setup>
import { createResource, createListResource, toast, FeatherIcon } from "frappe-ui"
import { computed, inject, ref, onMounted, onBeforeUnmount } from "vue"
import { IonModal, modalController } from "@ionic/vue"

import { formatTimestamp } from "@/utils/formatters"
import { formatNepaliDate, formatDaysFromToday } from "@/utils/nepali_date"

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

const lastLogType = computed(() => {
	const type = lastLog?.value?.log_type === "IN" ? "check-in" : "check-out"
	return lastLog?.value?.custom_attendance_type === "OOO Work" ? "OOO " + type : type
})

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

	if (lastLog.value && lastLog.value.log_type === "IN") {
		selectedAttendanceType.value = lastLog.value.custom_attendance_type || "Normal"
	} else {
		selectedAttendanceType.value = "Normal"
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
	socket.emit("doctype_subscribe", DOCTYPE)
	socket.on("list_update", (data) => {
		if (data.doctype == DOCTYPE) {
			checkins.reload()
		}
	})
})

onBeforeUnmount(() => {
	socket.emit("doctype_unsubscribe", DOCTYPE)
	socket.off("list_update")
})
</script>
