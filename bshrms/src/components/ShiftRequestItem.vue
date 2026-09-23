<template>
	<RequestRow
		icon="watch"
		tone="red"
		:title="props.doc.shift_type || __('Shift Request')"
		:meta="meta"
		:status="__(status.label)"
		:statusTheme="status.theme"
		:isTeamRequest="props.isTeamRequest"
		:employee="props.doc.employee"
		:employeeName="props.doc.employee_name"
	/>
</template>

<script setup>
import { computed, inject } from "vue"

import RequestRow from "@/components/RequestRow.vue"
import { getTotalDays } from "@/data/attendance"
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
	props.doc.to_date ? __("{0}d", [props.doc.total_shift_days || getTotalDays(props.doc)]) : "",
])

const status = computed(() => requestStatus(props.doc, props.workflowStateField))
</script>
