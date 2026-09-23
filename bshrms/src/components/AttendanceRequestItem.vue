<template>
	<RequestRow
		icon="calendar"
		tone="red"
		:title="__(props.doc.reason || 'Attendance Request')"
		:subtitle="props.doc.explanation || ''"
		:meta="meta"
		:note="rejectionNote"
		:status="__(status.label)"
		:statusTheme="status.theme"
		:isTeamRequest="props.isTeamRequest"
		:employee="props.doc.employee"
		:employeeName="props.doc.employee_name"
		:cancellable="Number(props.doc.docstatus) === 0 && status.label === 'Pending'"
		doctype="Attendance Request"
		:name="props.doc.name"
		:owner="props.doc.owner"
	/>
</template>

<script setup>
import { computed, inject } from "vue"

import RequestRow from "@/components/RequestRow.vue"
import { formatDualPeriod } from "@/utils/nepali_date"
import { requestStatus } from "@/utils/request_status"

const __ = inject("$translate")

const props = defineProps({
	doc: { type: Object },
	isTeamRequest: { type: Boolean, default: false },
	workflowStateField: { type: String, required: false },
})

const meta = computed(() => [
	formatDualPeriod(props.doc.from_date, props.doc.to_date),
	props.doc.total_attendance_days ? __("{0}d", [props.doc.total_attendance_days]) : "",
])

const status = computed(() => requestStatus(props.doc, props.workflowStateField))

const rejectionNote = computed(() =>
	status.value.label === "Rejected" ? props.doc.custom_rejection_reason || "" : ""
)
</script>
