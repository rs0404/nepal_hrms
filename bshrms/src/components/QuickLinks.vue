<template>
	<div class="flex flex-col gap-3 w-full">
		<div class="px-1 text-lg font-bold text-gray-900">{{ title || __("Quick Links") }}</div>
		<div class="grid grid-cols-4 gap-3">
			<router-link
				class="flex flex-col items-center justify-start gap-2 bg-white rounded-xl p-3 shadow-sm active:bg-gray-50"
				v-for="link in props.items"
				:key="link.title"
				:to="{ name: link.route }"
			>
				<div
					class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full"
					:class="toneBg(link.tone)"
				>
					<component
						:is="link.icon"
						v-if="link.icon"
						class="h-5 w-5"
						:class="toneClass(link.tone)"
					/>
					<FeatherIcon
						v-else
						:name="link.feather"
						class="h-5 w-5"
						:class="toneClass(link.tone)"
					/>
				</div>
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
	purple: "text-purple-600",
	teal: "text-teal-600",
	pink: "text-pink-600",
	amber: "text-amber-600",
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

const TONE_BG = {
	red: "bg-red-50",
	green: "bg-green-50",
	blue: "bg-blue-50",
	orange: "bg-orange-50",
	purple: "bg-purple-50",
	teal: "bg-teal-50",
	pink: "bg-pink-50",
	amber: "bg-amber-50",
	gray: "bg-gray-100",
}

function toneBg(tone) {
	return TONE_BG[tone] || TONE_BG.gray
}

function toneClass(tone) {
	return TONES[tone] || TONES.gray
}
</script>
