<template>
	<RequestRow
		icon="file-text"
		tone="blue"
		:title="claimTitle"
		:meta="meta"
		:status="__(status, null, 'Expense Claim')"
		:statusTheme="statusMap[status] || 'gray'"
		:isTeamRequest="props.isTeamRequest"
		:employee="props.doc.employee"
		:employeeName="props.doc.employee_name"
	/>
</template>

<script setup>
import { computed, inject } from "vue"

import RequestRow from "@/components/RequestRow.vue"

import { getCompanyCurrency } from "@/data/currencies"
import { formatCurrency } from "@/utils/formatters"
import { formatDualDate, formatDualPeriod } from "@/utils/nepali_date"

const __ = inject("$translate")
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

const statusMap = {
	Draft: "orange",
	Submitted: "blue",
	Cancelled: "gray",
	Paid: "green",
	Unpaid: "orange",
	"Approved & Draft": "green",
	"Approved & Unpaid": "green",
	"Approved & Submitted": "blue",
	Rejected: "red",
}

const status = computed(() => {
	if (props.workflowStateField) {
		return props.doc[props.workflowStateField]
	} else if (
		props.doc.approval_status === "Approved" &&
		["Draft", "Unpaid", "Submitted"].includes(props.doc.status)
	) {
		return `${props.doc.approval_status} & ${props.doc.status}`
	} else if (props.doc.approval_status === "Rejected") {
		return "Rejected"
	}
	return props.doc.status
})

const claimTitle = computed(() => {
	let title = __(props.doc.expense_type)
	if (props.doc.total_expenses > 1) {
		title = __("{0} & {1} more", [title, props.doc.total_expenses - 1])
	}
	return title
})

const meta = computed(() => {
	const from = props.doc.from_date || props.doc.posting_date
	const to = props.doc.to_date
	return [
		from && to ? formatDualPeriod(from, to) : formatDualDate(from),
		formatCurrency(props.doc.total_claimed_amount, currency.value),
	]
})

const currency = computed(() => getCompanyCurrency(props.doc.company))

const approvalStatus = computed(() => {
	return props.doc.approval_status === "Draft" ? "Pending" : props.doc.approval_status
})
</script>
