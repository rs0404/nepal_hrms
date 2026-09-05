<template>
	<div class="flex flex-col gap-3">
		<div class="flex items-center gap-1.5">
			<button
				type="button"
				class="flex-1 text-left rounded-md border border-gray-200 bg-white px-2.5 py-1.5"
				@click="openDatePicker"
			>
				<div class="text-sm font-semibold text-gray-900 leading-5">
					{{ formatNepaliDate(attendanceDate) }}
					<span class="text-[11px] font-medium text-gray-500">
						{{ dayjs(attendanceDate).format("D MMM YYYY") }}
					</span>
				</div>
			</button>
			<Button
				v-if="!isToday"
				variant="subtle"
				class="!text-[11px] shrink-0"
				@click="goToday"
			>
				{{ __("Today") }}
			</Button>
			<Button variant="subtle" class="!text-[11px] shrink-0" @click="liveBoard.reload()">
				{{ __("Refresh") }}
			</Button>
		</div>

		<div v-if="liveBoard.loading && !liveBoard.data" class="text-xs text-gray-400 text-center py-4">
			{{ __("Loading live attendance…") }}
		</div>
		<div v-else-if="liveBoard.error" class="text-xs text-red-500 text-center py-4">
			{{ __("Could not load live attendance") }}
		</div>
		<template v-else>
			<div class="grid grid-cols-3 gap-1.5">
				<button
					v-for="col in visibleColumns"
					:key="col.key"
					type="button"
					class="rounded-lg px-2 py-2 text-center ring-1 ring-inset"
					:class="
						activeCol === col.key
							? col.activeClass
							: 'bg-white ring-gray-200 text-gray-600'
					"
					@click="activeCol = col.key"
				>
					<div class="text-base font-semibold leading-5">{{ col.count }}</div>
					<div class="text-[10px] font-medium leading-4">{{ __(col.label) }}</div>
				</button>
			</div>

			<div
				class="rounded-lg border divide-y overflow-hidden"
				:class="activeColMeta.listClass"
			>
				<div v-if="!activeRows.length" class="text-xs text-gray-400 italic p-4 text-center bg-white">
					{{ __("No employees in this list") }}
				</div>
				<template v-else>
					<div
						v-for="group in groupedActiveRows"
						:key="group.department"
						class="flex flex-col"
					>
						<div
							class="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide"
							:class="activeColMeta.headerClass"
						>
							{{ group.department }}
							<span class="font-medium normal-case"> ({{ group.rows.length }})</span>
						</div>
						<div
							v-for="emp in group.rows"
							:key="emp.name + (emp.punches || []).join()"
							class="px-3 py-2.5 border-t"
							:class="activeColMeta.rowClass"
						>
							<div class="text-sm font-semibold text-gray-800">
								{{ emp.employee_name || emp.name }}
							</div>
							<div class="flex flex-wrap gap-1 mt-1.5" v-if="emp.punches?.length">
								<span
									v-for="(punch, idx) in emp.punches"
									:key="idx"
									class="text-[10px] font-semibold px-1.5 py-0.5 rounded"
									:class="punchClass(punch)"
								>
									{{ punch }}
								</span>
							</div>
						</div>
					</div>
				</template>
			</div>
		</template>

		<NepaliDatePickerDialog
			v-model="showDatePicker"
			:initialDate="attendanceDate"
			@dateSelected="onDateSelected"
		/>
	</div>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { createResource, Button } from "frappe-ui"

import NepaliDatePickerDialog from "@/components/NepaliDatePickerDialog.vue"
import { formatNepaliDate } from "@/utils/nepali_date"

const props = defineProps({
	leaveBoardOnly: { type: Boolean, default: false },
	canViewPast: { type: Boolean, default: false },
})

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const attendanceDate = ref(dayjs().format("YYYY-MM-DD"))
const showDatePicker = ref(false)
const activeCol = ref(props.leaveBoardOnly ? "leave" : "pending")

const isToday = computed(() => attendanceDate.value === dayjs().format("YYYY-MM-DD"))

