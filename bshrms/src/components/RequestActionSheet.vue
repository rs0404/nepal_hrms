<template>
	<div
		v-if="document?.doc"
		class="bg-white w-full flex flex-col items-center justify-center pb-5 max-h-[calc(100vh-5rem)]"
	>
		<!-- Header -->
		<div
			class="w-full flex flex-row gap-2 pt-8 pb-5 border-b justify-center items-center sticky top-0 z-[100]"
		>
			<span class="text-gray-900 font-bold text-lg text-center">
				{{ __(document?.doctype) }}
			</span>
			<FeatherIcon
				v-if="props.showOpenForm"
				name="external-link"
				class="h-4 w-4 text-gray-500 cursor-pointer"
				@click="openFormView"
			/>
		</div>

		<!-- Request Summary -->
		<div class="w-full p-4 overflow-auto">
			<div class="flex flex-col items-center justify-center gap-5">
				<div
					v-for="field in fieldsWithValues"
					:key="field.fieldname"
					:class="[
						['Small Text', 'Text', 'Long Text', 'Table', 'geolocation'].includes(
							field.fieldtype
						)
							? 'flex-col'
							: ['Date', 'DateRange'].includes(field.fieldtype)
								? 'flex-row items-start justify-between gap-3'
								: 'flex-row items-center justify-between',
						'flex w-full',
					]"
				>
					<div class="text-gray-600 text-base">{{ __(field.label, null, props.modelValue?.doctype) }}</div>
					<component
						v-if="field.fieldtype === 'Table'"
						:is="field.component"
						:doc="document?.doc"
					/>
					<FormattedField
						v-else
						:value="field.value"
						:fieldtype="field.fieldtype"
						:fieldname="field.fieldname"
					/>
				</div>

				<!-- Attachments -->
				<div
					class="flex flex-col gap-2 w-full"
					v-if="attachedFiles?.data?.length"
				>
					<div class="text-gray-600 text-base">{{ __('Attachments') }}</div>
					<ul class="w-full flex flex-col items-center gap-2">
						<li
							class="bg-gray-100 rounded p-2 w-full"
							v-for="(file, index) in attachedFiles.data"
							:key="index"
						>
							<div
								class="flex flex-row items-center justify-between text-gray-700 text-sm"
							>
								<span class="grow" @click="showFilePreview(file)">
									{{ file.file_name || file.name }}
								</span>
							</div>
						</li>
					</ul>
				</div>

				<!-- Related applications (Attendance) -->
				<div
					v-if="relatedApplications?.length"
					class="flex flex-col gap-2 w-full"
				>
					<div class="text-gray-600 text-base">{{ __("Related Applications") }}</div>
					<button
						v-for="app in relatedApplications"
						:key="app.doctype + app.name"
						type="button"
						class="w-full text-left bg-blue-50 border border-blue-100 rounded-lg px-3 py-2"
						@click="openRelatedApplication(app)"
					>
						<div class="text-sm font-medium text-blue-800">
							{{ __(app.doctype) }}
						</div>
						<div class="text-xs text-blue-600 truncate">
							{{ app.name }}
							<span v-if="app.status" class="text-blue-400"> · {{ __(app.status) }}</span>
						</div>
					</button>
				</div>
			</div>
		</div>

		<!-- Actions -->
		<WorkflowActionSheet
			v-if="workflow?.hasWorkflow"
			:doc="document.doc"
			:workflow="workflow"
			view="actionSheet"
		/>

		<div
			v-else-if="showAttendanceRequestApproval"
			class="flex w-full flex-row items-center justify-between gap-3 sticky bottom-0 border-t z-[100] p-4"
		>
			<Button
				@click="showRejectDialog = true"
				class="w-full py-5"
				variant="subtle"
				theme="red"
			>
				<template #prefix>
					<FeatherIcon name="x" class="w-4" />
				</template>
				{{ __("Reject") }}
			</Button>

			<Button
				@click="approveAttendanceRequest"
				class="w-full py-5"
				variant="solid"
				theme="green"
				:loading="approvingAttendanceRequest"
			>
				<template #prefix>
					<FeatherIcon name="check" class="w-4" />
				</template>
				{{ __("Approve") }}
			</Button>
		</div>

		<div
			v-else-if="
				props.modelValue.doctype !== 'Attendance Request' &&
				!canCancelOwnLeave &&
				['Open', 'Draft'].includes(document?.doc?.[approvalField]) &&
				hasPermission('approval')
			"
			class="flex w-full flex-row items-center justify-between gap-3 sticky bottom-0 border-t z-[100] p-4"
		>
			<Button
				@click="updateDocumentStatus({ status: 'Rejected' })"
				class="w-full py-5"
				variant="subtle"
				theme="red"
			>
				<template #prefix>
					<FeatherIcon name="x" class="w-4" />
				</template>
				{{ __("Reject") }}
			</Button>

			<Button
				@click="updateDocumentStatus({ status: 'Approved' })"
				class="w-full py-5"
				variant="solid"
				theme="green"
			>
				<template #prefix>
					<FeatherIcon name="check" class="w-4" />
				</template>
				{{ __("Approve") }}
			</Button>
		</div>

		<div
			v-else-if="canSubmitRequest"
			class="flex w-full flex-row items-center justify-between gap-3 sticky bottom-0 border-t z-[100] p-4"
		>
			<Button
				@click="updateDocumentStatus({ docstatus: 1 })"
				class="w-full py-5"
				variant="solid"
			>
				{{ __("Submit") }}
			</Button>
		</div>

		<div
			v-else-if="document?.doc?.docstatus === 1 && hasPermission('cancel')"
			class="flex w-full flex-row items-center justify-between gap-3 sticky bottom-0 border-t z-[100] p-4"
		>
			<Button
				@click="updateDocumentStatus({ docstatus: 2 })"
				class="w-full py-5"
				variant="subtle"
				theme="red"
			>
				<template #prefix>
					<FeatherIcon name="x" class="w-4" />
				</template>
				{{ __("Cancel") }}
			</Button>
		</div>

		<div
			v-if="canCancelOwnLeave"
			class="flex w-full flex-row items-center justify-between gap-3 sticky bottom-0 border-t z-[100] p-4 bg-white"
		>
			<Button
				@click="showCancelLeaveDialog = true"
				class="w-full py-5"
				variant="subtle"
				theme="red"
			>
				<template #prefix>
					<FeatherIcon name="x" class="w-4" />
				</template>
				{{ __("Cancel Application") }}
			</Button>
		</div>

		<Dialog v-model="showRejectDialog">
			<template #body-title>
				<h2 class="text-lg font-bold">{{ __("Reject Attendance Request") }}</h2>
			</template>
			<template #body-content>
				<p class="text-sm text-gray-600 mb-3">
					{{ __("Provide a reason for rejecting this request.") }}
				</p>
				<label class="block text-sm font-medium text-gray-700 mb-1">
					{{ __("Reason") }}
				</label>
				<textarea
					v-model="rejectReason"
					rows="3"
					class="w-full border border-gray-200 rounded-lg p-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
					:placeholder="__('Why is this attendance request being rejected?')"
				/>
			</template>
			<template #actions>
				<div class="flex gap-2 w-full">
					<Button class="flex-1" variant="outline" @click="showRejectDialog = false">
						{{ __("Cancel") }}
					</Button>
					<Button
						class="flex-1"
						variant="solid"
						theme="red"
						:loading="rejectingAttendanceRequest"
						:disabled="!rejectReason.trim()"
						@click="rejectAttendanceRequest"
					>
						{{ __("Reject") }}
					</Button>
				</div>
			</template>
		</Dialog>

		<Dialog v-model="showCancelLeaveDialog">
			<template #body-title>
				<h2 class="text-lg font-bold">{{ __("Cancel Leave Application") }}</h2>
			</template>
			<template #body-content>
				<p class="text-sm text-gray-600">
					{{
						__(
							"This will withdraw the application so you can submit a corrected one. This cannot be undone."
						)
					}}
				</p>
			</template>
			<template #actions>
				<div class="flex gap-2 w-full">
					<Button class="flex-1" variant="outline" @click="showCancelLeaveDialog = false">
						{{ __("Keep") }}
					</Button>
					<Button
						class="flex-1"
						variant="solid"
						theme="red"
						:loading="cancellingOwnLeave"
						@click="cancelOwnLeaveApplication"
					>
						{{ __("Cancel Application") }}
					</Button>
				</div>
			</template>
		</Dialog>

		<!-- File Preview Modal -->
		<ion-modal
			ref="modal"
			:is-open="showPreviewModal"
			@didDismiss="showPreviewModal = false"
		>
			<FilePreviewModal :file="selectedFile" />
		</ion-modal>
	</div>
