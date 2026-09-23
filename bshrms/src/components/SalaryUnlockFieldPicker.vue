<template>
	<div v-if="salaryPrivacy.data?.enabled" class="flex flex-col rounded bg-white">
		<label class="flex flex-row items-center justify-between gap-3 p-4">
			<div class="flex min-w-0 grow flex-row items-center gap-3">
				<FeatherIcon name="lock" class="h-5 w-5 shrink-0 text-gray-500" />
				<div class="min-w-0">
					<div class="text-base font-normal text-gray-800">{{ __("Salary Unlock") }}</div>
					<div class="text-xs text-gray-500">
						{{ __("Type this to see salary amounts") }}
					</div>
				</div>
			</div>
			<select
				class="form-select max-w-[45%] rounded border-gray-300 text-sm"
				:value="salaryPrivacy.data.field"
				:disabled="saving"
				@change="save($event.target.value)"
			>
				<option
					v-for="option in salaryPrivacy.data.fields"
					:key="option.fieldname"
					:value="option.fieldname"
				>
					{{ option.label }}
				</option>
			</select>
		</label>
	</div>
</template>

<script setup>
import { inject, ref } from "vue"
import { FeatherIcon, call, toast } from "frappe-ui"

import { lockSalary, salaryPrivacy } from "@/data/salary_lock"

const __ = inject("$translate")
const saving = ref(false)

async function save(fieldname) {
	saving.value = true
	try {
		salaryPrivacy.setData(
			await call("nepal_hrms.api.salary_privacy.set_salary_unlock_field", { fieldname })
		)
		// A new answer should be asked for, not ride on the old unlock.
		lockSalary()
		toast({
			title: __("Saved"),
			text: __("Unlock field set to {0}.", [salaryPrivacy.data.label]),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
	} catch (e) {
		toast({
			title: __("Could not save"),
			text: e?.messages?.[0] || __("Please try again."),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	} finally {
		saving.value = false
	}
}
</script>
