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

const LIST_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"attendance_date",
	"type_of_work",
	"status",
	"reason",
	"docstatus",
	"total_hours",
]

const FILTER_CONFIG = computed(() => [
	{ fieldname: "attendance_date", fieldtype: "Date", label: __("Attendance Date") },
	{
		fieldname: "status",
		fieldtype: "Select",
		label: __("Status"),
		options: "Draft\nApproved\nRejected",
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
