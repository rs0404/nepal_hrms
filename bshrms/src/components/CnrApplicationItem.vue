<template>
	<RequestRow
		:icon="kind.icon"
		:tone="kind.tone"
		:title="__(kind.title)"
		:subtitle="reason"
		:meta="meta"
		:note="rejectionNote"
		:status="__(status.label)"
		:statusTheme="status.theme"
		:isTeamRequest="props.isTeamRequest"
		:employee="props.doc.employee"
		:employeeName="props.doc.employee_name"
		:cancellable="Number(props.doc.docstatus) === 0 && status.label === 'Pending'"
		:doctype="props.doc.doctype"
		:name="props.doc.name"
		:owner="props.doc.owner"
	/>
</template>

<script setup>
import { computed, inject } from "vue"

import RequestRow from "@/components/RequestRow.vue"
import { formatDualDate, formatShortTime } from "@/utils/nepali_date"
import { requestStatus } from "@/utils/request_status"

const __ = inject("$translate")

const props = defineProps({
	doc: { type: Object, required: true },
	workflowStateField: { type: String, required: false },
	isTeamRequest: { type: Boolean, default: false },
})

// Same icons as the Quick Links that open these forms.
const KINDS = {
	"Late Entry Application": { icon: "clock", tone: "orange", title: "Late Entry" },
	"Early Exit Application": { icon: "log-out", tone: "purple", title: "Early Exit" },
	"Out of Office Application": { icon: "briefcase", tone: "blue", title: "Out of Office" },
}

const kind = computed(() => KINDS[props.doc.doctype] || KINDS["Out of Office Application"])

const reason = computed(() => (props.doc.reason || "").trim())

const timing = computed(() => {
	const doc = props.doc
	if (doc.doctype === "Late Entry Application") {
		const expected = formatShortTime(doc.estimated_late_entry_time)
		const actual = formatShortTime(doc.late_entry_time)
		if (actual) return __("Arrived {0}", [actual])
		return expected ? __("Expected {0}", [expected]) : ""
	}
	if (doc.doctype === "Early Exit Application") {
		const time = formatShortTime(doc.early_exit_time)
		return time ? __("Leaving {0}", [time]) : ""
	}
	const from = formatShortTime(doc.from_time) || formatShortTime(doc.estimated_from_time)
	const to = formatShortTime(doc.to_time) || formatShortTime(doc.estimated_to_time)
	if (!from && !to) return ""
	return `${from || "?"} – ${to || "?"}`
})

const meta = computed(() => [
	formatDualDate(props.doc.attendance_date),
	timing.value,
	props.doc.total_hours ? `${props.doc.total_hours}h` : "",
	props.doc.type_of_work ? __(props.doc.type_of_work) : "",
])

const status = computed(() => requestStatus(props.doc, props.workflowStateField))

const rejectionNote = computed(() =>
	status.value.label === "Rejected" ? props.doc.custom_rejection_reason || "" : ""
)
</script>
