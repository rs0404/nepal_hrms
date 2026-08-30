<template>
	<Dialog v-model="show">
		<template #body-title>
			<h2 class="text-xl font-bold">{{ __("Select Nepali Date") }}</h2>
		</template>
		<template #body-content>
			<div ref="pickerContainer" class="min-h-[350px]"></div>
		</template>
		<template #actions>
			<Button variant="outline" class="w-full" @click="show = false">
				{{ __("Cancel") }}
			</Button>
		</template>
	</Dialog>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, inject } from "vue"
import { Dialog, Button, createResource } from "frappe-ui"

const props = defineProps({
	modelValue: Boolean,
	initialDate: String,
	showAttendanceIndicators: {
		type: Boolean,
		default: false,
	},
})
const emit = defineEmits(["update:modelValue", "dateSelected"])
const __ = inject("$translate")

const show = ref(props.modelValue)
const pickerContainer = ref(null)

watch(() => props.modelValue, (val) => {
	show.value = val
	if (val) {
		setTimeout(renderPicker, 100)
	}
})

watch(() => show.value, (val) => {
	emit("update:modelValue", val)
})

const dayjs = inject("$dayjs")
const attendanceEvents = createResource({
	url: "hrms.api.get_attendance_calendar_events",
	auto: props.showAttendanceIndicators,
	makeParams() {
		return {
			from_date: dayjs().subtract(1, 'year').startOf('year').format("YYYY-MM-DD"),
			to_date: dayjs().add(1, 'year').endOf('year').format("YYYY-MM-DD"),
		}
	},
})

watch(() => attendanceEvents.data, () => {
	if (show.value) renderPicker()
}, { deep: true })

const renderPicker = () => {
	if (!pickerContainer.value || !window.NepaliCalendarLib) return

	window.NepaliCalendarLib.render(pickerContainer.value, {
		selectedDateAD: props.initialDate,
		events: props.showAttendanceIndicators ? attendanceEvents.data : null,
		onSelect: (nepaliDate) => {
			const adDate = nepaliDate.format({ format: "YYYY-MM-DD", calendar: "AD" })
			emit("dateSelected", adDate)
			show.value = false
		}
	})
}

onBeforeUnmount(() => {
	if (pickerContainer.value && window.NepaliCalendarLib) {
		window.NepaliCalendarLib.unmount(pickerContainer.value)
	}
})
</script>
