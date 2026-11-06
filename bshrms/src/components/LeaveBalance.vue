<template>
	<div class="flex flex-col w-full">
		<div class="flex flex-row justify-between items-center px-4">
			<div class="text-lg text-gray-800 font-bold">{{ __("Leave Balance") }} </div>
			<div v-if="hasBalances" class="flex flex-row items-center gap-3">
				<router-link :to="{ name: 'LeaveApplicationListView' }" v-slot="{ navigate }">
					<div
						@click="navigate"
						class="text-sm text-gray-800 font-semibold cursor-pointer underline underline-offset-2"
					>
						{{ __("View Leave History") }}
					</div>
				</router-link>
				<button
					v-if="canExpand"
					type="button"
					class="flex h-7 w-7 items-center justify-center rounded-full bg-gray-100 text-gray-700 active:bg-gray-200"
					:aria-label="expanded ? __('Show in one row') : __('Show all')"
					:aria-expanded="expanded"
					@click="expanded = !expanded"
				>
					<FeatherIcon :name="expanded ? 'chevron-up' : 'chevron-down'" class="h-4 w-4" />
				</button>
			</div>
		</div>

		<template v-if="hasBalances">
			<!-- One scrolling row, three cards to a screen; the arrow lays them all out. -->
			<div
				class="px-4 mt-3"
				:class="
					expanded
						? 'grid grid-cols-3 gap-2'
						: 'flex flex-row gap-2 overflow-x-auto snap-x hide-scrollbar pb-2'
				"
			>
				<button
					v-for="(balance, leave_type) in leaveBalance.data"
					:key="leave_type"
					type="button"
					class="flex flex-col items-center bg-white rounded-lg drop-shadow-md px-1.5 py-2 text-center active:bg-gray-50"
					:class="expanded ? '' : 'shrink-0 snap-start w-[calc((100%-1rem)/3)]'"
					@click="openHistory(leave_type, balance)"
				>
					<svg
						viewBox="0 0 36 36"
						class="h-14 w-14"
						role="img"
						:aria-label="__('{0} of {1} days left', [balance.left, balance.allocated])"
					>
						<circle
							cx="18"
							cy="18"
							:r="RADIUS"
							fill="none"
							stroke="currentColor"
							stroke-width="3.6"
							:style="{ color: LEFT_COLOR }"
						/>
						<circle
							v-for="arc in arcsFor(balance)"
							:key="arc.key"
							cx="18"
							cy="18"
							:r="RADIUS"
							fill="none"
							stroke="currentColor"
							stroke-width="3.6"
							:class="arc.colorClass"
							:style="arc.color ? { color: arc.color } : null"
							:stroke-dasharray="`${arc.length} ${100 - arc.length}`"
							:stroke-dashoffset="-arc.start"
							transform="rotate(-90 18 18)"
						/>
						<text
							x="18"
							y="19"
							text-anchor="middle"
							class="fill-gray-900 font-bold"
							style="font-size: 10px"
						>
							{{ balance.left }}
						</text>
						<text
							x="18"
							y="25.5"
							text-anchor="middle"
							class="fill-gray-500"
							style="font-size: 5px"
						>
							{{ __("left") }}
						</text>
					</svg>

					<div class="mt-1 min-h-[2rem] text-xs font-semibold text-gray-800 leading-4 line-clamp-2">
						{{ __(leave_type, null, "Leave Type") }}
					</div>
					<div class="text-[11px] leading-4 text-gray-600">
						{{ __("{0}/{1} approved", [balance.used, balance.allocated]) }}
					</div>
					<div class="text-[11px] leading-4 min-h-[1rem]">
						<span v-if="balance.pending" class="text-orange-600">
							{{ __("{0} pending", [balance.pending]) }}
						</span>
						<span v-else-if="balance.expired" class="text-gray-500">
							{{ __("{0} expired", [balance.expired]) }}
						</span>
					</div>
				</button>
			</div>

			<div class="flex flex-row flex-wrap gap-x-4 gap-y-1 px-4 mt-2 text-xs text-gray-600">
				<span v-for="item in legend" :key="item.label" class="flex items-center gap-1.5">
					<span
						class="h-2.5 w-2.5 rounded-sm"
						:class="item.colorClass"
						:style="item.color ? { backgroundColor: item.color } : null"
					/>
					{{ item.label }}
				</span>
			</div>
		</template>

		<EmptyState :message="__('You have no leaves allocated')" v-else />

		<!-- The leave behind one card: tap a row for the application itself. -->
		<ion-modal
			:is-open="!!selected"
			@didDismiss="selected = null"
			:initial-breakpoint="1"
			:breakpoints="[0, 1]"
		>
			<div v-if="selected" class="flex flex-col bg-white p-4 pb-6 standalone:pb-safe-bottom">
				<div class="text-lg font-bold text-gray-900">
					{{ __(selected.leaveType, null, "Leave Type") }}
				</div>
				<div v-if="selected.balance.from_date" class="text-xs text-gray-500">
					{{ formatDualPeriod(selected.balance.from_date, selected.balance.to_date) }}
				</div>
				<div class="mt-2 flex flex-row flex-wrap gap-x-3 text-sm">
					<span class="text-gray-800">{{ __("{0} approved", [selected.balance.used]) }}</span>
					<span v-if="selected.balance.pending" class="text-orange-600">
						{{ __("{0} pending", [selected.balance.pending]) }}
					</span>
					<span class="text-gray-800">{{ __("{0} left", [selected.balance.left]) }}</span>
				</div>

				<div v-if="history.loading" class="py-8 text-center text-sm text-gray-500">
					{{ __("Loading…") }}
				</div>
				<div v-else class="max-h-[60vh] overflow-y-auto">
					<RequestList
						:component="markRaw(LeaveRequestItem)"
						:items="history.data"
						:emptyStateMessage="__('No {0} taken in this period', [__(selected.leaveType, null, 'Leave Type')])"
					/>
				</div>
			</div>
		</ion-modal>
	</div>
