<template>
	<div class="w-full bg-white rounded-2xl shadow-sm p-5">
		<div class="text-lg font-bold text-gray-900 mb-3">{{ __("Request Panel") }}</div>
		<TabButtons
			:buttons="TAB_BUTTONS"
			v-model="activeTab"
			variant="underline"
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
					<span>{{ __("Assigned to Me") }}</span>
					<span class="request-count">{{ assignedToMe.length }}</span>
				</summary>
				<RequestList
					:items="assignedToMe"
					:teamRequests="true"
					:emptyStateMessage="__('Nothing is waiting for your approval')"
				/>
			</details>
			<details open class="request-section">
				<summary class="request-section-title">
					<span>{{ __("Under My Approvers") }}</span>
					<span class="request-count">{{ underMyApprovers.length }}</span>
				</summary>
				<RequestList
					:items="underMyApprovers"
					:teamRequests="true"
					:emptyStateMessage="__('Nothing is waiting with the approvers who report to you')"
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
import { ref, inject, onMounted, computed, markRaw, watch } from "vue"

import TabButtons from "@/components/TabButtons.vue"
import RequestList from "@/components/RequestList.vue"

import {
	myAttendanceRequests,
	myShiftRequests,
	pendingOOOApprovals,
	approvedOOOApprovals,
} from "@/data/attendance"
import { myClaims, teamClaims } from "@/data/claims"
import { myLeaves } from "@/data/leaves"
import { recentlyApprovedTeamRequests } from "@/data/request_dashboard"
import { teamPendingRequests } from "@/data/team_requests"
import {
	myLateEntryApplications,
	myEarlyExitApplications,
	myOutOfOfficeApplications,
} from "@/data/cnr_applications"
import { isFinalDraft } from "@/utils/request_status"

import AttendanceRequestItem from "@/components/AttendanceRequestItem.vue"
import ExpenseClaimItem from "@/components/ExpenseClaimItem.vue"
import LeaveRequestItem from "@/components/LeaveRequestItem.vue"
import ShiftRequestItem from "@/components/ShiftRequestItem.vue"
import OOOApprovalItem from "@/components/OOOApprovalItem.vue"
import CnrApplicationItem from "@/components/CnrApplicationItem.vue"

import { useListUpdate } from "@/composables/realtime"

// Kept for the session so a pull-to-refresh, which re-renders the page, does
// not drop the approver back on My Requests.
const TAB_KEY = "nepal_hrms:request_panel_tab"
function savedTab() {
	try {
		return sessionStorage.getItem(TAB_KEY) || "My Requests"
	} catch (e) {
		return "My Requests"
	}
}
const activeTab = ref(savedTab())
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

// Expense Claims follow the claim's own approver, so they are always "mine".
const teamRequests = computed(() => {
	const claims = (teamClaims.data || []).map((claim) => ({ ...claim, assigned_to_me: true }))
	return updateRequestDetails({ data: teamPendingRequests.data || [] }, { data: claims })
})

const assignedToMe = computed(() => teamRequests.value.filter((r) => r.assigned_to_me))

const underMyApprovers = computed(() => teamRequests.value.filter((r) => !r.assigned_to_me))

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

// Approved means submitted. An approved draft has created nothing yet, so it
// stays pending until someone submits it.
function isApprovedRequest(request) {
	const status = getRequestStatus(request)
	if (["Rejected", "Cancelled"].includes(status)) return false
	return Number(request.docstatus) === 1
}

function isPendingRequest(request) {
	const status = getRequestStatus(request)
	return Number(request.docstatus) === 0 && status !== "Cancelled" && !isFinalDraft(request)
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

function reloadAll(resources) {
	resources.forEach((resource) => resource.reload())
}

function loadTab(tab) {
	if (tab === "Team Requests") {
		reloadAll([teamPendingRequests, teamClaims, recentlyApprovedTeamRequests])
	} else if (tab === "OOO Approvals") {
		reloadAll([pendingOOOApprovals, approvedOOOApprovals])
	}
}

watch(activeTab, (tab) => {
	try {
		sessionStorage.setItem(TAB_KEY, tab)
	} catch (e) {
		// Private mode: the tab just is not remembered.
	}
	loadTab(tab)
})

onMounted(() => {
	loadTab(activeTab.value)
	useListUpdate(socket, "Leave Application", () => {
		myLeaves.reload()
		teamPendingRequests.reload()
		recentlyApprovedTeamRequests.reload()
	})
	useListUpdate(socket, "Expense Claim", () => {
		myClaims.reload()
		teamClaims.reload()
		recentlyApprovedTeamRequests.reload()
	})
	useListUpdate(socket, "Shift Request", () => {
		myShiftRequests.reload()
		teamPendingRequests.reload()
		recentlyApprovedTeamRequests.reload()
	})
	useListUpdate(socket, "Attendance Request", () => {
		myAttendanceRequests.reload()
		teamPendingRequests.reload()
		recentlyApprovedTeamRequests.reload()
	})
	useListUpdate(socket, "Attendance", () => {
		pendingOOOApprovals.reload()
		approvedOOOApprovals.reload()
	})
	useListUpdate(socket, "Late Entry Application", () => {
		myLateEntryApplications.reload()
		teamPendingRequests.reload()
		recentlyApprovedTeamRequests.reload()
	})
	useListUpdate(socket, "Early Exit Application", () => {
		myEarlyExitApplications.reload()
		teamPendingRequests.reload()
		recentlyApprovedTeamRequests.reload()
	})
	useListUpdate(socket, "Out of Office Application", () => {
		myOutOfOfficeApplications.reload()
		teamPendingRequests.reload()
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
