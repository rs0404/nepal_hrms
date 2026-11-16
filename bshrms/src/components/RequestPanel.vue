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
			<!-- Filters, and the switch into bulk selection -->
			<div class="mt-4 flex flex-col gap-2">
				<div class="grid grid-cols-2 gap-2">
					<select v-model="filters.employee" class="filter-select col-span-2">
						<option value="">{{ __("All Employees") }}</option>
						<option v-for="e in employeeOptions" :key="e.value" :value="e.value">
							{{ e.label }}
						</option>
					</select>
					<select
						v-model="filters.doctype"
						class="filter-select"
						:class="filters.doctype === 'Leave Application' ? '' : 'col-span-2'"
					>
						<option value="">{{ __("All Types") }}</option>
						<option v-for="dt in doctypeOptions" :key="dt" :value="dt">{{ __(dt) }}</option>
					</select>
					<select
						v-if="filters.doctype === 'Leave Application'"
						v-model="filters.leave_type"
						class="filter-select"
					>
						<option value="">{{ __("All Leave Types") }}</option>
						<option v-for="lt in leaveTypeOptions" :key="lt" :value="lt">{{ __(lt) }}</option>
					</select>
				</div>
				<div class="flex items-center justify-between gap-2">
					<button
						v-if="hasFilters"
						type="button"
						class="text-sm text-gray-600 underline"
						@click="clearFilters"
					>
						{{ __("Clear filters") }}
					</button>
					<span v-else />
					<Button
						v-if="selectableRequests.length"
						size="sm"
						:variant="selecting ? 'solid' : 'subtle'"
						@click="toggleSelecting"
					>
						<template #prefix>
							<FeatherIcon :name="selecting ? 'x' : 'check-square'" class="w-4" />
						</template>
						{{ selecting ? __("Done") : __("Select") }}
					</Button>
				</div>
			</div>

			<!-- Bulk actions -->
			<div
				v-if="selecting"
				class="sticky top-0 z-10 -mx-1 flex flex-col gap-2 rounded-xl border border-gray-200 bg-white p-3 shadow-sm"
			>
				<div class="flex items-center justify-between text-sm">
					<span class="font-semibold text-gray-800">
						{{ __("{0} selected", [selectedKeys.size]) }}
					</span>
					<button type="button" class="text-gray-600 underline" @click="toggleSelectAll">
						{{ allSelected ? __("Select none") : __("Select all ({0})", [selectableRequests.length]) }}
					</button>
				</div>
				<div class="flex gap-2">
					<Button
						class="w-full"
						variant="subtle"
						theme="red"
						:disabled="!selectedKeys.size"
						@click="openBulkDialog('Rejected')"
					>
						<template #prefix><FeatherIcon name="x" class="w-4" /></template>
						{{ __("Reject") }}
					</Button>
					<Button
						class="w-full"
						variant="solid"
						theme="green"
						:disabled="!selectedKeys.size"
						@click="openBulkDialog('Approved')"
					>
						<template #prefix><FeatherIcon name="check" class="w-4" /></template>
						{{ __("Approve") }}
					</Button>
				</div>
			</div>

			<details open class="request-section">
				<summary class="request-section-title">
					<span>{{ __("Assigned to Me") }}</span>
					<span class="request-count">{{ assignedToMe.length }}</span>
				</summary>
				<RequestList
					:items="assignedToMe"
					:teamRequests="true"
					:selecting="selecting"
					:selectable="isBulkSelectable"
					:selectedKeys="selectedKeys"
					@toggle="toggleSelected"
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
					:selecting="selecting"
					:selectable="isBulkSelectable"
					:selectedKeys="selectedKeys"
					@toggle="toggleSelected"
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

			<Dialog v-model="bulkDialog.open">
				<template #body-title>
					<h2 class="text-lg font-bold">
						{{
							bulkDialog.status === "Approved"
								? __("Approve {0} requests?", [selectedKeys.size])
								: __("Reject {0} requests?", [selectedKeys.size])
						}}
					</h2>
				</template>
				<template #body-content>
					<div class="flex flex-col gap-3">
						<p class="text-sm text-gray-600">
							{{ __("Each request is decided and submitted at once. This cannot be changed afterwards.") }}
						</p>
						<ul class="max-h-40 overflow-auto text-sm text-gray-700 flex flex-col gap-1">
							<li v-for="r in selectedRequests" :key="r.doctype + r.name" class="truncate">
								{{ r.employee_name || r.employee }} · {{ __(r.leave_type || r.doctype) }}
							</li>
						</ul>
						<textarea
							v-if="bulkDialog.status === 'Rejected'"
							v-model="bulkDialog.reason"
							rows="3"
							class="w-full border border-gray-300 rounded-lg p-3 text-sm text-gray-900 bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400"
							:placeholder="__('Rejection reason (sent with every request)')"
						/>
						<div v-if="bulkDialog.failed.length" class="rounded-lg bg-red-50 p-2 text-xs text-red-800 flex flex-col gap-1">
							<div class="font-semibold">{{ __("These could not be done:") }}</div>
							<div v-for="f in bulkDialog.failed" :key="f.doctype + f.name">
								{{ f.name }}: {{ f.error }}
							</div>
						</div>
					</div>
				</template>
				<template #actions>
					<div class="flex gap-2 w-full">
						<Button class="flex-1" variant="outline" @click="bulkDialog.open = false">
							{{ __("Back") }}
						</Button>
						<Button
							class="flex-1"
							variant="solid"
							:theme="bulkDialog.status === 'Approved' ? 'green' : 'red'"
							:loading="bulkDialog.running"
							:disabled="!selectedKeys.size || (bulkDialog.status === 'Rejected' && !bulkDialog.reason.trim())"
							@click="runBulk"
						>
							{{ bulkDialog.status === "Approved" ? __("Approve & Submit") : __("Reject & Submit") }}
						</Button>
					</div>
				</template>
			</Dialog>
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
import { ref, reactive, inject, onMounted, computed, markRaw, watch } from "vue"
import { Dialog, FeatherIcon, call, toast } from "frappe-ui"

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
const __ = inject("$translate")

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

