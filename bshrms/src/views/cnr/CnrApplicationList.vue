<template>
	<ion-page>
		<ListView
			:doctype="doctype"
			:pageTitle="pageTitle"
			:fields="LIST_FIELDS"
			:filterConfig="FILTER_CONFIG"
			:tabButtons="tabButtons"
		/>
	</ion-page>
</template>

<script setup>
import { IonPage } from "@ionic/vue"
import { computed, inject } from "vue"
import { useRoute } from "vue-router"
import ListView from "@/components/ListView.vue"

const __ = inject("$translate")
const route = useRoute()

const props = defineProps({
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

const pageTitle = computed(() => __("{0} History", [__(doctype.value)]))

const LIST_FIELDS = computed(() => {
	const fields = [
		"name",
		"employee",
		"employee_name",
		"attendance_date",
		"type_of_work",
		"status",
		"reason",
		"docstatus",
	]
	if (doctype.value === "Out of Office Application") {
		fields.push(
			"estimated_from_time",
			"estimated_to_time",
			"from_time",
			"to_time",
			"total_hours"
		)
	} else if (doctype.value === "Late Entry Application") {
		fields.push("estimated_late_entry_time", "late_entry_time")
	} else if (doctype.value === "Early Exit Application") {
		fields.push("early_exit_time")
	}
	return fields
})

const FILTER_CONFIG = computed(() => [
	{ fieldname: "attendance_date", fieldtype: "Date", label: __("Attendance Date") },
	{
		fieldname: "status",
		fieldtype: "Select",
		label: __("Status"),
		options: [
			{ label: __("Waiting for Approval"), value: "Draft" },
			{ label: __("Approved"), value: "Approved" },
			{ label: __("Rejected"), value: "Rejected" },
		],
	},
	{
		fieldname: "type_of_work",
		fieldtype: "Select",
		label: __("Type of Work"),
		options: "Personal Work\nOffice Work",
	},
])

const tabButtons = ["My Applications", "Team Applications"]
</script>
