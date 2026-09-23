<template>
	<form
		class="flex w-full flex-col gap-3 rounded-2xl border border-gray-200 bg-white p-4"
		@submit.prevent="submit"
	>
		<div class="flex items-center gap-3">
			<span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gray-100">
				<FeatherIcon name="lock" class="h-5 w-5 text-gray-600" />
			</span>
			<div class="min-w-0">
				<div class="text-[15px] font-semibold text-gray-900">
					{{ props.title || __("Salary amounts are hidden") }}
				</div>
				<div class="text-xs text-gray-500">
					{{ __("Type your {0} to see them for 5 minutes.", [fieldLabel]) }}
				</div>
			</div>
		</div>

		<input
			v-model="value"
			type="text"
			autocomplete="off"
			autocapitalize="off"
			spellcheck="false"
			class="form-input w-full rounded-lg border-gray-300"
			:placeholder="fieldLabel"
			:disabled="busy"
		/>
		<p v-if="error" class="text-xs text-red-600">{{ error }}</p>

		<div class="flex items-center justify-between gap-3">
			<span class="text-xs text-gray-400">{{ __("Set in your Profile") }}</span>
			<button
				type="submit"
				class="rounded-lg bg-gray-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
				:disabled="busy || !value.trim()"
			>
				{{ busy ? __("Checking…") : __("Show amounts") }}
			</button>
		</div>
	</form>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { FeatherIcon } from "frappe-ui"

import { salaryPrivacy, unlockSalary } from "@/data/salary_lock"

const __ = inject("$translate")

const props = defineProps({
	title: { type: String, default: "" },
})

const value = ref("")
const busy = ref(false)
const error = ref("")

const fieldLabel = computed(() => salaryPrivacy.data?.label || __("answer"))

async function submit() {
	if (!value.value.trim()) return
	busy.value = true
	error.value = ""
	try {
		const ok = await unlockSalary(value.value)
		if (ok) value.value = ""
		else error.value = __("That does not match your {0}.", [fieldLabel.value])
	} catch (e) {
		error.value = e?.messages?.[0] || e?.message || __("Could not check. Please try again.")
	} finally {
		busy.value = false
	}
}
</script>
