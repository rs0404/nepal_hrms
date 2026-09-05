<template>
	<div class="w-full">
		<TabButtons
			:buttons="TAB_BUTTONS"
			v-model="activeTab"
		/>
		<div v-if="activeTab == 'My Requests'" class="flex flex-col gap-5">
			<details open class="request-section mt-4">
				<summary class="request-section-title">
					<span>{{ __("Pending Approval") }}</span>
					<span class="request-count">{{ myPendingRequests.length }}</span>
				</summary>
				<RequestList
					:items="myPendingRequests"
					:emptyStateMessage="__('You have no pending requests')"
				/>
			</details>
			<details open class="request-section">
				<summary class="request-section-title">
					<span>{{ __("Recently Approved") }}</span>
					<span class="request-count">{{ myApprovedRequests.length }}</span>
				</summary>
				<RequestList
					:items="myApprovedRequests"
					:emptyStateMessage="__('You have no recently approved requests')"
				/>
			</details>
		</div>
		<div v-else-if="activeTab == 'Team Requests'" class="flex flex-col gap-5">
			<details open class="request-section mt-4">
				<summary class="request-section-title">
					<span>{{ __("Pending Approval") }}</span>
					<span class="request-count">{{ teamRequests.length }}</span>
				</summary>
				<RequestList
					:items="teamRequests"
					:teamRequests="true"
					:emptyStateMessage="__('You have no pending team requests')"
				/>
			</details>
			<details open class="request-section">
				<summary class="request-section-title">
					<span>{{ __("Recently Approved") }}</span>
					<span class="request-count">{{ teamApprovedRequests.length }}</span>
				</summary>
				<RequestList
					:items="teamApprovedRequests"
					:teamRequests="true"
					:emptyStateMessage="__('No recently approved team requests')"
				/>
			</details>
		</div>
		<div v-else-if="activeTab == 'OOO Approvals'" class="flex flex-col gap-5">
			<details open class="request-section mt-4">
				<summary class="request-section-title">
					<span>{{ __("Pending Approval") }}</span>
					<span class="request-count">{{ oooApprovals.length }}</span>
				</summary>
				<RequestList
					:items="oooApprovals"
					:teamRequests="true"
					:emptyStateMessage="__('You have no pending OOO approvals')"
				/>
			</details>
			<details open class="request-section">
				<summary class="request-section-title">
					<span>{{ __("Recently Approved") }}</span>
					<span class="request-count">{{ approvedOOOItems.length }}</span>
				</summary>
				<RequestList
					:items="approvedOOOItems"
					:teamRequests="true"
					:emptyStateMessage="__('No recently approved OOO work')"
				/>
			</details>
		</div>
	</div>
</template>

<script setup>
import { ref, inject, onMounted, computed, markRaw } from "vue"

import TabButtons from "@/components/TabButtons.vue"
import RequestList from "@/components/RequestList.vue"

import {
	myAttendanceRequests,
	myShiftRequests,
	teamShiftRequests,
	teamAttendanceRequests,
	pendingOOOApprovals,
	approvedOOOApprovals,
} from "@/data/attendance"
import { myClaims, teamClaims } from "@/data/claims"
import { myLeaves, teamLeaves } from "@/data/leaves"
import { recentlyApprovedTeamRequests } from "@/data/request_dashboard"
import {
	myLateEntryApplications,
	myEarlyExitApplications,
	myOutOfOfficeApplications,
	teamLateEntryApplications,
	teamEarlyExitApplications,
	teamOutOfOfficeApplications,
} from "@/data/cnr_applications"

import AttendanceRequestItem from "@/components/AttendanceRequestItem.vue"
import ExpenseClaimItem from "@/components/ExpenseClaimItem.vue"
import LeaveRequestItem from "@/components/LeaveRequestItem.vue"
import ShiftRequestItem from "@/components/ShiftRequestItem.vue"
import OOOApprovalItem from "@/components/OOOApprovalItem.vue"
import CnrApplicationItem from "@/components/CnrApplicationItem.vue"

import { useListUpdate } from "@/composables/realtime"

const activeTab = ref("My Requests")
const socket = inject("$socket")

const TAB_BUTTONS = ["My Requests", "Team Requests", "OOO Approvals"]

const myRequests = computed(() =>
	updateRequestDetails(
		myLeaves,
		myClaims,
		myShiftRequests,
		myAttendanceRequests,
		myLateEntryApplications,
		myEarlyExitApplications,
		myOutOfOfficeApplications
	)
)