</template>

<script setup>
import { computed, inject, ref, defineAsyncComponent, onMounted, watch } from "vue"
import { IonModal, modalController } from "@ionic/vue"
import { useRouter } from "vue-router"
import {
	toast,
	createDocumentResource,
	createResource,
	FeatherIcon,
	Dialog,
	Button,
	call,
} from "frappe-ui"

import FormattedField from "@/components/FormattedField.vue"
import FilePreviewModal from "@/components/FilePreviewModal.vue"
import WorkflowActionSheet from "@/components/WorkflowActionSheet.vue"

import { getCompanyCurrency } from "@/data/currencies"
import { formatCurrency } from "@/utils/formatters"

import useWorkflow from "@/composables/workflow"
import { myLeaves, leaveBalance } from "@/data/leaves"

const __ = inject("$translate")
const employee = inject("$employee")

const props = defineProps({
	fields: {
		type: Array,
		required: true,
	},
	showOpenForm: {
		type: Boolean,
		default: true,
	},
	modelValue: {
		type: Object,
		required: true,
	},
})
const router = useRouter()

const relatedApplications = ref([])

let showPreviewModal = ref(false)
let selectedFile = ref({})
let workflow = ref(null)
const showRejectDialog = ref(false)
const rejectReason = ref("")
const showCancelLeaveDialog = ref(false)
const cancellingOwnLeave = ref(false)
const approvingAttendanceRequest = ref(false)
const rejectingAttendanceRequest = ref(false)

