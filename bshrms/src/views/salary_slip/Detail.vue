<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<!-- Nothing about the slip is fetched or drawn until it is unlocked. -->
			<div v-if="salaryLocked" class="flex flex-col gap-4 p-4 pt-8">
				<SalaryUnlock :title="__('This salary slip is locked')" />
			</div>
			<FormView
				v-else-if="formFields.data"
				doctype="Salary Slip"
				v-model="salarySlip"
				:fields="formFields.data"
				:id="props.id"
				:tabbedView="true"
				:tabs="tabs"
				:showFormButton="false"
			>
				<!-- The payslip itself, the way people recognise it. Rendered into an
				     iframe because a print format is a whole HTML document with its
				     own styles, which would otherwise bleed into the app. -->
				<template #printPreview>
					<div class="flex h-full flex-col">
						<div v-if="printHTML.loading" class="p-4 text-base text-gray-600">
							{{ __("Loading salary slip…") }}
						</div>
						<ErrorMessage
							v-else-if="printHTML.error"
							class="p-4"
							:message="__('Could not load the salary slip')"
						/>
						<iframe
							v-else-if="printHTML.data?.html"
							class="w-full grow border-0 bg-white"
							:srcdoc="printHTML.data.html"
							:title="__('Salary Slip')"
							sandbox="allow-same-origin"
						/>
					</div>
				</template>

				<!-- Child Tables -->
				<template #earnings="{ isFormReadOnly }">
					<SalaryDetailTable
						type="Earnings"
						:salarySlip="salarySlip"
						:isReadOnly="isFormReadOnly"
					/>
				</template>

				<template #deductions="{ isFormReadOnly }">
					<SalaryDetailTable
						type="Deductions"
						:salarySlip="salarySlip"
						:isReadOnly="isFormReadOnly"
					/>
				</template>

			</FormView>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { ref, watch } from "vue"
import { IonPage, IonContent } from "@ionic/vue"

import { createResource, ErrorMessage } from "frappe-ui"

import FormView from "@/components/FormView.vue"
import SalaryDetailTable from "@/components/SalaryDetailTable.vue"
import SalaryUnlock from "@/components/SalaryUnlock.vue"
import { salaryLocked } from "@/data/salary_lock"

import { getCompanyCurrency } from "@/data/currencies"

const props = defineProps({
	id: {
		type: String,
		required: true,
	},
})


// reactive object to store form data
const salarySlip = ref({})

// get form fields
const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: "Salary Slip" },
	transform(data) {
		return getFilteredFields(data)
	},
})
formFields.reload()

const printHTML = createResource({
	url: "nepal_hrms.api.salary_slip_print.get_salary_slip_html",
	params: { name: props.id },
})

watch(
	salaryLocked,
	(locked) => {
		if (locked) {
			// Dropping the rendered slip too, so it is not kept behind the lock screen.
			printHTML.reset()
		} else if (!printHTML.data && !printHTML.loading) {
			printHTML.fetch()
		}
	},
	{ immediate: true }
)

const tabs = [
	// First, because it is what the employee came to see. The field tabs stay
	// behind it for anyone checking how a figure was reached.
	{ name: "Salary Slip", slot: "printPreview" },
	{ name: "Details", lastField: "payment_days" },
	{ name: "Earnings & Deductions", lastField: "base_total_deduction" },
	{ name: "Net Pay Info", lastField: "base_total_in_words" },
	{ name: "Income Tax Breakup", lastField: "total_income_tax" },
	{ name: "Bank Details", lastField: "bank_account_no" },
]

watch(
	() => salarySlip.value.company,
	async (company) => {
		if (!company) return

		const companyCurrency = await getCompanyCurrency(company)

		formFields.data?.map((field) => {
			if (field.label?.includes("Company Currency")) {
				if (salarySlip.value.currency === companyCurrency) {
					// hide base currency fields
					field.hidden = true
				} else {
					// set currency in label
					field.label = field.label.replace("Company Currency", companyCurrency)
				}
			}
		})
	},
	{ immediate: true }
)

function getFilteredFields(fields) {
	const hasTimesheets = salarySlip.value?.timesheets?.length
	if (hasTimesheets) return fields

	const excludeFields = [
		"timesheets_section",
		"timesheets",
		"total_working_hours",
		"hour_rate",
		"base_hour_rate",
		"help_section",
		"earning_deduction_sb",
	]
	return fields.filter((field) => !excludeFields.includes(field.fieldname))
}
</script>
