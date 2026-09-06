<template>
	<ListItem
		:isTeamRequest="props.isTeamRequest"
		:employee="props.doc.employee"
		:employeeName="props.doc.employee_name"
	>
		<template #left>
			<AttendanceIcon class="h-5 w-5 text-gray-500" />
			<div class="flex flex-col items-start gap-1.5">
				<div class="text-base font-normal text-gray-800">
					{{ props.doc.reason }}
				</div>
				<div class="text-xs font-normal text-gray-500">
					<span>{{ formatNepaliPeriod(props.doc.from_date, props.doc.to_date) }}</span>
					<span v-if="props.doc.to_date">
						<span class="whitespace-pre"> &middot; </span>
						<span class="whitespace-nowrap">{{
							__("{0}d", [props.doc.total_attendance_days])
						}}</span>
					</span>
					<span class="whitespace-pre"> &middot; </span>
					<span class="whitespace-nowrap">{{ formatDaysFromToday(props.doc.from_date) }}</span>
				</div>
				<div
					v-if="props.doc.status === 'Rejected' && props.doc.custom_rejection_reason"
					class="text-[11px] text-red-600 truncate max-w-[220px]"
				>
					{{ props.doc.custom_rejection_reason }}
				</div>
			</div>
		</template>
		<template #right>
			<Badge variant="outline" :theme="colorMap[status] || 'gray'" :label="__(status)" size="md" />
			<FeatherIcon name="chevron-right" class="h-5 w-5 text-gray-500" />
		</template>
	</ListItem>
</template>

<script setup>
import { computed } from "vue"
import { Badge, FeatherIcon } from "frappe-ui"

import ListItem from "@/components/ListItem.vue"
import AttendanceIcon from "@/components/icons/AttendanceIcon.vue"
import { formatNepaliPeriod, formatDaysFromToday } from "@/utils/nepali_date"

const props = defineProps({
	doc: {
		type: Object,
	},
	isTeamRequest: {
		type: Boolean,
		default: false,
	},
	workflowStateField: {
		type: String,
		required: false,
	},
})

const status = computed(() => {
	if (props.workflowStateField) return props.doc[props.workflowStateField]
	if (props.doc.docstatus === 1) return "Submitted"
	if (props.doc.docstatus === 2) return "Cancelled"
	return props.doc.status || "Open"
})

const colorMap = {
	Open: "orange",
	Draft: "gray",
	Approved: "green",
	Rejected: "red",
	Submitted: "blue",
	Cancelled: "gray",
}
</script>