function showFilePreview(fileObj) {
	selectedFile.value = fileObj
	showPreviewModal.value = true
}

const document = createDocumentResource({
	doctype: props.modelValue.doctype,
	name: props.modelValue.name,
	auto: true,
	onSuccess(doc) {
		attachedFiles.reload()
		loadRelatedApplications()
	},
})

async function loadRelatedApplications() {
	relatedApplications.value = []
	if (props.modelValue?.doctype !== "Attendance") return
	try {
		const data = await call("nepal_hrms.api.attendance_calendar.get_attendance_related_applications", {
			attendance: props.modelValue.name,
			employee: props.modelValue.employee || document.doc?.employee,
			attendance_date:
				props.modelValue.attendance_date || document.doc?.attendance_date,
		})
		relatedApplications.value = data?.links || []
	} catch (e) {
		console.warn("related applications load failed", e)
	}
}

function openRelatedApplication(app) {
	const routeName =
		app.route_name || `${String(app.doctype).replace(/\s+/g, "")}DetailView`
	modalController.dismiss()
	router.push({ name: routeName, params: { id: app.name } })
}

const attachedFiles = createResource({
	url: "hrms.api.get_attachments",
	params: {
		dt: props.modelValue.doctype,
		dn: props.modelValue.name,
	},
})

const docPermissions = createResource({
	url: "frappe.client.get_doc_permissions",
	params: { doctype: props.modelValue.doctype, docname: props.modelValue.name },
	auto: true,
})

const permittedWriteFields = createResource({
	url: "hrms.api.get_permitted_fields_for_write",
	params: { doctype: props.modelValue.doctype },
	auto: true,
})