</template>

<script setup>
import { computed, inject, markRaw, onMounted, ref } from "vue"
import { IonModal } from "@ionic/vue"
import { FeatherIcon, createResource } from "frappe-ui"

import LeaveRequestItem from "@/components/LeaveRequestItem.vue"
import RequestList from "@/components/RequestList.vue"
import { leaveBalance, transformLeaveData } from "@/data/leaves"
import { OUTCOME } from "@/utils/attendance_colors"
import { formatDualPeriod } from "@/utils/nepali_date"

const __ = inject("$translate")

// Circumference 100, so a segment's length is its percentage of the allocation.
const RADIUS = 15.9155
// Days still left take the calendar's Present green, approved days its leave
// blue, and pending the orange of the Pending status pill.
const LEFT_COLOR = OUTCOME.present.ring
const USED_COLOR = OUTCOME.leave.ring
const CARDS_PER_ROW = 3

const legend = [
	{ label: __("Left"), color: LEFT_COLOR },
	{ label: __("Approved"), color: USED_COLOR },
	{ label: __("Pending approval"), colorClass: "bg-orange-400" },
]

const expanded = ref(false)
const selected = ref(null)

const hasBalances = computed(() => Object.keys(leaveBalance.data || {}).length > 0)
const canExpand = computed(() => Object.keys(leaveBalance.data || {}).length > CARDS_PER_ROW)

const history = createResource({
	url: "nepal_hrms.api.leave_application.get_leave_type_history",
	transform: (data) => transformLeaveData(data || []),
})

onMounted(() => {
	if (!leaveBalance.data) leaveBalance.reload()
})

function openHistory(leaveType, balance) {
	selected.value = { leaveType, balance }
	history.submit({
		leave_type: leaveType,
		from_date: balance.from_date,
		to_date: balance.to_date,
	})
}

function arcsFor(balance) {
	const total = Number(balance.allocated) || 0
	if (total <= 0) return []
	const parts = [
		{ key: "used", days: balance.used, color: USED_COLOR },
		{ key: "pending", days: balance.pending, colorClass: "text-orange-400" },
		{ key: "expired", days: balance.expired, colorClass: "text-gray-300" },
	]
	const arcs = []
	let start = 0
	for (const part of parts) {
		const length = Math.min((Number(part.days) / total) * 100 || 0, 100 - start)
		if (length <= 0) continue
		arcs.push({ ...part, start, length })
		start += length
	}
	return arcs
}
</script>
