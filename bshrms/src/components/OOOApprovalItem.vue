<template>
	<ListItem @click.stop="openReview">
		<template #left>
			<FeatherIcon name="map-pin" class="h-5 w-5 text-blue-500" />
			<div class="flex flex-col items-start gap-1">
				<div class="text-sm font-bold text-gray-800">{{ props.doc.employee_name }}</div>
				<div class="text-xs text-gray-500">
					<span>{{ formatNepaliDate(props.doc.attendance_date) }}</span>
					<span class="mx-1">&middot;</span>
					<span>{{ formatDaysFromToday(props.doc.attendance_date) }}</span>
					<span class="mx-1">&middot;</span>
					<span>{{ props.doc.working_hours }} hrs</span>
				</div>
			</div>
		</template>
		<template #right>
			<div class="flex items-center gap-2" @click.stop>
				<Button variant="ghost" size="sm" @click="openReview">
					{{ __("Review") }}
				</Button>
				<Button
					v-if="props.doc.can_approve"
					variant="solid"
					size="sm"
					:loading="approving"
					@click="approve"
				>
					{{ __("Approve") }}
				</Button>
				<Button
					v-if="props.doc.can_approve"
					variant="subtle"
					theme="red"
					size="sm"
					@click="showReject = true"
				>
					{{ __("Reject") }}
				</Button>
			</div>
		</template>
	</ListItem>

	<Dialog v-model="showReview">
		<template #body-title>
			<h2 class="text-lg font-bold">{{ __("Review OOO Work") }}</h2>
		</template>
		<template #body-content>
			<div v-if="loadingDetails" class="text-sm text-gray-500 py-4">
				{{ __("Loading check-in details…") }}
			</div>
			<div v-else class="flex flex-col gap-4">
				<div class="text-sm text-gray-600">
					<div class="font-semibold text-gray-800">{{ props.doc.employee_name }}</div>
					<div>{{ formatNepaliDate(props.doc.attendance_date) }}</div>
					<div class="text-xs text-gray-500">
						{{ formatDaysFromToday(props.doc.attendance_date) }}
					</div>
				</div>

				<div
					v-for="checkin in reviewCheckins"
					:key="checkin.name"
					class="rounded-lg border border-gray-200 p-3"
				>
					<label class="block text-sm font-medium text-gray-700 mb-1">
						{{ checkin.log_type === "IN" ? __("OOO Check In") : __("OOO Check Out") }}
					</label>
					<input
						v-model="checkin.edit_time"
						type="datetime-local"
						:step="60"
						:disabled="checkin.is_approved || checkin.is_rejected"
						class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
					/>
					<div v-if="checkin.reason" class="text-xs text-gray-500 mt-1">
						{{ checkin.reason }}
					</div>
					<div
						v-if="checkin.distance_from_shift_location_m != null"
						class="mt-2 rounded-md bg-gray-50 px-3 py-2 text-xs text-gray-700"
					>
						{{ __("Distance from normal check-in location") }}
						<a
							:href="
								mapLink(
									approvalDetails.shift_location.latitude,
									approvalDetails.shift_location.longitude
								)
							"
							target="_blank"
							rel="noopener noreferrer"
							class="font-medium text-blue-700 underline"
						>
							({{ approvalDetails.shift_location.location_name }})
						</a>
						:
						<span class="font-semibold">
							{{ formatDistance(checkin.distance_from_shift_location_m) }}
						</span>
						<span
							v-if="approvalDetails.shift_location.checkin_radius > 0"
							:class="
								checkin.distance_from_shift_location_m <=
								approvalDetails.shift_location.checkin_radius
									? 'text-green-700'
									: 'text-red-700'
							"
						>
							·
							{{
								checkin.distance_from_shift_location_m <=
								approvalDetails.shift_location.checkin_radius
									? __("Within normal check-in radius")
									: __("Outside normal check-in radius")
							}}
						</span>
					</div>
					<iframe
						v-if="checkin.latitude != null && checkin.longitude != null"
						:src="mapUrl(checkin.latitude, checkin.longitude)"
						class="w-full h-40 rounded border mt-3"
						loading="lazy"
						referrerpolicy="no-referrer-when-downgrade"
						:aria-label="__('OOO check-in location')"
					/>
				</div>

				<div v-if="!reviewCheckins.length" class="text-sm text-gray-500">
					{{ __("No OOO check-ins were found.") }}
				</div>

				<div class="rounded-md bg-blue-50 px-3 py-2 text-sm text-blue-800">
					{{ __("Calculated OOO hours") }}:
					<span class="font-semibold">{{ correctedOOOHours }}</span>
				</div>

				<div v-if="approvalDetails?.path_points?.length" class="flex flex-col gap-2">
					<div class="text-sm font-semibold text-gray-800">
						{{ __("Tracked Location Trail") }}
						<span class="font-normal text-gray-500">
							({{ approvalDetails.path_points.length }})
						</span>
					</div>
					<div class="max-h-36 overflow-auto rounded-lg border divide-y">
						<a
							v-for="point in approvalDetails.path_points"
							:key="point.name"
							:href="mapLink(point.latitude, point.longitude)"
							target="_blank"
							rel="noopener noreferrer"
							class="flex justify-between gap-2 px-3 py-2 text-xs text-blue-700"
						>
							<span>{{ formatPointTime(point.timestamp) }}</span>
							<span>
								{{ Number(point.latitude).toFixed(5) }},
								{{ Number(point.longitude).toFixed(5) }}
								<template v-if="point.accuracy">
									(±{{ Math.round(point.accuracy) }}m)
								</template>
							</span>
						</a>
					</div>
				</div>

				<div class="flex flex-col gap-2 border-t pt-4">
					<div class="text-sm font-semibold text-gray-800">
						{{ __("Attendance Comments") }}
					</div>
					<div v-if="comments.length" class="flex flex-col gap-2">
						<div
							v-for="comment in comments"
							:key="comment.name"
							class="rounded-lg bg-gray-50 px-3 py-2"
						>
							<div class="text-xs font-semibold text-gray-700">
								{{ comment.full_name }}
								<span class="font-normal text-gray-400">
									· {{ formatPointTime(comment.creation) }}
								</span>
							</div>
							<div class="comment-content text-sm text-gray-700 mt-1" v-html="comment.content" />
						</div>
					</div>
					<div v-else class="text-xs text-gray-400">
						{{ __("No attendance comments yet.") }}
					</div>
					<template v-if="approvalDetails?.attendance">
						<textarea
							v-model="commentText"
							rows="3"
							class="w-full border border-gray-300 rounded-lg p-2 text-sm"
							:placeholder="__('Add a comment to this Attendance…')"
						/>
						<label class="flex items-center gap-2 text-xs text-gray-600">
							<input v-model="mentionEmployee" type="checkbox" />
							{{ __("Tag {0} in this comment", [props.doc.employee_name]) }}
						</label>
						<Button
							variant="subtle"
							:loading="addingComment"
							:disabled="!commentText.trim()"
							@click="addComment"
						>
							{{ __("Add Comment") }}
						</Button>
					</template>
					<div v-else class="text-xs text-amber-600">
						{{ __("Comments become available after an Attendance record exists.") }}
					</div>
				</div>
			</div>
		</template>
		<template #actions>
			<div class="flex gap-2 w-full">
				<Button class="flex-1" variant="outline" @click="showReview = false">
					{{ __("Close") }}
				</Button>
				<Button
					v-if="props.doc.can_approve"
					class="flex-1"
					variant="subtle"
					:loading="saving"
					:disabled="!editableCheckins.length"
					@click="saveCorrections"
				>
					{{ __("Save Times") }}
				</Button>
				<Button
					v-if="props.doc.can_approve"
					class="flex-1"
					variant="solid"
					:loading="approving"
					:disabled="!editableCheckins.length"
					@click="approve"
				>
					{{ __("Save & Approve") }}
				</Button>
			</div>
		</template>
	</Dialog>

	<Dialog v-model="showReject">
		<template #body-title>
			<h2 class="text-lg font-bold">{{ __("Reject OOO Work") }}</h2>
		</template>
		<template #body-content>
			<p class="text-sm text-gray-600 mb-3">
				{{ __("Reject OOO check-ins for {0} on {1}.", [
					props.doc.employee_name,
					formatNepaliDate(props.doc.attendance_date),
				]) }}
			</p>
			<label class="block text-sm font-medium text-gray-700 mb-1">
				{{ __("Reason") }}
			</label>
			<textarea
				v-model="rejectReason"
				rows="3"
				class="w-full border border-gray-200 rounded-lg p-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
				:placeholder="__('Why is this OOO being rejected?')"
			/>
		</template>
		<template #actions>
			<div class="flex gap-2 w-full">
				<Button class="flex-1" variant="outline" @click="showReject = false">
					{{ __("Cancel") }}
				</Button>
				<Button
					class="flex-1"
					variant="solid"
					theme="red"
					:loading="rejecting"
					:disabled="!rejectReason.trim()"
					@click="reject"
				>
					{{ __("Reject") }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { ref, inject, computed } from "vue"
import { FeatherIcon, createResource, toast, Dialog, Button, call } from "frappe-ui"
import ListItem from "@/components/ListItem.vue"
import { formatNepaliDate, formatDaysFromToday } from "@/utils/nepali_date"
import { pendingOOOApprovals, approvedOOOApprovals } from "@/data/attendance"

const props = defineProps({
	doc: {
		type: Object,
		required: true,
	},
})

const __ = inject("$translate")
const approving = ref(false)
const rejecting = ref(false)
const showReject = ref(false)
const rejectReason = ref("")
const showReview = ref(false)
const loadingDetails = ref(false)
const saving = ref(false)
const approvalDetails = ref(null)
const editableCheckins = ref([])
const reviewCheckins = ref([])
const comments = ref([])
const commentText = ref("")
const mentionEmployee = ref(true)
const addingComment = ref(false)

const approveResource = createResource({
	url: "nepal_hrms.api.ooo_attendance.approve_ooo_checkins",
})

const rejectResource = createResource({
	url: "nepal_hrms.api.ooo_attendance.reject_ooo_checkins",
})

const correctedOOOHours = computed(() => {
	const rows = [...reviewCheckins.value]
		.filter((row) => row.edit_time)
		.sort((a, b) => new Date(a.edit_time) - new Date(b.edit_time))
	let openIn = null
	let milliseconds = 0
	for (const row of rows) {
		const time = new Date(row.edit_time)
		if (row.log_type === "IN") {
			openIn = time
		} else if (row.log_type === "OUT" && openIn && time > openIn) {
			milliseconds += time - openIn
			openIn = null
		}
	}
	return `${(milliseconds / 3600000).toFixed(2)} hrs`
})

const toInputDateTime = (value) =>
	value ? String(value).replace(" ", "T").slice(0, 16) : ""

const mapUrl = (latitude, longitude) =>
	`https://maps.google.com/maps?q=${latitude},${longitude}&hl=en&z=16&output=embed`

const mapLink = (latitude, longitude) =>
	`https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`

const formatDistance = (meters) => {
	const distance = Number(meters)
	if (!Number.isFinite(distance)) return "—"
	return distance < 1000
		? `${Math.round(distance).toLocaleString()} m`
		: `${(distance / 1000).toFixed(2)} km (${Math.round(distance).toLocaleString()} m)`
}

const formatPointTime = (value) =>
	value ? String(value).replace("T", " ").slice(0, 16) : ""

async function openReview() {
	showReview.value = true
	loadingDetails.value = true
	try {
		approvalDetails.value = await call(
			"nepal_hrms.api.ooo_attendance.get_ooo_approval_details",
			{
				employee: props.doc.employee,
				attendance_date: props.doc.attendance_date,
			}
		)
		reviewCheckins.value = (approvalDetails.value?.ooo_checkins || []).map((row) => ({
			...row,
			edit_time: toInputDateTime(row.time),
		}))
		editableCheckins.value = reviewCheckins.value
			.filter((row) => !row.is_approved && !row.is_rejected)
		await loadComments()
	} catch (error) {
		showReview.value = false
		toast({
			title: __("Error"),
			text: error.messages?.join?.(" ") || error.message || __("Could not load OOO details"),
			variant: "error",
		})
	} finally {
		loadingDetails.value = false
	}
}

async function loadComments() {
	comments.value = []
	if (!approvalDetails.value?.attendance) return
	try {
		const response = await call(
			"nepal_hrms.api.ooo_attendance.get_ooo_attendance_comments",
			{
				employee: props.doc.employee,
				attendance_date: props.doc.attendance_date,
			}
		)
		comments.value = response?.comments || []
	} catch (error) {
		console.warn("Could not load Attendance comments", error)
	}
}

async function addComment() {
	if (!commentText.value.trim()) return
	addingComment.value = true
	try {
		await call("nepal_hrms.api.ooo_attendance.add_ooo_attendance_comment", {
			employee: props.doc.employee,
			attendance_date: props.doc.attendance_date,
			content: commentText.value.trim(),
			mention_employee: mentionEmployee.value ? 1 : 0,
		})
		commentText.value = ""
		await loadComments()
		toast({
			title: __("Comment added"),
			text: mentionEmployee.value
				? __("{0} was tagged.", [props.doc.employee_name])
				: __("Attendance comment saved."),
			variant: "success",
		})
	} catch (error) {
		toast({
			title: __("Error"),
			text: error.messages?.join?.(" ") || error.message || __("Could not add comment"),
			variant: "error",
		})
	} finally {
		addingComment.value = false
	}
}

async function saveCorrections({ quiet = false } = {}) {
	if (!editableCheckins.value.length) return
	saving.value = true
	try {
		await call("nepal_hrms.api.ooo_attendance.update_pending_ooo_checkin_times", {
			employee: props.doc.employee,
			attendance_date: props.doc.attendance_date,
			checkins: editableCheckins.value.map((row) => ({
				name: row.name,
				time: row.edit_time ? `${row.edit_time.replace("T", " ")}:00` : null,
			})),
		})
		if (!quiet) {
			toast({
				title: __("Saved"),
				text: __("OOO check-in times updated."),
				variant: "success",
			})
		}
		pendingOOOApprovals.reload()
	} catch (error) {
		toast({
			title: __("Error"),
			text: error.messages?.join?.(" ") || error.message || __("Could not update OOO times"),
			variant: "error",
		})
		throw error
	} finally {
		saving.value = false
	}
}

async function approve() {
	approving.value = true
	try {
		if (showReview.value && editableCheckins.value.length) {
			await saveCorrections({ quiet: true })
		}
		await approveResource.submit({
			employee: props.doc.employee,
			attendance_date: props.doc.attendance_date,
		})

		toast({
			title: __("Success"),
			text: __("OOO attendance approved for {0}", [props.doc.employee_name]),
			variant: "success",
		})

		pendingOOOApprovals.reload()
		approvedOOOApprovals.reload()
		showReview.value = false
	} catch (error) {
		console.error("OOO Approval Error:", error)
		toast({
			title: __("Error"),
			text: error.messages?.join?.(" ") || error.message || __("Failed to approve OOO attendance"),
			variant: "error",
		})
	} finally {
		approving.value = false
	}
}

async function reject() {
	if (!rejectReason.value.trim()) return
	rejecting.value = true
	try {
		await rejectResource.submit({
			employee: props.doc.employee,
			attendance_date: props.doc.attendance_date,
			reason: rejectReason.value.trim(),
		})

		toast({
			title: __("Rejected"),
			text: __("OOO attendance rejected for {0}", [props.doc.employee_name]),
			variant: "success",
		})

		showReject.value = false
		rejectReason.value = ""
		pendingOOOApprovals.reload()
	} catch (error) {
		console.error("OOO Reject Error:", error)
		toast({
			title: __("Error"),
			text: error.messages?.join?.(" ") || error.message || __("Failed to reject OOO attendance"),
			variant: "error",
		})
	} finally {
		rejecting.value = false
	}
}
</script>
