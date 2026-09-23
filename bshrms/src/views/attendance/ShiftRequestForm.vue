<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<FormView
				v-if="formFields.data"
				doctype="Shift Request"
				v-model="shiftRequest"
				:isSubmittable="true"
				:fields="formFields.data"
				:id="props.id"
				@validateForm="validateForm"
			/>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { createResource } from "frappe-ui"
import { ref, watch, inject } from "vue"
import { useRoute } from "vue-router"

import FormView from "@/components/FormView.vue"

const employee = inject("$employee")
const __ = inject("$translate")
const route = useRoute()

const props = defineProps({
	id: {
		type: String,
		required: false,
	},
})

// reactive object to store form data. Opened from a calendar day, the day,
// employee and company are already known.
const prefill = !props.id && route.query?.prefill === "1" ? route.query : {}
const shiftRequest = ref({
	...(props.id
		? {}
		: {
				employee: employee.data?.name,
				employee_name: employee.data?.employee_name,
				company: employee.data?.company,
				status: "Draft",
			}),
	...(prefill.from_date ? { from_date: String(prefill.from_date) } : {}),
	...(prefill.to_date ? { to_date: String(prefill.to_date) } : {}),
})

// get form fields
const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: "Shift Request" },
	auto: true,
	transform(data) {
		if (props.id) return data
		return data
			.filter(
				(field) => !["employee", "employee_name", "status", "company"].includes(field.fieldname)
			)
			.map((field) =>
				// The approver is whoever HR set for this employee (or the department's
				// first shift approver). It is not the employee's choice.
				field.fieldname === "approver" ? { ...field, read_only: 1 } : field
			)
	},
})

createResource({
	url: "hrms.api.get_shift_request_approvers",
	params: { employee: employee.data.name },
	auto: !props.id,
	onSuccess(data) {
		// hrms lists the employee's own approver first, then the department's.
		const approver = data?.[0]
		shiftRequest.value.approver = approver?.name || ""
		const field = formFields.data?.find((f) => f.fieldname === "approver")
		if (field) {
			field.documentList = approver
				? [{ label: approver.full_name || approver.name, value: approver.name }]
				: []
			field.error_message = approver
				? ""
				: __("No shift approver is set for you. Ask HR to set one.")
		}
	},
})

// form scripts
watch(
	() => shiftRequest.value.employee,
	(employee_id) => {
		if (props.id && employee_id !== employee.data.name) {
			// if employee is not the current user, set form as read only
			setFormReadOnly()
		}
	}
)

watch(
	() => [shiftRequest.value.from_date, shiftRequest.value.to_date],
	([from_date, to_date]) => {
		validateDates(from_date, to_date)
	}
)

// helper functions
function setFormReadOnly() {
	if (shiftRequest.value.approver === employee.data.user_id) return
	formFields.data.map((field) => (field.read_only = true))
}

function validateDates(from_date, to_date) {
	if (!(from_date && to_date)) return

	const error_message = from_date > to_date ? __("To Date cannot be before From Date") : ""

	const from_date_field = formFields.data.find((field) => field.fieldname === "from_date")
	from_date_field.error_message = error_message
}

function validateForm() {
	shiftRequest.value.employee = employee.data.name
}
</script>
