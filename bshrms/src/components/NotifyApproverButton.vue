<!--
	Nudges the approver with the same PWA notification the application raised.

	Whether a nudge can land depends on the Nepal HRMS Settings row for this
	application type, so the button asks the server first and disables itself
	with the reason rather than looking alive and doing nothing.
-->
<template>
	<button
		v-if="info"
		type="button"
		class="shrink-0 p-1.5 rounded"
		:class="
			info.can_notify
				? 'text-gray-500 hover:text-gray-900 hover:bg-gray-100 active:bg-gray-200'
				: 'text-gray-300 active:bg-gray-100'
		"
		:disabled="sending"
		:aria-label="label"
		:title="label"
		@click.stop.prevent="send"
	>
		<LoadingIndicator v-if="sending" class="h-4 w-4" />
		<FeatherIcon v-else :name="sent ? 'check' : 'bell'" class="h-4 w-4" />
	</button>
</template>

<script setup>
import { computed, inject, ref, watch, onBeforeUnmount } from "vue"
import { FeatherIcon, LoadingIndicator, call, toast } from "frappe-ui"

const __ = inject("$translate")

const props = defineProps({
	doctype: { type: String, required: true },
	name: { type: String, required: true },
})

const info = ref(null)
const sending = ref(false)
const sent = ref(false)
let resetTimer = null

const label = computed(() => {
	if (!info.value) return __("Notify approver")
	if (info.value.can_notify) {
		return info.value.approver_name
			? __("Notify {0}", [info.value.approver_name])
			: __("Notify approver")
	}
	return info.value.reason || __("Cannot notify")
})

const loadInfo = async () => {
	info.value = null
	if (!props.doctype || !props.name) return
	try {
		info.value = await call(
			"nepal_hrms.api.application_share.get_share_info",
			{ doctype: props.doctype, name: props.name }
		)
	} catch (e) {
		// A document the user cannot read, or the API not deployed yet: leave
		// the button out entirely rather than showing a dead control.
		info.value = null
	}
}

const send = async () => {
	if (sending.value) return

	sending.value = true
	try {
		// This answer was fetched when the row rendered. Someone changing the
		// notification settings does not push that down, so a cached "no" has
		// to be re-checked on tap or the button stays wrong until a reload.
		if (!info.value?.can_notify) {
			await loadInfo()
		}

		// A phone has no hover, so a greyed-out icon with a title attribute
		// tells the employee nothing. Stay tappable and say why instead.
		if (!info.value?.can_notify) {
			toast({
				title: __("Cannot notify"),
				text:
					info.value?.reason ||
					__("The approver cannot be notified for this request"),
				icon: "alert-circle",
				position: "bottom-center",
				iconClasses: "text-amber-500",
			})
			return
		}

		const res = await call(
			"nepal_hrms.api.application_share.notify_approver",
			{ doctype: props.doctype, name: props.name }
		)
		sent.value = true
		clearTimeout(resetTimer)
		resetTimer = setTimeout(() => (sent.value = false), 3000)
		toast({
			title: __("Notified"),
			text: res?.approver_name
				? __("{0} has been notified", [res.approver_name])
				: __("The approver has been notified"),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
	} catch (e) {
		toast({
			title: __("Error"),
			text: __(e.message || "Could not notify the approver"),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	} finally {
		sending.value = false
	}
}

watch(() => [props.doctype, props.name], loadInfo, { immediate: true })
onBeforeUnmount(() => clearTimeout(resetTimer))
</script>
