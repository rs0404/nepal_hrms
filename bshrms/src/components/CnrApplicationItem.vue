<template>
	<ListItem
		:isTeamRequest="props.isTeamRequest"
		:employee="props.doc.employee"
		:employeeName="props.doc.employee_name"
	>
		<template #left>
			<div
				class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600"
			>
				{{ shortLabel }}
			</div>
			<div class="flex flex-col items-start gap-1 min-w-0">
				<div class="text-base font-medium text-gray-800 truncate max-w-[210px]">
					{{ title }}
				</div>
				<div class="text-xs font-normal text-gray-500">
					<span>{{ formatNepaliDate(props.doc.attendance_date) }}</span>
					<span class="whitespace-pre"> · </span>
					<span>{{ formatDaysFromToday(props.doc.attendance_date) }}</span>
					<span v-if="props.doc.type_of_work">
						<span class="whitespace-pre"> · </span>{{ __(props.doc.type_of_work) }}
					</span>
					<span v-if="props.doc.total_hours">
						<span class="whitespace-pre"> · </span>{{ props.doc.total_hours }}h
					</span>
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
import { inject } from "vue"

import ListItem from "@/components/ListItem.vue"
import { formatNepaliDate, formatDaysFromToday } from "@/utils/nepali_date"

const __ = inject("$translate")

const props = defineProps({
	doc: { type: Object, required: true },
	workflowStateField: { type: String, required: false },
	isTeamRequest: { type: Boolean, default: false },
})

const shortLabel = computed(() => {
	const dt = props.doc.doctype || ""
	if (dt.includes("Late")) return "L"
	if (dt.includes("Early")) return "E"
	return "O"
})

const title = computed(() => {
	const reason = (props.doc.reason || "").trim()
	if (reason) return reason.length > 48 ? reason.slice(0, 48) + "…" : reason
	return __(props.doc.doctype || "Application")
})

const status = computed(() => {
	if (props.workflowStateField) return props.doc[props.workflowStateField]
	if (props.doc.docstatus === 1) return "Submitted"
	if (props.doc.docstatus === 2) return "Cancelled"
	if ((props.doc.status || "Draft") === "Draft") return "Waiting for Approval"
	return props.doc.status
})

const colorMap = {
	Draft: "orange",
	"Waiting for Approval": "orange",
	Approved: "green",
	Rejected: "red",
	Submitted: "blue",
	Cancelled: "orange",
}
</script>
