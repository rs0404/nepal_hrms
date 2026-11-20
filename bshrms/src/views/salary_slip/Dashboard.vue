<template>
	<BaseLayout :pageTitle="__('Salary Slips')">
		<template #body>
			<div class="flex flex-col items-center my-7 p-4">
				<SalaryUnlock v-if="salaryLocked" class="mb-4" />
				<button
					v-else-if="salaryPrivacy.data?.enabled"
					type="button"
					class="mb-3 flex items-center gap-1.5 self-end text-xs font-semibold text-gray-500"
					@click="lockSalary"
				>
					<FeatherIcon name="lock" class="h-3.5 w-3.5" />
					{{ __("Hide amounts") }}
				</button>
				<div class="flex flex-col w-full bg-white rounded py-5 px-3.5 gap-5">
					<div v-if="lastSalarySlip && lastSalarySlip.year_to_date" class="flex flex-col w-full gap-1.5">
						<span class="text-gray-600 text-sm font-medium leading-5">
							{{ __("Year To Date") }}
						</span>
						<span class="text-gray-800 text-xl font-bold leading-6">
							{{
								maskedAmount(
									formatCurrency(lastSalarySlip.year_to_date, lastSalarySlip.currency)
								)
							}}
						</span>
					</div>

					<div
						v-if="periodsUnavailable"
						class="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800"
					>
						{{ __("Payroll periods are not available to you, so all your salary slips are shown.") }}
					</div>
					<Autocomplete
						v-else
						:label="__('Payroll Period')"
						class="w-full"
						:placeholder="__('Select Payroll Period')"
						v-model="selectedPeriod"
						:options="payrollPeriods.data"
					/>
				</div>

				<div class="flex flex-col items-center mt-5 mb-7 w-full">
					<div
						v-if="documents.data?.length"
						class="flex flex-col bg-white rounded mt-5 overflow-auto w-full"
					>
						<div
							class="p-3.5 items-center justify-between border-b cursor-pointer"
							v-for="link in documents.data"
							:key="link.name"
						>
							<router-link
								:to="{
									name: 'SalarySlipDetailView',
									params: { id: link.name },
								}"
								v-slot="{ navigate }"
							>
								<SalarySlipItem :doc="link" @click="navigate" />
							</router-link>
						</div>
					</div>
					<EmptyState :message="__('No salary slips found')" v-else />
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { inject, ref, computed, watch, onMounted, onBeforeUnmount } from "vue"
import { Autocomplete, FeatherIcon, createListResource, createResource } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import EmptyState from "@/components/EmptyState.vue"
import SalarySlipItem from "@/components/SalarySlipItem.vue"
import SalaryUnlock from "@/components/SalaryUnlock.vue"
import { lockSalary, maskedAmount, salaryLocked, salaryPrivacy } from "@/data/salary_lock"

import { formatCurrency } from "@/utils/formatters"
import { formatNepaliMonthPeriodNe, formatNepaliMonthYearPeriod } from "@/utils/nepali_date"

let selectedPeriod = ref({})
let periodsByName = ref({})

const employee = inject("$employee")
const dayjs = inject("$dayjs")
const socket = inject("$socket")
const __ = inject("$translate")

// From the server, not the doctype: an Employee often has only "select" on
// Payroll Period, which returns names without the dates the filter needs.
const payrollPeriods = createResource({
	url: "nepal_hrms.api.payroll_periods.get_my_payroll_periods",
	auto: true,
	transform(data) {
		return data.map((period) => {
			periodsByName.value[period.name] = period
			return {
				label: getPeriodLabel(period),
				value: period.name,
			}
		})
	},
	// onSuccess gets the raw rows, not the transformed options, so build the
	// option here. Default to the period containing today, else the latest.
	onSuccess: (data) => {
		if (!data?.length) return showAllSlips()
		const today = dayjs().format("YYYY-MM-DD")
		const current =
			data.find((period) => period.start_date <= today && today <= period.end_date) ||
			data[0]
		selectedPeriod.value = { label: getPeriodLabel(current), value: current.name }
	},
	// No read access to Payroll Period: the slips are still the employee's own.
	onError: () => {
		periodsUnavailable.value = true
		showAllSlips()
	},
})

const periodsUnavailable = ref(false)

function showAllSlips() {
	delete documents.filters.start_date
	documents.reload()
}

const documents = createListResource({
	doctype: "Salary Slip",
	fields: [
		"name",
		"start_date",
		"end_date",
		"currency",
		"gross_pay",
		"net_pay",
		"year_to_date",
	],
	filters: {
		employee: employee.data?.name,
		docstatus: 1,
	},
	orderBy: "end_date desc",
})

const lastSalarySlip = computed(() => documents.data?.[0])

function getPeriodLabel(period) {
	const ad = `${dayjs(period?.start_date).format("MMM YYYY")} – ${dayjs(
		period?.end_date
	).format("MMM YYYY")}`
	const bs =
		formatNepaliMonthPeriodNe(period?.start_date, period?.end_date) ||
		formatNepaliMonthYearPeriod(period?.start_date, period?.end_date)
	return bs ? `${bs} · ${ad}` : ad
}

watch(
	() => selectedPeriod.value,
	(value) => {
		let period = periodsByName.value[value?.value]
		documents.filters.start_date = [
			"between",
			[period?.start_date, period?.end_date],
		]
		documents.reload()
	}
)

onMounted(() => {
	socket.on("hrms:update_salary_slips", (data) => {
		if (data.employee === employee.data.name) {
			documents.reload()
		}
	})
})

onBeforeUnmount(() => {
	socket.off("hrms:update_salary_slips")
})
</script>