// Expense Claims come from stock HRMS without comment counts; fetch them here.
const claimCommentCounts = ref({})
watch(
	() => teamClaims.data,
	async (claims) => {
		if (!claims?.length) return
		try {
			claimCommentCounts.value = await call(
				"nepal_hrms.api.request_comments.get_comment_counts",
				{ requests: claims.map((c) => ({ doctype: "Expense Claim", name: c.name })) }
			)
		} catch (e) {
			// The badge is a hint; the list works without it.
		}
	}
)

// Expense Claims follow the claim's own approver, so they are always "mine".
const teamRequests = computed(() => {
	const claims = (teamClaims.data || []).map((claim) => ({
		...claim,
		doctype: claim.doctype || "Expense Claim",
		assigned_to_me: true,
		comment_count: claimCommentCounts.value[`Expense Claim::${claim.name}`] || 0,
	}))
	return updateRequestDetails({ data: teamPendingRequests.data || [] }, { data: claims })
})

const filteredTeamRequests = computed(() => applyFilters(teamRequests.value))

const assignedToMe = computed(() => filteredTeamRequests.value.filter((r) => r.assigned_to_me))

const underMyApprovers = computed(() => filteredTeamRequests.value.filter((r) => !r.assigned_to_me))

const myPendingRequests = computed(() =>
	getSortedRequests(myRequests.value.filter((request) => isPendingRequest(request)))
)

const myApprovedRequests = computed(() =>
	getSortedRequests(myRequests.value.filter((request) => isApprovedRequest(request)))
)

const allTeamApproved = computed(() =>
	updateRequestDetails({ data: [...(recentlyApprovedTeamRequests.data || [])] })
)

const teamApprovedRequests = computed(() =>
	getSortedRequests(applyFilters(allTeamApproved.value))
)

// --- Team Requests filters ---------------------------------------------------
const filters = reactive({ employee: "", doctype: "", leave_type: "" })

const teamRows = computed(() => [...teamRequests.value, ...allTeamApproved.value])

const employeeOptions = computed(() => {
	const seen = new Map()
	teamRows.value.forEach((r) => {
		if (r.employee && !seen.has(r.employee)) {
			seen.set(r.employee, { value: r.employee, label: r.employee_name || r.employee })
		}
	})
	return [...seen.values()].sort((a, b) => a.label.localeCompare(b.label))
})

const doctypeOptions = computed(() =>
	[...new Set(teamRows.value.map((r) => r.doctype).filter(Boolean))].sort()
)

const leaveTypeOptions = computed(() =>
	[
		...new Set(
			teamRows.value
				.filter((r) => r.doctype === "Leave Application" && r.leave_type)
				.map((r) => r.leave_type)
		),
	].sort()
)