const ALL_COLUMNS = [
	{
		key: "pending",
		label: "Pending",
		activeClass: "bg-red-50 ring-red-200 text-red-700",
		listClass: "border-red-100",
		headerClass: "bg-red-100 text-red-800",
		rowClass: "bg-red-50/80 border-red-100",
		live: true,
	},
	{
		key: "active",
		label: "Active",
		activeClass: "bg-green-50 ring-green-200 text-green-700",
		listClass: "border-green-100",
		headerClass: "bg-green-100 text-green-800",
		rowClass: "bg-green-50/80 border-green-100",
		live: true,
	},
	{
		key: "completed",
		label: "Checked Out",
		activeClass: "bg-blue-50 ring-blue-200 text-blue-700",
		listClass: "border-blue-100",
		headerClass: "bg-blue-100 text-blue-800",
		rowClass: "bg-blue-50/80 border-blue-100",
		live: true,
	},
	{
		key: "leave",
		label: "On Leave",
		activeClass: "bg-violet-50 ring-violet-200 text-violet-700",
		listClass: "border-violet-100",
		headerClass: "bg-violet-100 text-violet-800",
		rowClass: "bg-violet-50/80 border-violet-100",
		live: false,
	},
	{
		key: "upcoming",
		label: "Upcoming",
		activeClass: "bg-orange-50 ring-orange-200 text-orange-700",
		listClass: "border-orange-100",
		headerClass: "bg-orange-100 text-orange-800",
		rowClass: "bg-orange-50/80 border-orange-100",
		live: false,
	},
	{
		key: "pending_leave",
		label: "Pending Leave",
		activeClass: "bg-amber-50 ring-amber-200 text-amber-700",
		listClass: "border-amber-100",
		headerClass: "bg-amber-100 text-amber-800",
		rowClass: "bg-amber-50/80 border-amber-100",
		live: false,
	},
]

const liveBoard = createResource({
	url: "nepal_hrms.api.pwa_access.get_pwa_live_attendance",
	makeParams: () => ({ attendance_date: attendanceDate.value }),
	auto: true,
	onSuccess() {
		const cols = visibleColumns.value
		if (!cols.find((c) => c.key === activeCol.value)) {
			activeCol.value = cols[0]?.key
		}
	},
})

function flatten(grouped) {
	const rows = []
	for (const list of Object.values(grouped || {})) {
		for (const emp of list || []) rows.push(emp)
	}
	return rows
}

const visibleColumns = computed(() => {
	const leaveOnly = props.leaveBoardOnly || liveBoard.data?.leave_board_only
	return ALL_COLUMNS.filter((col) => (leaveOnly ? !col.live : true)).map((col) => ({
		...col,
		count: flatten(liveBoard.data?.[col.key]).length,
	}))
})

const activeColMeta = computed(
	() =>
		ALL_COLUMNS.find((c) => c.key === activeCol.value) || {
			listClass: "border-gray-100",
			headerClass: "bg-gray-50 text-gray-500",
			rowClass: "bg-white border-gray-100",
		}
)

const activeRows = computed(() => flatten(liveBoard.data?.[activeCol.value]))

const groupedActiveRows = computed(() => {
	const byDept = {}
	for (const emp of activeRows.value) {
		const dept = emp.department || __("No Department")
		if (!byDept[dept]) byDept[dept] = []
		byDept[dept].push(emp)
	}
	return Object.entries(byDept).map(([department, rows]) => ({ department, rows }))
})

function punchClass(punch) {
	const s = String(punch || "")
	if (s.includes("(IN)") || s.includes("(OOO IN)")) return "bg-green-50 text-green-700"
	if (s.includes("(OUT)") || s.includes("(OOO OUT)")) return "bg-red-50 text-red-700"
	return "bg-gray-100 text-gray-600"
}

function openDatePicker() {
	if (!props.canViewPast && !isToday.value) {
		attendanceDate.value = dayjs().format("YYYY-MM-DD")
	}
	showDatePicker.value = true
}

function onDateSelected(val) {
	if (!val) return
	if (!props.canViewPast && val < dayjs().format("YYYY-MM-DD")) {
		attendanceDate.value = dayjs().format("YYYY-MM-DD")
	} else {
		attendanceDate.value = val
	}
	liveBoard.reload()
}

function goToday() {
	attendanceDate.value = dayjs().format("YYYY-MM-DD")
	liveBoard.reload()
}
</script>
