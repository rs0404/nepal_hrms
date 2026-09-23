<template>
	<div class="flex flex-col gap-3 my-4 w-full">
		<div class="text-lg font-bold text-gray-900">{{ title || __("Quick Links") }}</div>
		<div class="grid grid-cols-4 gap-3">
			<router-link
				class="flex flex-col items-center justify-start gap-2 bg-white rounded-xl p-3 shadow-sm active:bg-gray-50"
				v-for="link in props.items"
				:key="link.title"
				:to="{ name: link.route }"
			>
				<component
					:is="link.icon"
					v-if="link.icon"
					class="h-6 w-6 shrink-0"
					:class="toneClass(link.tone)"
				/>
				<FeatherIcon
					v-else
					:name="link.feather"
					class="h-6 w-6 shrink-0"
					:class="toneClass(link.tone)"
				/>
				<!-- Two lines, centred: 'Request Attendance' wraps, the rest do not,
				     and tiles in a row must stay the same height either way. -->
				<div class="text-xs font-normal text-gray-800 text-center leading-tight">
					{{ link.title }}
				</div>
			</router-link>
		</div>
	</div>
</template>

<script setup>
import { FeatherIcon } from "frappe-ui"

// Tailwind only ships the classes it can see in the source, so these are spelled
// out rather than built as `text-${tone}-600` at runtime.
const TONES = {
	red: "text-red-600",
	green: "text-green-600",
	blue: "text-blue-600",
	orange: "text-orange-500",
	gray: "text-gray-500",
}

const props = defineProps({
	title: {
		type: String,
		required: false,
		default: "",
	},
	items: {
		type: Array,
		required: true,
	},
})

function toneClass(tone) {
	return TONES[tone] || TONES.gray
}
</script>
