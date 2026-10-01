<template>
	<!--
		The day as two halves, the leave's part filled -- the same split the
		calendar shades -- so the halves differ by position, not colour alone.
		Pass a title: it is the mark's only text.
	-->
	<span
		class="inline-flex shrink-0 overflow-hidden rounded-sm ring-1 ring-inset ring-blue-600"
		role="img"
		:aria-label="$attrs.title"
	>
		<span class="h-2.5 w-2" :class="fill.first" />
		<span class="w-px bg-blue-600" />
		<span class="h-2.5 w-2" :class="fill.second" />
	</span>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
	// full | first | second | half (a half day whose half is unknown)
	span: { type: String, default: "full" },
})

const FILLED = "bg-blue-600"
const EMPTY = "bg-white"
const UNKNOWN = "bg-blue-200"

const fill = computed(() => {
	if (props.span === "first") return { first: FILLED, second: EMPTY }
	if (props.span === "second") return { first: EMPTY, second: FILLED }
	if (props.span === "half") return { first: UNKNOWN, second: UNKNOWN }
	return { first: FILLED, second: FILLED }
})
</script>
