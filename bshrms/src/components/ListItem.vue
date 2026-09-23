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
		</div>
	</div>
</template>

<script setup>
import EmployeeAvatar from "@/components/EmployeeAvatar.vue"

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
	// RequestRow's 40px icon circle rather than a bare 20px icon.
	wideIcon: {
		type: Boolean,
		default: false,
	},
})
</script>
