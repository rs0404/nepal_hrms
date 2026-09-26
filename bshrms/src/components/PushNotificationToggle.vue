<!-- Device push on/off. The browser's own permission prompt appears the first
     time it is switched on; after that the state is remembered per device. -->
<template>
	<div class="flex flex-col bg-white rounded">
		<div class="flex flex-row items-center justify-between gap-3 p-4">
			<div class="flex flex-row items-center gap-3 grow min-w-0">
				<FeatherIcon name="bell" class="h-5 w-5 shrink-0 text-gray-500" />
				<div class="min-w-0">
					<div class="text-base font-normal text-gray-800">
						{{ __("Push Notifications") }}
					</div>
					<div v-if="hint" class="text-xs text-gray-500 mt-0.5">
						{{ hint }}
					</div>
				</div>
			</div>

			<LoadingIndicator v-if="busy" class="w-4 h-4 shrink-0 text-gray-800" />
			<Switch
				v-else
				size="md"
				class="shrink-0"
				:model-value="enabled"
				:disabled="disabled"
				@update:model-value="onToggle"
			/>
		</div>
	</div>
</template>

<script setup>
import { computed, inject } from "vue"
import { FeatherIcon, LoadingIndicator, Switch, toast } from "frappe-ui"

import { usePushNotifications } from "@/composables/push_notifications"

const __ = inject("$translate")

const { enabled, busy, disabled, unavailableReason, setEnabled } =
	usePushNotifications(__)

const hint = computed(
	() => unavailableReason.value || (enabled.value ? "" : __("Off on this device"))
)

const onToggle = async (next) => {
	const result = await setEnabled(next)
	if (!result.message) return

	toast({
		title: result.ok ? __("Success") : __("Notifications"),
		text: result.message,
		icon: result.ok ? "check-circle" : "alert-circle",
		position: "bottom-center",
		iconClasses: result.ok ? "text-green-500" : "text-amber-500",
	})
}
</script>
