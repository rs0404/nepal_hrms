<template>
	<!-- underline: text tabs sharing one rule, for a card that already has a
	     heading. The segmented pill needs px-8 to look right, which makes
	     three labels like "Team Requests" wrap onto two lines on a phone. -->
	<div v-if="variant === 'underline'" class="flex border-b border-gray-200">
		<button
			v-for="button in buttons"
			:key="keyOf(button)"
			class="flex-1 px-1 pb-2.5 -mb-px border-b-2 text-sm font-medium transition-colors whitespace-nowrap"
			:class="
				modelValue === keyOf(button)
					? 'border-red-600 text-red-600'
					: 'border-transparent text-gray-500'
			"
			@click="$emit('update:modelValue', keyOf(button))"
		>
			{{ button.label ?? __(button) }}
		</button>
	</div>

	<div v-else class="flex p-1 bg-gray-200 rounded">
		<button
			v-for="button in buttons"
			:key="keyOf(button)"
			class="px-8 py-2.5 transition-all rounded-[7px] flex-auto font-medium text-base"
			:class="
				modelValue === keyOf(button)
					? 'bg-white drop-shadow text-gray-900'
					: 'text-gray-600'
			"
			@click="$emit('update:modelValue', keyOf(button))"
		>
			{{ button.label ?? __(button) }}
		</button>
	</div>
</template>

<script setup>
const props = defineProps({
	buttons: {
		type: Array,
		required: true,
	},
	modelValue: {
		type: String,
	},
	variant: {
		type: String,
		default: "segmented",
	},
})

defineEmits(["update:modelValue"])

function keyOf(button) {
	return button.key ?? button.label ?? button
}
</script>
