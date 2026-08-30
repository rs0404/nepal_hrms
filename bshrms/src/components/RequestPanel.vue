<template>
	<div class="w-full">
		<TabButtons
			:buttons="TAB_BUTTONS"
			v-model="activeTab"
		/>
		<RequestList v-if="activeTab == 'My Requests'" :items="myRequests" />
		<RequestList
			v-else-if="activeTab == 'Team Requests'"
			:items="teamRequests"
			:teamRequests="true"
		/>
		<RequestList
			v-else-if="activeTab == 'OOO Approvals'"
			:items="oooApprovals"
			:teamRequests="true"
		/>
	</div>
</template>

<script setup>
import { ref, inject, onMounted, computed, markRaw } from "vue"

import TabButtons from "@/components/TabButtons.vue"
import RequestList from "@/components/RequestList.vue"

import { myAttendanceRequests, myShiftRequests, teamShiftRequests, teamAttendanceRequests, pendingOOOApprovals } from "@/data/attendance"
import { myClaims, teamClaims } from "@/data/claims"
import { myLeaves, teamLeaves } from "@/data/leaves"
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

const oooApprovals = computed(() => {
	const approvals = [...(pendingOOOApprovals.data || [])]
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

	return getSortedRequests(requests)
}

function getSortedRequests(list) {
	return list
		.sort((a, b) => {
			return new Date(b.creation) - new Date(a.creation)
		})
		.splice(0, 12)
}

onMounted(() => {
	useListUpdate(socket, "Leave Application", () => teamLeaves.reload())
	useListUpdate(socket, "Expense Claim", () => teamClaims.reload())
	useListUpdate(socket, "Shift Request", () => teamShiftRequests.reload())
	useListUpdate(socket, "Attendance Request", () => teamAttendanceRequests.reload())
	useListUpdate(socket, "Attendance", () => pendingOOOApprovals.reload())
	useListUpdate(socket, "Late Entry Application", () => {
		myLateEntryApplications.reload()
		teamLateEntryApplications.reload()
	})
	useListUpdate(socket, "Early Exit Application", () => {
		myEarlyExitApplications.reload()
		teamEarlyExitApplications.reload()
	})
	useListUpdate(socket, "Out of Office Application", () => {
		myOutOfOfficeApplications.reload()
		teamOutOfOfficeApplications.reload()
	})
})
</script>
