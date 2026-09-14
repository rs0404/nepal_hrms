<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<div
				v-if="deadlineWarning"
				class="mx-4 mt-4 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg"
			>
				{{ deadlineWarning }}
			</div>
			<FormView
				v-if="formFields.data"
				:doctype="doctype"
				v-model="application"
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
import { createResource, call } from "frappe-ui"
import { ref, watch, inject, computed, onMounted } from "vue"
import { useRoute } from "vue-router"

import FormView from "@/components/FormView.vue"
import { timeFromDatetime } from "@/utils/nepali_date"

const employee = inject("$employee")
const dayjs = inject("$dayjs")
const __ = inject("$translate")
const route = useRoute()
const deadlineWarning = ref("")
const prefillMode = ref(false)

const props = defineProps({
	id: { type: String, required: false },
	doctype: { type: String, required: false },
})

const doctype = computed(() => {
	if (props.doctype) return props.doctype
	const name = route.name || ""
	if (name.startsWith("LateEntryApplication")) return "Late Entry Application"
	if (name.startsWith("EarlyExitApplication")) return "Early Exit Application"
	if (name.startsWith("OutOfOfficeApplication")) return "Out of Office Application"
	return "Late Entry Application"
})

const application = ref({
	employee: employee.data?.name,
	employee_name: employee.data?.employee_name,
	company: employee.data?.company,
	department: employee.data?.department,
	status: "Draft",
	posting_date: dayjs().format("YYYY-MM-DD"),
})

const HIDDEN_ON_CREATE = [
	"employee",
	"employee_name",
	"status",
	"company",
	"attendance",
	"naming_series",
	"department",
	"amended_from",
	"custom_rejection_reason",
	"late_entry_time",
	"from_time",
	"to_time",
	"total_hours",
]

const PREFILL_READONLY = ["posting_date", "attendance_date"]

const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	makeParams: () => ({ doctype: doctype.value }),
	auto: true,
	transform(data) {
		let fields = data.filter((field) => {
			if (field.fieldname === "status") return false
			if (!props.id && HIDDEN_ON_CREATE.includes(field.fieldname)) return false
			return true
		})
		if (prefillMode.value) {
			fields = fields.map((field) => {
				if (PREFILL_READONLY.includes(field.fieldname)) {
					return { ...field, read_only: 1 }
				}
				return field
			})
		}
		return fields
	},
})

watch(doctype, () => formFields.reload())

watch(
	() => application.value.employee,
	(employee_id) => {
		if (props.id && employee_id && employee_id !== employee.data.name) {
			formFields.data?.forEach((field) => (field.read_only = true))
		}
	}
)

async function applyPrefillFromQuery() {
	if (props.id) return
	const q = route.query || {}
	if (q.prefill !== "1" || !q.attendance_date) return

	prefillMode.value = true
	application.value = {
		...application.value,
		employee: employee.data?.name,
		employee_name: employee.data?.employee_name,
		company: employee.data?.company,
		department: employee.data?.department,
		status: "Draft",
		posting_date: dayjs().format("YYYY-MM-DD"),
		attendance_date: String(q.attendance_date),
		type_of_work: application.value.type_of_work || "Personal Work",
	}

	try {
		const rows = await call("frappe.client.get_list", {
			doctype: "Attendance",
			filters: {
				employee: employee.data.name,
				attendance_date: q.attendance_date,
				docstatus: ["<", 2],
			},
			fields: ["name", "in_time", "out_time", "company"],
			limit_page_length: 1,
		})

		const att = Array.isArray(rows) ? rows[0] : null
		if (att) {
			application.value.attendance = att.name
			if (doctype.value === "Early Exit Application" && att.out_time) {
				application.value.early_exit_time = timeFromDatetime(att.out_time)
			}
		}
	} catch (e) {
		console.warn("CNR prefill attendance lookup failed", e)
	}

	formFields.reload()
}

onMounted(() => {
	applyPrefillFromQuery()
})

function validateForm() {
	application.value.employee = employee.data.name
	if (employee.data?.company) application.value.company = employee.data.company
	if (employee.data?.department) application.value.department = employee.data.department
	if (!application.value.status) application.value.status = "Draft"
	if (!application.value.posting_date) {
		application.value.posting_date = dayjs().format("YYYY-MM-DD")
	}
	if (!application.value.attendance_date) {
		application.value.attendance_date = dayjs().format("YYYY-MM-DD")
	}
	if (!application.value.type_of_work) {
		application.value.type_of_work = "Personal Work"
	}
}

// Soft deadline hint (server validate_late_early_application is authoritative)
const deadlineSettings = createResource({
	url: "nepal_hrms.api.cnr_applications.get_late_early_application_deadline_settings",
	auto: true,
})

watch(
	() => [
		application.value.attendance_date,
		application.value.estimated_from_time,
		application.value.estimated_to_time,
		doctype.value,
		deadlineSettings.data,
	],
	() => {
		const warnings = []
		const s = deadlineSettings.data
		if (
			s?.enable_late_early_application_deadline &&
			application.value.attendance_date
		) {
			const maxDays = Number(s.late_early_application_max_days || 2)
			const attDate = dayjs(application.value.attendance_date)
			const deadline = attDate.add(maxDays, "day")
			if (dayjs().startOf("day").isAfter(deadline)) {
				warnings.push(
					__(
						"{0} cannot be filed for {1}. Applications must be filed within {2} day(s) of the attendance date (deadline was {3}).",
						[
							__(doctype.value),
							attDate.format("YYYY-MM-DD"),
							maxDays,
							deadline.format("YYYY-MM-DD"),
						]
					)
				)
			}
		}

		if (
			doctype.value === "Out of Office Application" &&
			application.value.estimated_from_time &&
			application.value.estimated_to_time
		) {
			const minutes = (value) => {
				const [hours, mins, seconds] = String(value)
					.split(":")
					.map((part) => Number(part) || 0)
				return hours * 60 + mins + seconds / 60
			}
			const duration =
				(minutes(application.value.estimated_to_time) -
					minutes(application.value.estimated_from_time)) /
				60
			const maxHours = Number(s?.max_paid_out_of_office_hours || 2)
			if (duration >= 0 && maxHours > 0 && duration > maxHours) {
				warnings.push(
					__(
						"Estimated OOO duration ({0}h) exceeds the configured {1}h limit. Submission will be blocked.",
						[duration.toFixed(2), maxHours]
					)
				)
			}
		}

		deadlineWarning.value = warnings.join(" ")
	}
)
</script>
