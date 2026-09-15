<template>
	<ListItem
		:isTeamRequest="props.isTeamRequest"
		:employee="props.doc.employee"
		:employeeName="props.doc.employee_name"
	>
		<template #left>
			<LeaveIcon class="h-5 w-5 text-gray-500" />
			<div class="flex flex-col items-start gap-1.5">
				<div class="flex items-center flex-wrap gap-1">
					<span class="text-base font-normal text-gray-800">
						{{ __(props.doc.leave_type, null, "Leave Type") }}
					</span>
					<span
						v-for="mark in leaveMarks"
						:key="mark"
						class="leave-mark-badge"
						:class="leaveMarkClass(mark)"
					>
						{{ mark }}
					</span>
				</div>
				<div class="text-xs font-normal text-gray-500">
					<span>{{ formatNepaliPeriod(props.doc.from_date, props.doc.to_date) }}</span>
					<span class="whitespace-pre"> &middot; </span>
					<span class="whitespace-nowrap">{{ __("{0}d", [props.doc.total_leave_days]) }}</span>
					<span class="whitespace-pre"> &middot; </span>
					<span class="whitespace-nowrap">{{ formatDaysFromToday(props.doc.from_date) }}</span>
				</div>
			</div>
		</template>
		<template #right>
			<Badge variant="outline" :theme="colorMap[status]" :label="__(status, null, 'Leave Application')" size="md" />
			<FeatherIcon name="chevron-right" class="h-5 w-5 text-gray-500" />
		</template>
	</ListItem>
</template>

<script setup>
import { computed } from "vue"
import { FeatherIcon, Badge } from "frappe-ui"

import ListItem from "@/components/ListItem.vue"
import LeaveIcon from "@/components/icons/LeaveIcon.vue"
import { formatNepaliPeriod, formatDaysFromToday } from "@/utils/nepali_date"
import { leaveApplicationMarks, leaveMarkClass } from "@/utils/leave_marks"

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

const leaveMarks = computed(() => leaveApplicationMarks(props.doc))

const status = computed(() => {
	return props.workflowStateField ? props.doc[props.workflowStateField] : props.doc.status
})

const colorMap = {
	Approved: "green",
	Rejected: "red",
	Open: "orange",
}
</script>

<style scoped>
.leave-mark-badge {
	display: inline-block;
	font-size: 10px;
	font-weight: 700;
	line-height: 1;
	padding: 2px 4px;
	border-radius: 4px;
	letter-spacing: -0.02em;
	white-space: nowrap;
}

.leave-mark-badge.half {
	color: #1d4ed8;
	background: #dbeafe;
}

.leave-mark-badge.sick {
	color: #9a3412;
	background: #ffedd5;
}

.leave-mark-badge.home {
	color: #065f46;
	background: #d1fae5;
}
</style>
