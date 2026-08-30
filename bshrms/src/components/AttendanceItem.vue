<template>
	<ListItem>
		<template #left>
			<AttendanceIcon class="h-5 w-5 text-gray-500" />
			<div class="flex flex-col items-start gap-1.5 min-w-0">
				<div class="text-base font-medium text-gray-800">
					{{ formatNepaliDate(props.doc.attendance_date) }}
					<span class="text-xs text-gray-500 font-normal ml-1">
						({{ dayjs(props.doc.attendance_date).format("D MMM") }})
					</span>
				</div>
				<div class="text-xs font-normal text-gray-500 truncate max-w-[220px]">
					<span v-if="props.doc.in_time || props.doc.out_time">
						{{ formatTime(props.doc.in_time) }}
						–
						{{ formatTime(props.doc.out_time) }}
					</span>
					<span v-else>{{ __("No check-in times") }}</span>
					<span v-if="props.doc.working_hours != null" class="ml-1">
						&middot; {{ Number(props.doc.working_hours).toFixed(1) }}h
					</span>
				</div>
				<div
					v-if="props.doc.leave_application || props.doc.attendance_request"
					class="flex flex-wrap gap-1.5 text-[10px] text-blue-600"
				>
					<span v-if="props.doc.leave_application">
						{{ __("Leave") }}: {{ props.doc.leave_application }}
					</span>
					<span v-if="props.doc.attendance_request">
						{{ __("Att. Request") }}: {{ props.doc.attendance_request }}
					</span>
				</div>
			</div>
		</template>
		<template #right>
			<Badge
				variant="outline"
				:theme="colorMap[props.doc.status] || 'gray'"
				:label="__(props.doc.status)"
				size="md"
			/>
		</template>
	</ListItem>
</template>

<script setup>
import { inject } from "vue"
import { Badge } from "frappe-ui"

import ListItem from "@/components/ListItem.vue"
import AttendanceIcon from "@/components/icons/AttendanceIcon.vue"
import { formatNepaliDate } from "@/utils/nepali_date"

const dayjs = inject("$dayjs")
const __ = inject("$translate")

const props = defineProps({
	doc: {
		type: Object,
		required: true,
	},
})

const colorMap = {
	Present: "green",
	"Work From Home": "green",
	"Half Day": "orange",
	Absent: "red",
	"On Leave": "blue",
	Holiday: "gray",
}

const formatTime = (t) => {
	if (!t) return "—"
	return dayjs(t).isValid() ? dayjs(t).format("hh:mm a") : String(t).slice(0, 5)
}
</script>
