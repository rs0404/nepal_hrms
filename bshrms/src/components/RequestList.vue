<template>
	<div class="flex flex-col bg-white mt-2 overflow-auto" v-if="props.items?.length">
		<div
			class="flex flex-row px-1 py-3.5 items-center justify-between border-b border-gray-100 last:border-b-0 cursor-pointer active:bg-gray-50"
			v-for="link in props.items"
			:key="link.doctype + link.name"
			@click="onRowClick(link)"
		>
			<div
				v-if="props.selecting"
				class="mr-3 flex h-5 w-5 shrink-0 items-center justify-center rounded border"
				:class="
					!isSelectable(link)
						? 'border-gray-200 bg-gray-50'
						: isSelected(link)
							? 'border-gray-900 bg-gray-900'
							: 'border-gray-400 bg-white'
				"
			>
				<FeatherIcon v-if="isSelected(link)" name="check" class="h-3.5 w-3.5 text-white" />
			</div>
			<component
				:is="props.component || link.component"
				:doc="link"
				:workflowStateField="link.workflow_state_field"
				:isTeamRequest="props.teamRequests"
			/>
		</div>

		<router-link
			v-if="props.addListButton"
			:to="{ name: props.listButtonRoute }"
			v-slot="{ navigate }"
		>
			<Button
				variant="ghost"
				@click="navigate"
				class="w-full !text-gray-600 py-6 text-sm border-none bg-white hover:bg-white"
			>
				{{ __("View List") }}
			</Button>
		</router-link>
	</div>
	<EmptyState :message="emptyStateMessage || __('You have no requests')" v-else />

	<ion-modal
		ref="modal"
		:is-open="isRequestModalOpen"
		@didDismiss="closeRequestModal"
		:initial-breakpoint="1"
		:breakpoints="[0, 1]"
	>
		<RequestActionSheet :fields="fieldsMap[selectedRequest?.doctype]" v-model="selectedRequest" />
	</ion-modal>
</template>

<script setup>
import { ref, inject } from "vue"
import { IonModal } from "@ionic/vue"
import { FeatherIcon } from "frappe-ui"
import RequestActionSheet from "@/components/RequestActionSheet.vue"

import {
	LEAVE_FIELDS,
	EXPENSE_CLAIM_FIELDS,
	ATTENDANCE_REQUEST_FIELDS,
	SHIFT_REQUEST_FIELDS,
	SHIFT_FIELDS,
	CNR_APPLICATION_FIELDS,
} from "@/data/config/requestSummaryFields"

const __ = inject("$translate")
const props = defineProps({
	component: {
		type: Object,
	},
	items: {
		type: Array,
	},
	teamRequests: {
		type: Boolean,
		default: false,
	},
	addListButton: {
		type: Boolean,
		default: false,
	},
	listButtonRoute: {
		type: String,
		default: "",
	},
	emptyStateMessage: {
		type: String,
		default: "",
	},
	// Bulk selection: while selecting, a tap toggles a selectable row instead
	// of opening it. Rows that cannot be selected still open.
	selecting: {
		type: Boolean,
		default: false,
	},
	selectable: {
		type: Function,
		default: () => false,
	},
	selectedKeys: {
		type: Set,
		default: () => new Set(),
	},
})
const emit = defineEmits(["toggle"])

function isSelectable(request) {
	return props.selecting && props.selectable(request)
}

function isSelected(request) {
	return props.selectedKeys.has(`${request.doctype}::${request.name}`)
}

function onRowClick(request) {
	if (isSelectable(request)) emit("toggle", request)
	else openRequestModal(request)
}

const fieldsMap = {
	"Leave Application": LEAVE_FIELDS,
	"Expense Claim": EXPENSE_CLAIM_FIELDS,
	"Attendance Request": ATTENDANCE_REQUEST_FIELDS,
	"Shift Request": SHIFT_REQUEST_FIELDS,
	"Shift Assignment": SHIFT_FIELDS,
	"Late Entry Application": CNR_APPLICATION_FIELDS,
	"Early Exit Application": CNR_APPLICATION_FIELDS,
	"Out of Office Application": CNR_APPLICATION_FIELDS,
}

const isRequestModalOpen = ref(false)
const selectedRequest = ref(null)

const openRequestModal = async (request) => {
	selectedRequest.value = request
	isRequestModalOpen.value = true
}

const closeRequestModal = async () => {
	isRequestModalOpen.value = false
	selectedRequest.value = null
}
</script>