const hasFilters = computed(() => !!(filters.employee || filters.doctype || filters.leave_type))

function applyFilters(list) {
	return list.filter(
		(r) =>
			(!filters.employee || r.employee === filters.employee) &&
			(!filters.doctype || r.doctype === filters.doctype) &&
			(!filters.leave_type || r.leave_type === filters.leave_type)
	)
}

function clearFilters() {
	filters.employee = ""
	filters.doctype = ""
	filters.leave_type = ""
}

watch(
	() => filters.doctype,
	(doctype) => {
		if (doctype !== "Leave Application") filters.leave_type = ""
	}
)

// --- Bulk approve / reject ---------------------------------------------------
// Expense Claims follow their own approver flow, and a rejected Attendance
// Request is already final, so neither can be bulk-decided.
const BULK_DOCTYPES = [
	"Leave Application",
	"Attendance Request",
	"Shift Request",
	"Late Entry Application",
	"Early Exit Application",
	"Out of Office Application",
]

const selecting = ref(false)
const selectedKeys = ref(new Set())
const bulkDialog = reactive({ open: false, status: "", reason: "", running: false, failed: [] })

const requestKey = (r) => `${r.doctype}::${r.name}`

function isBulkSelectable(r) {
	return BULK_DOCTYPES.includes(r.doctype) && Number(r.docstatus) === 0 && !isFinalDraft(r)
}

const selectableRequests = computed(() =>
	[...assignedToMe.value, ...underMyApprovers.value].filter(isBulkSelectable)
)

const selectedRequests = computed(() =>
	selectableRequests.value.filter((r) => selectedKeys.value.has(requestKey(r)))
)

const allSelected = computed(
	() =>
		selectableRequests.value.length > 0 &&
		selectableRequests.value.every((r) => selectedKeys.value.has(requestKey(r)))
)

// A filter change hides rows; keep only what is still on screen selected.
watch(selectableRequests, (rows) => {
	const visible = new Set(rows.map(requestKey))
	const kept = [...selectedKeys.value].filter((k) => visible.has(k))
	if (kept.length !== selectedKeys.value.size) selectedKeys.value = new Set(kept)
})

function toggleSelecting() {
	selecting.value = !selecting.value
	selectedKeys.value = new Set()
}

function toggleSelected(r) {
	const next = new Set(selectedKeys.value)
	const key = requestKey(r)
	next.has(key) ? next.delete(key) : next.add(key)
	selectedKeys.value = next
}

function toggleSelectAll() {
	selectedKeys.value = allSelected.value
		? new Set()
		: new Set(selectableRequests.value.map(requestKey))
}

function openBulkDialog(status) {
	Object.assign(bulkDialog, { open: true, status, reason: "", failed: [] })
}

async function runBulk() {
	bulkDialog.running = true
	try {
		const result = await call("nepal_hrms.api.team_requests.bulk_decide_team_requests", {
			requests: selectedRequests.value.map((r) => ({ doctype: r.doctype, name: r.name })),
			status: bulkDialog.status,
			rejection_reason: bulkDialog.status === "Rejected" ? bulkDialog.reason.trim() : null,
		})
		const done = result?.done || []
		const failed = result?.failed || []
		if (done.length) {
			toast({
				title: __("Success"),
				text:
					bulkDialog.status === "Approved"
						? __("{0} approved and submitted", [done.length])
						: __("{0} rejected", [done.length]),
				icon: "check-circle",
				position: "bottom-center",
				iconClasses: "text-green-500",
			})
		}
		// Keep the failures selected and listed so they can be looked at one by one.
		selectedKeys.value = new Set(failed.map(requestKey))
		bulkDialog.failed = failed
		if (!failed.length) {
			bulkDialog.open = false
			selecting.value = false
		}
		reloadAll([teamPendingRequests, recentlyApprovedTeamRequests])
	} catch (error) {
		toast({
			title: __("Error"),
			text: error?.messages?.join?.(" ") || error?.message || __("Bulk action failed"),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	} finally {
		bulkDialog.running = false
	}
}

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

.filter-select {
	@apply w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-300;
}

.request-count {
	@apply inline-flex min-w-5 items-center justify-center rounded-full bg-gray-100 px-1.5 py-0.5 text-xs font-semibold text-gray-600;
}
</style>
