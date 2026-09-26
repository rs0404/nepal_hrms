<!-- Copies a link to this application so it can be pasted to the approver. -->
<template>
	<button
		type="button"
		class="shrink-0 p-1.5 rounded text-gray-500 hover:text-gray-900 hover:bg-gray-100 active:bg-gray-200"
		:aria-label="__('Copy link')"
		:title="__('Copy link')"
		@click.stop.prevent="copy"
	>
		<FeatherIcon :name="copied ? 'check' : 'link-2'" class="h-4 w-4" />
	</button>
</template>

<script setup>
import { inject, ref, onBeforeUnmount } from "vue"
import { FeatherIcon, toast } from "frappe-ui"
import { applicationLink, copyText } from "@/utils/application_share"

const __ = inject("$translate")

const props = defineProps({
	doctype: { type: String, required: true },
	name: { type: String, required: true },
})

const copied = ref(false)
let resetTimer = null

// The tick is the confirmation people actually look at; the toast carries the
// link so it can be read back before pasting.
const copy = async () => {
	const link = applicationLink(props.doctype, props.name)
	if (!link) return

	const ok = await copyText(link)
	if (!ok) {
		toast({
			title: __("Error"),
			text: __("Could not copy the link"),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
		return
	}

	copied.value = true
	clearTimeout(resetTimer)
	resetTimer = setTimeout(() => (copied.value = false), 2000)

	toast({
		title: __("Link copied"),
		text: link,
		icon: "check-circle",
		position: "bottom-center",
		iconClasses: "text-green-500",
	})
}

onBeforeUnmount(() => clearTimeout(resetTimer))
</script>
