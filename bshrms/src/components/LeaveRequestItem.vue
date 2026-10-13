<template>
	<RequestRow
		icon="calendar"
		tone="blue"
		:title="__(props.doc.leave_type, null, 'Leave Type')"
		:meta="meta"
		:status="__(status.label, null, 'Leave Application')"
		:statusTheme="status.theme"
		:isTeamRequest="props.isTeamRequest"
		:employee="props.doc.employee"
		:employeeName="props.doc.employee_name"
		:cancellable="status.label === 'Open'"
		doctype="Leave Application"
		:name="props.doc.name"
		:owner="props.doc.owner"
	>
		<template #title-extra>
			<span
				v-for="mark in leaveMarks"
				:key="mark"
				class="leave-mark-badge"
				:class="leaveMarkClass(mark)"
			>
				{{ mark }}
			</span>
			<!-- Which part of the day: full, 1st half or 2nd half. -->
			<LeaveSpanMark :span="span" :title="spanLabel" />
		</template>
	</RequestRow>
</template>

<script setup>
import { computed, inject } from "vue"

import RequestRow from "@/components/RequestRow.vue"
import LeaveSpanMark from "@/components/LeaveSpanMark.vue"
import { formatDualPeriod } from "@/utils/nepali_date"
import { isAwaitingSubmit, notSubmittedLabel } from "@/utils/request_status"
import {
	leaveApplicationMarks,
	leaveMarkClass,
	leaveSpan,
	leaveSpanLabel,
} from "@/utils/leave_marks"

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

const __ = inject("$translate")

const leaveMarks = computed(() => leaveApplicationMarks(props.doc))
const span = computed(() => leaveSpan(props.doc))
const spanLabel = computed(() =>
	leaveSpanLabel(span.value, __, props.doc?.from_date !== props.doc?.to_date)
)

const meta = computed(() => [
	formatDualPeriod(props.doc.from_date, props.doc.to_date),
	props.doc.total_leave_days ? __("{0}d", [props.doc.total_leave_days]) : "",
])

// Leave has its own status field (Open / Approved / Rejected / Cancelled).
const THEMES = { Approved: "green", Rejected: "red", Open: "orange", Cancelled: "gray" }

const status = computed(() => {
	if (!props.workflowStateField && isAwaitingSubmit(props.doc)) {
		return { label: notSubmittedLabel(props.doc.status), theme: "orange" }
	}
	const label =
		(props.workflowStateField ? props.doc[props.workflowStateField] : props.doc.status) || "Open"
	return { label, theme: THEMES[label] || "gray" }
})
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

.leave-mark-badge.lwp {
	color: #334155;
	background: #e2e8f0;
}
</style>
