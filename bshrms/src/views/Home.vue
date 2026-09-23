<template>
	<BaseLayout>
		<template #body>
			<div class="flex flex-col items-center my-7 p-4 gap-7">
				<div class="w-full">
					<div class="text-base text-gray-600">{{ greeting }}</div>
					<div class="text-2xl font-bold text-gray-900">{{ firstName }}</div>
				</div>

				<CheckInPanel />
				<QuickLinks :items="quickLinks" :title="__('Quick Links')" />

				<div class="w-full px-1" v-if="oooCheckins.data?.length">
					<button
						type="button"
						class="w-full flex items-center justify-between px-1 mb-2"
						@click="oooExpanded = !oooExpanded"
					>
						<span class="text-lg text-gray-800 font-bold">
							{{ __("Out of Office Work") }}
							<span class="text-sm font-medium text-gray-500 ml-1">
								({{ oooCheckins.data.length }})
							</span>
						</span>
						<FeatherIcon
							:name="oooExpanded ? 'chevron-up' : 'chevron-down'"
							class="w-5 h-5 text-gray-500"
						/>
					</button>
					<div v-show="oooExpanded" class="flex flex-col gap-3">
						<div
							v-for="log in oooCheckins.data"
							:key="log.name"
							class="bg-white p-4 rounded-lg shadow-sm border border-gray-100"
						>
							<div class="flex justify-between items-start mb-2">
								<div class="flex flex-col">
									<span class="text-sm font-bold text-gray-800">
										{{ formatTimestamp(log.time) }}
									</span>
								</div>
								<Badge
									:label="
										log.custom_attendance_type === 'OOO Work'
											? 'OOO ' + __(log.log_type)
											: __(log.log_type)
									"
									:theme="log.log_type === 'IN' ? 'green' : 'orange'"
									size="sm"
								/>
							</div>
							<div class="text-xs text-gray-500 flex items-center gap-1 mb-1">
								<FeatherIcon name="map-pin" class="w-3 h-3" />
								<span>{{ log.latitude }}, {{ log.longitude }}</span>
							</div>
							<div class="text-sm text-gray-700 italic" v-if="log.custom_reason">
								"{{ log.custom_reason }}"
							</div>
						</div>
					</div>
				</div>

				<RequestPanel />
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { createListResource, Badge, FeatherIcon } from "frappe-ui"

import CheckInPanel from "@/components/CheckInPanel.vue"
import QuickLinks from "@/components/QuickLinks.vue"
import BaseLayout from "@/components/BaseLayout.vue"
import RequestPanel from "@/components/RequestPanel.vue"
import { formatTimestamp } from "@/utils/formatters"

import { userResource } from "@/data/user"

const __ = inject("$translate")
const employee = inject("$employee")
const oooExpanded = ref(false)

const firstName = computed(() => userResource.data?.first_name || "")

// Server time would be the employee's shift timezone, not theirs; the greeting is
// a pleasantry, so the device clock is the right thing to read.
const greeting = computed(() => {
	const hour = new Date().getHours()
	if (hour < 12) return __("Good morning")
	if (hour < 17) return __("Good afternoon")
	return __("Good evening")
})

const oooCheckins = createListResource({
	doctype: "Employee Checkin",
	fields: ["name", "time", "log_type", "latitude", "longitude", "custom_attendance_type", "custom_reason"],
	filters: {
		employee: employee.data.name,
		custom_attendance_type: "OOO Work",
	},
	orderBy: "time desc",
	limit: 5,
	auto: true,
})

const quickLinks = [
	{ feather: "calendar", tone: "red", title: __("Request Attendance"), route: "AttendanceRequestFormView" },
	{ feather: "clock", tone: "red", title: __("Late Entry"), route: "LateEntryApplicationFormView" },
	{ feather: "log-out", tone: "red", title: __("Early Exit"), route: "EarlyExitApplicationFormView" },
	{ feather: "briefcase", tone: "red", title: __("Out of Office"), route: "OutOfOfficeApplicationFormView" },
	{ feather: "watch", tone: "red", title: __("Shift"), route: "ShiftRequestFormView" },
	{ feather: "calendar", tone: "green", title: __("Leave"), route: "LeaveApplicationFormView" },
	{ feather: "file-text", tone: "blue", title: __("Expense"), route: "ExpenseClaimFormView" },
	{ feather: "credit-card", tone: "orange", title: __("Advance"), route: "EmployeeAdvanceFormView" },
]
</script>