const teamRequests = computed(() =>
	getSortedRequests(
		updateRequestDetails(
			teamLeaves,
			teamClaims,
			teamShiftRequests,
			teamAttendanceRequests,
			teamLateEntryApplications,
			teamEarlyExitApplications,
			teamOutOfOfficeApplications
		)
	)
)

const myPendingRequests = computed(() =>
	getSortedRequests(myRequests.value.filter((request) => isPendingRequest(request)))
)

const myApprovedRequests = computed(() =>
	getSortedRequests(myRequests.value.filter((request) => isApprovedRequest(request)))
)

const teamApprovedRequests = computed(() =>
	getSortedRequests(
		updateRequestDetails({ data: [...(recentlyApprovedTeamRequests.data || [])] })
	)
)

const oooApprovals = computed(() => {
	const approvals = [...(pendingOOOApprovals.data || [])]
	approvals.forEach((item) => {
		item.component = markRaw(OOOApprovalItem)
		item.creation = item.attendance_date
	})
	return getSortedRequests(approvals)
})

const approvedOOOItems = computed(() => {
	const approvals = [...(approvedOOOApprovals.data || [])]
	approvals.forEach((item) => {
		item.component = markRaw(OOOApprovalItem)
		item.creation = item.attendance_date
	})
	return getSortedRequests(approvals)
})

function updateRequestDetails(...resources) {
	const requests = resources.reduce(
		(acc, resource) => acc.concat(resource?.data || []),
		[]
	)

	const componentMap = {
		"Leave Application": LeaveRequestItem,
		"Expense Claim": ExpenseClaimItem,
		"Shift Request": ShiftRequestItem,
		"Attendance Request": AttendanceRequestItem,
		"Late Entry Application": CnrApplicationItem,
		"Early Exit Application": CnrApplicationItem,
		"Out of Office Application": CnrApplicationItem,
	}
	requests.forEach((request) => {
		request.component = markRaw(componentMap[request.doctype] || CnrApplicationItem)
	})

	return requests.sort(
		(a, b) =>
			new Date(b.modified || b.creation) - new Date(a.modified || a.creation)
	)
}

function getRequestStatus(request) {
	if (request.workflow_state_field && request[request.workflow_state_field]) {
		return request[request.workflow_state_field]
	}
	if (request.approval_status) return request.approval_status
	return request.status || ""
}

function isApprovedRequest(request) {
	const status = getRequestStatus(request)
	if (["Rejected", "Cancelled"].includes(status)) return false
	return status === "Approved" || Number(request.docstatus) === 1
}

function isPendingRequest(request) {
	const status = getRequestStatus(request)
	return (
		Number(request.docstatus) === 0 &&
		!["Approved", "Rejected", "Cancelled"].includes(status)
	)
}

function getSortedRequests(list) {
	return list
		.sort((a, b) => {
			return (
				new Date(b.modified || b.creation) -
				new Date(a.modified || a.creation)
			)
		})
		.slice(0, 12)
}

onMounted(() => {
	useListUpdate(socket, "Leave Application", () => {
		myLeaves.reload()
		teamLeaves.reload()
		recentlyApprovedTeamRequests.reload()
	})
	useListUpdate(socket, "Expense Claim", () => {
		myClaims.reload()
		teamClaims.reload()
		recentlyApprovedTeamRequests.reload()
	})
	useListUpdate(socket, "Shift Request", () => {
		myShiftRequests.reload()
		teamShiftRequests.reload()
		recentlyApprovedTeamRequests.reload()
	})
	useListUpdate(socket, "Attendance Request", () => {
		myAttendanceRequests.reload()
		teamAttendanceRequests.reload()
		recentlyApprovedTeamRequests.reload()
	})
	useListUpdate(socket, "Attendance", () => {
		pendingOOOApprovals.reload()
		approvedOOOApprovals.reload()
	})
	useListUpdate(socket, "Late Entry Application", () => {
		myLateEntryApplications.reload()
		teamLateEntryApplications.reload()
		recentlyApprovedTeamRequests.reload()
	})
	useListUpdate(socket, "Early Exit Application", () => {
		myEarlyExitApplications.reload()
		teamEarlyExitApplications.reload()
		recentlyApprovedTeamRequests.reload()
	})
	useListUpdate(socket, "Out of Office Application", () => {
		myOutOfOfficeApplications.reload()
		teamOutOfOfficeApplications.reload()
		recentlyApprovedTeamRequests.reload()
	})
})
</script>

<style scoped>
.request-section-title {
	@apply flex cursor-pointer select-none items-center gap-2 text-sm font-semibold text-gray-700;
}

.request-count {
	@apply inline-flex min-w-5 items-center justify-center rounded-full bg-gray-100 px-1.5 py-0.5 text-xs font-semibold text-gray-600;
}
</style>