const CNR_DOCTYPES = [
	"Late Entry Application",
	"Early Exit Application",
	"Out of Office Application",
]

const canApproveCnr = createResource({
	url: "nepal_hrms.api.cnr_applications.can_approve_cnr_application",
	makeParams: () => ({
		employee: document.doc?.employee || props.modelValue.employee,
	}),
})

const canApproveAttendanceRequest = createResource({
	url: "nepal_hrms.overrides.attendance_request.can_approve_attendance_request",
	makeParams: () => ({
		employee: document.doc?.employee || props.modelValue.employee,
		name: props.modelValue.name,
	}),
})

watch(
	() => document.doc?.employee || props.modelValue.employee,
	(employee) => {
		if (employee && CNR_DOCTYPES.includes(props.modelValue.doctype)) {
			canApproveCnr.reload()
		}
		if (employee && props.modelValue.doctype === "Attendance Request") {
			canApproveAttendanceRequest.reload()
		}
	},
	{ immediate: true }
)

const canCancelOwnLeave = computed(() => {
	if (props.modelValue.doctype !== "Leave Application") return false
	if (document?.doc?.docstatus !== 0) return false
	const status = document?.doc?.status || "Open"
	if (status !== "Open") return false
	const leaveEmployee = document?.doc?.employee || props.modelValue.employee
	return !!leaveEmployee && leaveEmployee === employee?.data?.name
})

