<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<FormView
				v-if="formFields.data"
				doctype="Employee Advance"
				v-model="employeeAdvance"
				:isSubmittable="true"
				:fields="formFields.data"
				:id="props.id"
				:showAttachmentView="true"
				@validateForm="validateForm"
			/>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { createResource } from "frappe-ui"
import { ref, watch, inject, computed } from "vue"

import FormView from "@/components/FormView.vue"

import { getCompanyCurrency } from "@/data/currencies"

const employee = inject("$employee")

const props = defineProps({
	id: {
		type: String,
		required: false,
	},
})

// object to store form data
const employeeAdvance = ref({
	employee: employee.data.name,
	employee_name: employee.data.employee_name,
	company: employee.data.company,
	department: employee.data.department,
})

const companyCurrency = computed(() =>
	getCompanyCurrency(employeeAdvance.value.company)
)

// get form fields
const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: "Employee Advance" },
	transform(data) {
		const fields = getFilteredFields(data)
		return applyFilters(fields)
	},
	onSuccess(_) {
		employeeCurrency.reload()
	},
})
formFields.reload()

const employeeCurrency = createResource({
	url: "hrms.payroll.doctype.salary_structure_assignment.salary_structure_assignment.get_employee_currency",
	params: { employee: employee.data.name },
	onSuccess(data) {
		employeeAdvance.value.currency = data
	},
})

// HRMS 16: hrms.api.get_advance_account is gone and nothing replaces it on the
// client. The server fills Advance Account itself -- from the employee's own
// advance account, else the company default when the advance is submitted --
// so the field is left for the user to set only when they need another one.
// The Exchange Rate field is gone too: the paid amount in company currency is
// worked out on the server from the payment (base_paid_amount).

// form scripts
watch(
	() => employeeAdvance.value.currency,
	() => {
		if (formFields.data) applyFilters(formFields.data)
	}
)

// helper functions
function getFilteredFields(fields) {
	// reduce noise from the form view by excluding unnecessary fields
	// eg: employee and other details can be fetched from the session user
	const excludeFields = ["naming_series", "base_paid_amount"]
	const extraFields = [
		"employee",
		"employee_name",
		"department",
		"company",
		"more_info_section",
		"pending_amount",
	]

	if (!props.id) excludeFields.push(...extraFields)

	return fields.filter((field) => !excludeFields.includes(field.fieldname))
}

function applyFilters(fields) {
	return fields.map((field) => {
		if (field.fieldname === "advance_account") {
			let currencies = [employeeAdvance.value.currency]
			if (employeeAdvance.value.currency != companyCurrency.value)
				currencies.push(companyCurrency.value)

			field.linkFilters = {
				company: employeeAdvance.value.company,
				is_group: 0,
				root_type: "Asset",
				account_type: "Receivable",
				account_currency: ["in", currencies],
			}
		}

		return field
	})
}

function validateForm() {}
</script>
