<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<FormView
				v-if="formFields.data"
				doctype="Compensatory Leave Request"
				v-model="request"
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
import { createResource, createListResource } from "frappe-ui"
import { ref, watch, inject } from "vue"
import { useRoute } from "vue-router"

import FormView from "@/components/FormView.vue"

const employee = inject("$employee")
const route = useRoute()

const props = defineProps({
	id: { type: String, required: false },
})

// Opened from a worked holiday on the calendar: the day and the half-day flag
// come from the day sheet (it offers this only where Frappe HR will accept it).
const prefill = !props.id && route.query?.prefill === "1" ? route.query : {}
const day = prefill.from_date ? String(prefill.from_date) : ""
const halfDay = prefill.half_day === "1"

const request = ref(
	props.id
		? {}
		: {
				employee: employee.data?.name,
				employee_name: employee.data?.employee_name,
				department: employee.data?.department,
				...(day ? { work_from_date: day, work_end_date: day } : {}),
				...(halfDay ? { half_day: 1, half_day_date: day } : {}),
			}
)

const HIDDEN_ON_CREATE = ["employee", "employee_name", "department", "leave_allocation", "amended_from"]

const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: "Compensatory Leave Request" },
	auto: true,
	transform(data) {
		return data
			.filter((field) => props.id || !HIDDEN_ON_CREATE.includes(field.fieldname))
			.map((field) =>
				// Only a compensatory leave type can be claimed for a worked holiday.
				field.fieldname === "leave_type"
					? { ...field, linkFilters: { is_compensatory: 1 }, reqd: 1 }
					: field
			)
	},
})

// With a single compensatory leave type, there is nothing to choose.
createListResource({
	doctype: "Leave Type",
	fields: ["name"],
	filters: { is_compensatory: 1 },
	auto: !props.id,
	onSuccess(data) {
		if (!request.value.leave_type && data?.length === 1) {
			request.value.leave_type = data[0].name
		}
	},
})

watch(
	() => request.value.employee,
	(employeeId) => {
		if (props.id && employeeId && employeeId !== employee.data.name) {
			formFields.data?.forEach((field) => (field.read_only = true))
		}
	}
)

function validateForm() {
	request.value.employee = employee.data.name
}
</script>
