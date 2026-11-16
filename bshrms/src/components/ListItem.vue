<template>
	<div class="flex flex-col w-full justify-center gap-2.5">
		<div class="flex flex-row items-center justify-between">
			<div class="flex flex-row items-start gap-3 grow">
				<slot name="left" />
			</div>
			<div class="flex flex-row justify-end items-center gap-2">
				<slot name="right" />
			</div>
		</div>
		<!-- Indented to line up with the row's text, past its icon. -->
		<div
			v-if="props.isTeamRequest"
			class="flex flex-row items-center gap-2"
			:class="props.wideIcon ? 'pl-[52px]' : 'pl-8'"
		>
			<EmployeeAvatar :employeeID="props.employee" />
			<div class="text-sm text-gray-600 grow">
				{{ props.employeeName }}
			</div>
			<span
				v-if="props.commentCount"
				class="flex shrink-0 items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700"
				:title="__('{0} comments', [props.commentCount])"
			>
				<FeatherIcon name="message-square" class="h-3 w-3" />
				{{ props.commentCount }}
			</span>
		</div>
	</div>
</template>

<script setup>
import { inject } from "vue"
import { FeatherIcon } from "frappe-ui"

import EmployeeAvatar from "@/components/EmployeeAvatar.vue"

const __ = inject("$translate")

const props = defineProps({
	isTeamRequest: {
		type: Boolean,
		default: false,
	},
	employee: {
		type: String,
		required: false,
	},
	employeeName: {
		type: String,
		required: false,
	},
	commentCount: {
		type: Number,
		default: 0,
	},
	// RequestRow's 40px icon circle rather than a bare 20px icon.
	wideIcon: {
		type: Boolean,
		default: false,
	},
})
</script>
