<template>
	<ion-page>
		<ListView
			doctype="Attendance"
			:pageTitle="__('Attendance')"
			:fields="ATTENDANCE_FIELDS"
			:filterConfig="FILTER_CONFIG"
		/>
	</ion-page>
</template>

<script setup>
import { IonPage } from "@ionic/vue"
import ListView from "@/components/ListView.vue"
import { inject } from "vue"

const __ = inject("$translate")

const ATTENDANCE_FIELDS = [
	"name",
	"employee",
	"attendance_date",
	"status",
	"working_hours",
	"in_time",
	"out_time",
	"leave_type",
	"leave_application",
	"attendance_request",
	"shift",
	"docstatus",
]

const FILTER_CONFIG = [
	{
		fieldname: "status",
		fieldtype: "Select",
		label: __("Status"),
		options: "Present\nAbsent\nOn Leave\nHalf Day\nWork From Home\nHoliday",
	},
	{
		fieldname: "attendance_date",
		fieldtype: "Date",
		label: __("Attendance Date"),
	},
]
</script>