async function cancelOwnLeaveApplication() {
	cancellingOwnLeave.value = true
	try {
		await call("nepal_hrms.api.leave_application.cancel_own_leave_application", {
			name: props.modelValue.name,
		})
		showCancelLeaveDialog.value = false
		myLeaves.reload()
		leaveBalance.reload()
		toast({
			title: __("Success"),
			text: __("Leave application cancelled. You can submit a new one."),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
		modalController.dismiss()
	} catch (error) {
		toast({
			title: __("Error"),
			text:
				error.messages?.join?.(" ") ||
				error.message ||
				__("Could not cancel the leave application"),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	} finally {
		cancellingOwnLeave.value = false
	}
}

const showAttendanceRequestApproval = computed(() => {
	if (props.modelValue.doctype !== "Attendance Request") return false
	if (document?.doc?.docstatus !== 0) return false
	const status = document?.doc?.status || "Open"
	if (status !== "Open") return false
	return !!canApproveAttendanceRequest.data
})

const canSubmitRequest = computed(() => {
	if (document?.doc?.docstatus !== 0 || !hasPermission("submit")) return false
	if (props.modelValue.doctype === "Attendance Request") {
		const status = document?.doc?.status || "Open"
		return ["Open", "Approved"].includes(status)
	}
	return ["Approved", "Rejected"].includes(document?.doc?.[approvalField.value])
})

function hasPermission(action) {
	const isCnr = CNR_DOCTYPES.includes(props.modelValue.doctype)
	if (action === "approval") {
		const canWriteStatus = permittedWriteFields.data?.includes(approvalField.value)
		if (isCnr) return !!canApproveCnr.data && canWriteStatus
		return canWriteStatus
	}
	const allowed = docPermissions.data?.permissions[action]
	if (isCnr && (action === "submit" || action === "cancel")) {
		return !!canApproveCnr.data && allowed
	}
	return allowed
}

async function approveAttendanceRequest() {
	approvingAttendanceRequest.value = true
	try {
		await call(
			"nepal_hrms.overrides.attendance_request.set_attendance_request_approval",
			{
				name: props.modelValue.name,
				status: "Approved",
			}
		)
		await document.reload()
		toast({
			title: __("Success"),
			text: __("Approved successfully!"),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
	} catch (error) {
		toast({
			title: __("Error"),
			text:
				error.messages?.join?.(" ") ||
				error.message ||
				__("Approval failed!"),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	} finally {
		approvingAttendanceRequest.value = false
	}
}

async function rejectAttendanceRequest() {
	if (!rejectReason.value.trim()) return
	rejectingAttendanceRequest.value = true
	try {
		await call(
			"nepal_hrms.overrides.attendance_request.set_attendance_request_approval",
			{
				name: props.modelValue.name,
				status: "Rejected",
				rejection_reason: rejectReason.value.trim(),
			}
		)
		showRejectDialog.value = false
		rejectReason.value = ""
		await document.reload()
		toast({
			title: __("Success"),
			text: __("Rejected successfully!"),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
		modalController.dismiss()
	} catch (error) {
		toast({
			title: __("Error"),
			text:
				error.messages?.join?.(" ") ||
				error.message ||
				__("Rejection failed!"),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	} finally {
		rejectingAttendanceRequest.value = false
	}
}

const currency = computed(() => {
	let docCurrency = document?.doc?.currency

	if (!docCurrency && document?.doc?.company) {
		docCurrency = getCompanyCurrency(document?.doc?.company)
	}
	return docCurrency
})

const fieldsWithValues = computed(() => {
	return props.fields.filter((field) => {
		if (
			field.fieldname === "custom_rejection_reason" &&
			document?.doc?.status !== "Rejected"
		) {
			return false
		}

		const doc = { ...(props.modelValue || {}), ...(document?.doc || {}) }

		if (field.fieldtype === "Currency") {
			field.value = formatCurrency(doc[field.fieldname], currency.value)
		} else if (field.fieldtype === "Table") {
			// dynamically loading child table component as per config
			// does not work with @ alias due to vite's import analysis
			field.component = defineAsyncComponent(() =>
				import(`../components/${field.componentName}.vue`)
			)
			field.value = doc[field.fieldname]
		} else if (field.fieldtype === "DateRange") {
			field.value = {
				from: doc[field.fromField] || "",
				to: doc[field.toField] || "",
			}
		} else {
			field.value = doc[field.fieldname]
			if (
				field.fieldname === "status" &&
				field.value === "Draft" &&
				CNR_DOCTYPES.includes(props.modelValue.doctype)
			) {
				field.value = "Waiting for Approval"
			}
		}

		if (field.fieldtype === "DateRange") {
			return !!(field.value?.from || field.value?.to)
		}
		return field.value
	})
})

const approvalField = computed(() => {
	return props.modelValue.doctype === "Expense Claim"
		? "approval_status"
		: "status"
})

const getSuccessMessage = ({ status = "", docstatus = 0 }) => {
	if (status) {
		return __("{0} successfully!", [__(status)])
	} else if (docstatus) {
		return __("Document {0} successfully!", [
			docstatus === 1 ? __("submitted") : __("cancelled")]
		)
	}
}

const getFailureMessage = ({ status = "", docstatus = 0 }) => {
	if (status) {
		return __("{0} failed!", [status === __("Approved") ? __("Approval") : __("Rejection")])
	} else if (docstatus) {
		return __('Document {0} failed!', [docstatus === 1 ? __("submission") : __("cancellation")])
	}
}

const updateDocumentStatus = ({ status = "", docstatus = 0 }) => {
	let updateValues = {}

	if (status) updateValues[approvalField.value] = status
	if (docstatus) updateValues.docstatus = docstatus

	document.setValue.submit(
		{ ...updateValues },
		{
			onSuccess() {
				if (docstatus !== 0) modalController.dismiss()

				toast({
					title: __("Success"),
					text: getSuccessMessage({ status, docstatus }),
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
			},
			onError() {
				toast({
					title: __("Error"),
					text: getFailureMessage({ status, docstatus }),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
			},
		}
	)
}

const openFormView = () => {
	modalController.dismiss()
	router.push({
		name: `${props.modelValue.doctype.replace(/\s+/g, "")}DetailView`,
		params: { id: props.modelValue.name },
	})
}

onMounted(() => {
	workflow.value = useWorkflow(props.modelValue.doctype)
})
</script>

<style scoped>
ion-modal {
	--height: 100%;
}
</style>
