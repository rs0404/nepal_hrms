<template>
	<ListItem>
		<template #left>
			<FeatherIcon name="map-pin" class="h-5 w-5 text-blue-500" />
			<div class="flex flex-col items-start gap-1">
				<div class="text-sm font-bold text-gray-800">{{ props.doc.employee_name }}</div>
				<div class="text-xs text-gray-500">
					<span>{{ formatNepaliDate(props.doc.attendance_date) }}</span>
					<span class="mx-1">&middot;</span>
					<span>{{ props.doc.working_hours }} hrs</span>
				</div>
			</div>
		</template>
		<template #right>
			<div class="flex items-center gap-2" @click.stop>
				<Button variant="solid" size="sm" :loading="approving" @click="approve">
					{{ __("Approve") }}
				</Button>
				<Button variant="subtle" theme="red" size="sm" @click="showReject = true">
					{{ __("Reject") }}
				</Button>
			</div>
		</template>
	</ListItem>

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
import { ref, inject } from "vue"
import { FeatherIcon, createResource, toast, Dialog, Button } from "frappe-ui"
import ListItem from "@/components/ListItem.vue"
import { formatNepaliDate } from "@/utils/nepali_date"
import { pendingOOOApprovals } from "@/data/attendance"

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

const approveResource = createResource({
	url: "nepal_hrms.api.ooo_attendance.approve_ooo_checkins",
})

const rejectResource = createResource({
	url: "nepal_hrms.api.ooo_attendance.reject_ooo_checkins",
})

async function approve() {
	approving.value = true
	try {
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
