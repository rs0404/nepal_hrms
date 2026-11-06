<template>
	<div class="flex flex-col w-full">
		<div class="flex flex-row justify-between items-center px-4">
			<div class="text-lg text-gray-800 font-bold">{{ __("Leave Balance") }} </div>
			<router-link
				:to="{ name: 'LeaveApplicationListView' }"
				v-slot="{ navigate }"
				v-if="hasBalances"
			>
				<div
					@click="navigate"
					class="text-sm text-gray-800 font-semibold cursor-pointer underline underline-offset-2"
				>
					{{ __("View Leave History") }}
				</div>
			</router-link>
		</div>

		<template v-if="hasBalances">
			<div class="grid grid-cols-2 gap-3 px-4 mt-3">
				<div
					v-for="(balance, leave_type) in leaveBalance.data"
					:key="leave_type"
					class="flex flex-col items-center bg-white rounded-lg drop-shadow-md p-3 text-center"
				>
					<svg
						viewBox="0 0 36 36"
						class="h-20 w-20"
						role="img"
						:aria-label="__('{0} of {1} days left', [balance.left, balance.allocated])"
					>
						<circle
							cx="18"
							cy="18"
							:r="RADIUS"
							fill="none"
							stroke="currentColor"
							stroke-width="3.2"
							class="text-gray-200"
						/>
						<circle
							v-for="arc in arcsFor(balance)"
							:key="arc.key"
							cx="18"
							cy="18"
							:r="RADIUS"
							fill="none"
							stroke="currentColor"
							stroke-width="3.2"
							:class="arc.colorClass"
							:style="arc.color ? { color: arc.color } : null"
							:stroke-dasharray="`${arc.length} ${100 - arc.length}`"
							:stroke-dashoffset="-arc.start"
							transform="rotate(-90 18 18)"
						/>
						<text
							x="18"
							y="18"
							text-anchor="middle"
							class="fill-gray-900 font-bold"
							style="font-size: 9px"
						>
							{{ balance.left }}
						</text>
						<text
							x="18"
							y="24.5"
							text-anchor="middle"
							class="fill-gray-500"
							style="font-size: 4.5px"
						>
							{{ __("left") }}
						</text>
					</svg>

					<div class="mt-1 text-sm font-semibold text-gray-800 leading-5 line-clamp-2">
						{{ __(leave_type, null, "Leave Type") }}
					</div>
					<div class="text-xs text-gray-600">
						{{ __("{0} of {1} used", [balance.used, balance.allocated]) }}
					</div>
					<div v-if="balance.pending || balance.expired" class="text-xs">
						<span v-if="balance.pending" class="text-orange-600">
							{{ __("{0} pending", [balance.pending]) }}
						</span>
						<span v-if="balance.pending && balance.expired" class="text-gray-400"> · </span>
						<span v-if="balance.expired" class="text-gray-500">
							{{ __("{0} expired", [balance.expired]) }}
						</span>
					</div>
				</div>
			</div>

			<div class="flex flex-row flex-wrap gap-x-4 gap-y-1 px-4 mt-3 text-xs text-gray-600">
				<span class="flex items-center gap-1.5">
					<span class="h-2.5 w-2.5 rounded-sm" :style="{ backgroundColor: USED_COLOR }" />
					{{ __("Used") }}
				</span>
				<span class="flex items-center gap-1.5">
					<span class="h-2.5 w-2.5 rounded-sm bg-orange-400" />
					{{ __("Pending approval") }}
				</span>
				<span class="flex items-center gap-1.5">
					<span class="h-2.5 w-2.5 rounded-sm bg-gray-200" />
					{{ __("Left") }}
				</span>
			</div>
		</template>

		<EmptyState :message="__('You have no leaves allocated')" v-else />
	</div>
</template>

<script setup>
import { computed, inject, onMounted } from "vue"

import { leaveBalance } from "@/data/leaves"
import { OUTCOME } from "@/utils/attendance_colors"

const __ = inject("$translate")

// Circumference 100, so a segment's length is its percentage of the allocation.
const RADIUS = 15.9155
// Leave days are this blue on the attendance calendars; pending takes the orange
// of the Pending status pill.
const USED_COLOR = OUTCOME.leave.ring

const hasBalances = computed(() => Object.keys(leaveBalance.data || {}).length > 0)

onMounted(() => {
	if (!leaveBalance.data) leaveBalance.reload()
})

function arcsFor(balance) {
	const total = Number(balance.allocated) || 0
	if (total <= 0) return []
	const parts = [
		{ key: "used", days: balance.used, color: USED_COLOR },
		{ key: "pending", days: balance.pending, colorClass: "text-orange-400" },
		{ key: "expired", days: balance.expired, colorClass: "text-gray-400" },
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
