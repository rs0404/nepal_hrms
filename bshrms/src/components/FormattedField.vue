<template>
	<div v-if="isEmpty" class="text-gray-600 text-base">-</div>

	<Badge
		v-else-if="props.fieldtype === 'Select'"
		variant="outline"
		:theme="colorMap[props.value]"
		:label="__(props.value)"
		size="md"
	/>

	<div v-else-if="props.fieldtype === 'Date'" class="flex flex-col items-end text-right">
		<div class="text-gray-900 text-base">{{ formatNepaliDate(props.value) }}</div>
		<div class="text-xs text-gray-500">{{ dayjs(props.value).format("dddd, D MMM YYYY") }}</div>
		<div v-if="showRelativeOffset" class="text-xs text-gray-500">
			{{ formatDaysFromToday(props.value) }}
		</div>
	</div>

	<div v-else-if="props.fieldtype === 'DateRange'" class="flex flex-col items-end text-right">
		<div class="text-gray-900 text-base">{{ rangeBs }}</div>
		<div class="text-xs text-gray-500">{{ rangeAd }}</div>
		<div v-if="rangeOffset" class="text-xs text-gray-500">{{ rangeOffset }}</div>
	</div>

	<div v-else-if="props.fieldtype === 'Time'" class="text-gray-900 text-base">
		{{ formatTime(props.value) }}
	</div>

	<Input
		v-else-if="props.fieldtype === 'Check'"
		type="checkbox"
		label=""
		v-model="props.value"
		:disabled="true"
		class="rounded-sm text-gray-800"
	/>

	<div
		v-else-if="['Small Text', 'Text', 'Long Text'].includes(props.fieldtype)"
		class="text-gray-900 text-base bg-gray-100 rounded py-3 pl-3 mt-2"
	>
		{{ props.value }}
	</div>

	<EmployeeAvatar
		v-else-if="props.fieldtype === 'Link' && ['employee', 'reports_to'].includes(props.fieldname)"
		:employeeID="props.value"
		:showLabel="true"
	/>

	<div
		v-else-if="props.fieldtype === 'geolocation'"
		class="rounded border-4 translate-z-0 block overflow-hidden w-full h-170 mt-2"
	>
		<iframe
			width="100%"
			height="170"
			frameborder="0"
			scrolling="no"
			marginheight="0"
			marginwidth="0"
			style="border: 0"
			:src="`https://maps.google.com/maps?q=${getCoordinates(props.value).latitude},${
				getCoordinates(props.value).longitude
			}&hl=en&z=15&amp;output=embed`"
		>
		</iframe>
	</div>

	<div
		v-else-if="
			props.fieldtype === 'Link' &&
			[
				'leave_application',
				'attendance_request',
				'attendance',
			].includes(props.fieldname)
		"
		class="text-blue-700 text-base underline"
	>
		{{ props.value }}
	</div>

	<div v-else class="text-gray-900 text-base">{{ props.value }}</div>
</template>

<script setup>
import { computed, inject } from "vue"
import { Badge, Input } from "frappe-ui"

import EmployeeAvatar from "@/components/EmployeeAvatar.vue"
import { formatNepaliDate, formatNepaliPeriod, formatDaysFromToday } from "@/utils/nepali_date"

const dayjs = inject("$dayjs")

const NO_OFFSET_FIELDS = ["date_of_birth", "date_of_joining"]

const props = defineProps({
	value: [String, Number, Boolean, Array, Object],
	fieldtype: String,
	fieldname: String,
})

const isEmpty = computed(() => {
	if (props.fieldtype === "DateRange") {
		return !props.value?.from && !props.value?.to
	}
	return props.value === null || props.value === undefined || props.value === ""
})

const showRelativeOffset = computed(() => !NO_OFFSET_FIELDS.includes(props.fieldname))

const rangeBs = computed(() => {
	const from = props.value?.from
	const to = props.value?.to
	if (!from) return ""
	if (!to) return `${formatNepaliDate(from)} · Ongoing`
	return formatNepaliPeriod(from, to)
})

const rangeAd = computed(() => {
	const from = props.value?.from
	const to = props.value?.to
	if (!from) return ""
	const fromAd = dayjs(from).format("dddd, D MMM YYYY")
	if (!to) return `${fromAd} – Ongoing`
	if (from === to || dayjs(from).isSame(dayjs(to), "day")) return fromAd
	if (dayjs(from).isSame(dayjs(to), "year")) {
		return `${dayjs(from).format("dddd, D MMM")} – ${dayjs(to).format("dddd, D MMM YYYY")}`
	}
	return `${fromAd} – ${dayjs(to).format("dddd, D MMM YYYY")}`
})

const rangeOffset = computed(() => {
	const from = props.value?.from
	const to = props.value?.to
	if (!from) return ""
	const fromOffset = formatDaysFromToday(from)
	if (!to || from === to || dayjs(from).isSame(dayjs(to), "day")) return fromOffset
	const toOffset = formatDaysFromToday(to)
	if (fromOffset === toOffset) return fromOffset
	return `${fromOffset} · ${toOffset}`
})

const colorMap = {
	Approved: "green",
	Rejected: "red",
	Open: "orange",
	Draft: "orange",
	"Waiting for Approval": "orange",
}

const getCoordinates = (value) => {
	const [longitude, latitude] = JSON.parse(value).features[0].geometry.coordinates
	return { longitude, latitude }
}

const formatTime = (value) => {
	if (!value) return "-"
	const match = String(value).match(/(\d{1,2}):(\d{2})(?::(\d{2}))?/)
	if (!match) return String(value)
	const hours = Number(match[1])
	const minutes = match[2]
	const suffix = hours >= 12 ? "pm" : "am"
	const hour12 = hours % 12 || 12
	return `${hour12}:${minutes} ${suffix}`
}
</script>
