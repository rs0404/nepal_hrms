<template>
	<ListItem
		:isTeamRequest="props.isTeamRequest"
		:employee="props.employee"
		:employeeName="props.employeeName"
		wideIcon
	>
		<template #left>
			<div
				class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
				:class="toneClasses.bg"
			>
				<FeatherIcon :name="props.icon" class="h-5 w-5" :class="toneClasses.fg" />
			</div>
			<div class="flex min-w-0 flex-1 flex-col gap-0.5">
				<div class="flex min-w-0 flex-wrap items-center gap-1.5">
					<span class="truncate text-[15px] font-semibold text-gray-900">{{ props.title }}</span>
					<slot name="title-extra" />
				</div>
				<div v-if="props.subtitle" class="truncate text-sm text-gray-600">
					{{ props.subtitle }}
				</div>
				<div class="flex flex-wrap items-center gap-x-1.5 text-xs text-gray-500">
					<template v-for="(item, index) in visibleMeta" :key="index">
						<span v-if="index" aria-hidden="true">·</span>
						<span class="whitespace-nowrap">{{ item }}</span>
					</template>
				</div>
				<div v-if="props.note" class="truncate text-xs text-red-600">{{ props.note }}</div>
			</div>
		</template>
		<template #right>
			<div class="flex flex-col items-end gap-1.5">
				<span
					class="whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold"
					:class="statusClasses"
				>
					{{ props.status }}
				</span>
				<!-- .stop: the row itself opens the request sheet. -->
				<button
					v-if="canCancel"
					type="button"
					class="flex items-center gap-1 rounded-full border border-red-200 px-2 py-0.5 text-xs font-semibold text-red-600 active:bg-red-50 disabled:opacity-50"
					:disabled="deleting"
					@click.stop="confirmCancel"
				>
					<FeatherIcon name="x" class="h-3 w-3" />
					{{ deleting ? __("Cancelling…") : __("Cancel") }}
				</button>
			</div>
			<FeatherIcon name="chevron-right" class="h-4 w-4 shrink-0 text-gray-400" />
		</template>
	</ListItem>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { FeatherIcon, call, toast } from "frappe-ui"
import { alertController } from "@ionic/vue"

import ListItem from "@/components/ListItem.vue"

const __ = inject("$translate")
const session = inject("$session")
const myEmployee = inject("$employee")

const props = defineProps({
	icon: { type: String, required: true },
	// red | green | blue | orange | purple | teal | pink | gray
	tone: { type: String, default: "gray" },
	title: { type: String, default: "" },
	subtitle: { type: String, default: "" },
	meta: { type: Array, default: () => [] },
	note: { type: String, default: "" },
	status: { type: String, default: "" },
	// green | red | orange | blue | gray
	statusTheme: { type: String, default: "gray" },
	isTeamRequest: { type: Boolean, default: false },
	employee: String,
	employeeName: String,
	// A draft nobody has decided, of a type the employee may withdraw. The row
	// still checks it is their own; the server checks everything again.
	cancellable: { type: Boolean, default: false },
	doctype: String,
	name: String,
	owner: String,
})

const deleting = ref(false)

const canCancel = computed(() => {
	if (!props.cancellable || props.isTeamRequest || !props.doctype || !props.name) return false
	// Leave lists come from stock HRMS without an owner; fall back to "it is mine".
	if (props.owner) return props.owner === session.user
	return Boolean(props.employee) && props.employee === myEmployee.data?.name
})

async function confirmCancel() {
	const alert = await alertController.create({
		header: __("Cancel this request?"),
		message: __("{0} will be deleted. This cannot be undone.", [props.title || __(props.doctype)]),
		buttons: [
			{ text: __("Keep"), role: "cancel" },
			{ text: __("Delete"), role: "destructive", handler: () => withdraw() },
		],
	})
	await alert.present()
}

async function withdraw() {
	deleting.value = true
	try {
		await call("nepal_hrms.api.request_dashboard.delete_my_draft_request", {
			doctype: props.doctype,
			name: props.name,
		})
		toast({
			title: __("Deleted"),
			text: __("{0} was cancelled.", [props.title || __(props.doctype)]),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
	} catch (error) {
		toast({
			title: __("Could not cancel"),
			text: error?.messages?.[0] || error?.message || __("Please try again."),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	} finally {
		deleting.value = false
	}
}

// Spelled out so Tailwind keeps the classes.
const TONES = {
	red: { bg: "bg-red-50", fg: "text-red-600" },
	green: { bg: "bg-green-50", fg: "text-green-600" },
	blue: { bg: "bg-blue-50", fg: "text-blue-600" },
	orange: { bg: "bg-orange-50", fg: "text-orange-600" },
	purple: { bg: "bg-purple-50", fg: "text-purple-600" },
	teal: { bg: "bg-teal-50", fg: "text-teal-600" },
	pink: { bg: "bg-pink-50", fg: "text-pink-600" },
	gray: { bg: "bg-gray-100", fg: "text-gray-600" },
}

const STATUS = {
	green: "bg-green-50 text-green-700",
	red: "bg-red-50 text-red-700",
	orange: "bg-amber-50 text-amber-700",
	blue: "bg-blue-50 text-blue-700",
	gray: "bg-gray-100 text-gray-600",
}

const toneClasses = computed(() => TONES[props.tone] || TONES.gray)
const statusClasses = computed(() => STATUS[props.statusTheme] || STATUS.gray)
const visibleMeta = computed(() => props.meta.filter(Boolean))
</script>
