<template>
	<div
		v-if="showField"
		class="flex flex-col gap-1.5"
		:class="highlightClass"
	>
		<!-- Label -->
		<span
			v-if="!['Check', 'Section Break', 'Column Break'].includes(props.fieldtype)"
			:class="[
				// mark field as mandatory
				props.reqd ? `after:content-['_*'] after:text-red-600` : ``,
				props.highlight
					? `block text-sm font-semibold leading-5 text-gray-900`
					: `block text-sm leading-5 text-gray-700`,
			]"
		>
			{{ props.label }}
		</span>
		<p v-if="props.highlight && props.hint" class="text-xs text-orange-800 -mt-1">
			{{ props.hint }}
		</p>

		<!-- Quick choices (e.g. frequent leave types) -->
		<div
			v-if="quickOptions.length"
			class="flex flex-wrap gap-1.5"
			:class="
				props.highlight && !modelValue
					? 'rounded-md ring-2 ring-orange-400 bg-orange-100/80 p-1.5'
					: ''
			"
		>
			<button
				v-for="opt in quickOptions"
				:key="opt.value"
				type="button"
				class="inline-flex items-center gap-1.5 max-w-full px-2.5 py-1.5 rounded-md border text-left transition-colors"
				:class="chipClass(opt)"
				:disabled="isReadOnly || isOptionDisabled(opt)"
				:title="isOptionDisabled(opt) ? __('No remaining leave') : undefined"
				@click="selectQuickOption(opt)"
			>
				<span class="text-xs font-semibold truncate">{{ opt.label }}</span>
				<!-- Leave chips carry a balance; shift chips do not. -->
				<span
					v-if="'remaining' in opt || opt.is_lwp"
					class="text-[11px] tabular-nums shrink-0 inline-flex items-center gap-0.5"
					:class="chipRemainingClass(opt)"
				>
					{{ remainingLabel(opt) }}
					<span
						v-if="opt.pending"
						class="text-[10px] font-normal opacity-80"
					>
						−{{ opt.pending }}
					</span>
				</span>
			</button>
		</div>

		<!-- Segmented choice: a short pick that has to be made, e.g. which half of a
		     half day. Big buttons in place of a dropdown, because there are only a
		     couple of answers and a dropdown hides them behind a tap. -->
		<div
			v-if="segmentOptions.length"
			class="grid gap-2"
			:class="props.highlight && !modelValue ? 'rounded-lg ring-2 ring-orange-400 bg-orange-100/80 p-1.5' : ''"
			:style="{ gridTemplateColumns: `repeat(${segmentOptions.length}, minmax(0, 1fr))` }"
		>
			<button
				v-for="opt in segmentOptions"
				:key="opt.value"
				type="button"
				class="flex flex-col items-center justify-center gap-0.5 rounded-lg border px-2 py-3 transition-colors"
				:class="
					modelValue === opt.value
						? 'border-red-500 bg-red-50 text-red-700 ring-1 ring-inset ring-red-500'
						: 'border-gray-200 bg-white text-gray-700 active:bg-gray-50'
				"
				:disabled="isReadOnly"
				@click="emit('update:modelValue', opt.value)"
			>
				<span class="text-sm font-semibold">{{ opt.label }}</span>
				<span v-if="opt.hint" class="text-xs tabular-nums opacity-70">{{ opt.hint }}</span>
			</button>
		</div>

		<!-- Select or Link field with predefined options -->
		<Autocomplete
			v-if="showSelectControl"
			:class="isReadOnly ? 'pointer-events-none' : ''"
			:placeholder="props.placeholder || __('Select {0}', [props.label])"
			:options="selectionList"
			:modelValue="modelValue"
			v-bind="$attrs"
			:disabled="isReadOnly"
			@update:modelValue="(v) => emit('update:modelValue', v?.value)"
		/>

		<!-- Link field -->
		<Link
			v-else-if="props.fieldtype === 'Link'"
			:doctype="props.options"
			:modelValue="modelValue"
			:filters="props.linkFilters"
			:disabled="isReadOnly"
			@update:modelValue="(v) => emit('update:modelValue', v)"
		/>

		<!-- Text -->
		<Input
			v-else-if="['Text Editor', 'Small Text', 'Text', 'Long Text'].includes(props.fieldtype)"
			type="textarea"
			:value="modelValue"
			:placeholder="props.placeholder || __('Enter {0}', [props.label])"
			@input="(v) => emit('update:modelValue', v)"
			@change="(v) => emit('change', v)"
			v-bind="$attrs"
			:disabled="isReadOnly"
			:class="props.highlight ? 'h-20 bg-white border-orange-300' : 'h-15'"
		/>

		<!-- Check -->
		<Input
			v-else-if="props.fieldtype === 'Check'"
			type="checkbox"
			:label="props.label"
			:value="modelValue"
			@input="(v) => emit('update:modelValue', v)"
			@change="(v) => emit('change', v)"
			v-bind="$attrs"
			:disabled="isReadOnly"
			class="rounded-sm text-gray-800"
		/>

		<!-- Data field -->
		<Input
			v-else-if="props.fieldtype === 'Data'"
			type="text"
			:value="modelValue"
			@input="(v) => emit('update:modelValue', v)"
			@change="(v) => emit('change', v)"
			v-bind="$attrs"
			:disabled="isReadOnly"
		/>

		<!-- Read only currency field -->
		<Input
			v-else-if="props.fieldtype === 'Currency' && isReadOnly"
			type="text"
			:value="modelValue"
			@input="(v) => emit('update:modelValue', v)"
			@change="(v) => emit('change', v)"
			v-bind="$attrs"
			:disabled="isReadOnly"
		/>

		<!-- Float/Int field -->
		<Input
			v-else-if="isNumberType"
			type="number"
			:value="modelValue"
			@input="(v) => emit('update:modelValue', v)"
			@change="(v) => emit('change', v)"
			v-bind="$attrs"
			:disabled="isReadOnly"
		/>

		<!-- Section Break -->
		<div
			v-else-if="props.fieldtype === 'Section Break'"
			:class="props.addSectionPadding ? 'mt-2' : ''"
		>
			<h2
				v-if="props.label"
				class="text-base font-semibold text-gray-800"
				:class="props.addSectionPadding ? 'pt-4' : ''"
			>
				{{ props.label }}
			</h2>
		</div>

		<!-- Date -->
		<!-- FIXME: default datepicker has poor UI -->
		<div v-else-if="props.fieldtype === 'Date'" class="flex flex-col gap-1 w-full">
			<div class="flex gap-2 items-center">
				<div class="flex-1 border rounded px-3 py-2 bg-gray-50 flex flex-col justify-center min-h-[42px] cursor-pointer" @click="showNepaliPicker = true">
					<div class="text-sm font-medium text-gray-900" v-if="modelValue">
						{{ formatNepaliDate(modelValue) }}
					</div>
					<div class="text-xs text-gray-500" v-if="modelValue">
						{{ dayjs(modelValue).format("dddd, DD-MM-YYYY") }}
					</div>
					<div class="text-xs text-gray-500" v-if="modelValue && showRelativeDays">
						{{ formatDaysFromToday(modelValue) }}
					</div>
					<div class="text-sm text-gray-400 italic" v-else-if="!modelValue">
						{{ __("Select Date") }}
					</div>
				</div>
				<Button 
					v-if="!isReadOnly"
					icon="calendar" 
					variant="outline" 
					class="h-10 w-10 flex-shrink-0 text-orange-600 border-orange-200 hover:bg-orange-50"
					@click="showNepaliPicker = true" 
				/>
			</div>
			<NepaliDatePickerDialog 
				v-model="showNepaliPicker" 
				:initialDate="modelValue"
				:showAttendanceIndicators="['Attendance Request', 'Leave Application'].includes(props.doctype)"
				@dateSelected="(val) => emit('update:modelValue', val)"
			/>
		</div>

		<!-- Time with known bounds: 15-minute slider plus typed entry -->
		<ShiftTimeSlider
			v-else-if="props.fieldtype === 'Time' && props.timeWindow"
			:modelValue="props.modelValue"
			:window="props.timeWindow"
			:readOnly="Boolean(isReadOnly)"
			@update:modelValue="(val) => emit('update:modelValue', val)"
		/>

		<!-- Time (Frappe Time is HH:MM:SS; native input uses HH:MM or HH:MM:SS) -->
		<input
			v-else-if="props.fieldtype === 'Time'"
			type="time"
			:step="props.noSeconds ? 60 : 1"
			class="form-input block w-full border-gray-400 rounded disabled:bg-gray-50 disabled:text-gray-700"
			:value="timeInputValue"
			:disabled="isReadOnly"
			:placeholder="__('Select {0}', [props.label])"
			@input="onTimeInput"
		/>

		<!-- Datetime -->
		<DateTimePicker
			v-else-if="props.fieldtype === 'Datetime'"
			:value="modelValue"
			:placeholder="`Select ${props.label}`"
			:formatter="(val) => dayjs(val).format('DD-MM-YYYY HH:mm:ss')"
			@update:modelValue="(v) => emit('update:modelValue', v)"
			v-bind="$attrs"
			:disabled="isReadOnly"
		/>

		<ErrorMessage :message="props.errorMessage" />
	</div>
</template>

<script setup>
import { Autocomplete, DateTimePicker, ErrorMessage, Input, Button } from "frappe-ui"
import ShiftTimeSlider from "@/components/ShiftTimeSlider.vue"
import { computed, onMounted, inject, ref } from "vue"

import Link from "@/components/Link.vue"
import NepaliDatePickerDialog from "@/components/NepaliDatePickerDialog.vue"
import { formatNepaliDate, formatDaysFromToday } from "@/utils/nepali_date"

const showNepaliPicker = ref(false)

const __ = inject("$translate")

const props = defineProps({
	fieldtype: String,
	fieldname: String,
	modelValue: [String, Number, Boolean, Array, Object],
	default: [String, Number, Boolean, Array, Object],
	label: String,
	options: [String, Array],
	linkFilters: Object,
	documentList: Array,
	readOnly: [Boolean, Number],
	reqd: [Boolean, Number],
	hidden: {
		type: [Boolean, Number],
		default: false,
	},
	errorMessage: String,
	minDate: String,
	maxDate: String,
	addSectionPadding: {
		type: Boolean,
		default: true,
	},
	doctype: String,
	quickOptions: {
		type: Array,
		default: () => [],
	},
	// [{ value, label, hint? }] -- renders buttons instead of the dropdown.
	segmentOptions: {
		type: Array,
		default: () => [],
	},
	placeholder: String,
	highlight: {
		type: Boolean,
		default: false,
	},
	hint: String,
	// { min, span, step } turns a Time field into a ShiftTimeSlider
	timeWindow: Object,
	// Time picked to the minute; seconds are saved as 00.
	noSeconds: Boolean,
})

const emit = defineEmits(["change", "update:modelValue"])
const dayjs = inject("$dayjs")

const showRelativeDays = computed(() => {
	if (props.doctype === "Employee") return false
	return !["date_of_birth", "date_of_joining"].includes(props.fieldname)
})

const showField = computed(() => {
	if (props.readOnly && !isLayoutField.value && !props.modelValue) return false

	return props.fieldtype !== "Table" && !props.hidden
})

const isNumberType = computed(() => {
	return ["Int", "Float", "Currency"].includes(props.fieldtype)
})

const isLayoutField = computed(() => {
	return ["Section Break", "Column Break"].includes(props.fieldtype)
})

const isReadOnly = computed(() => {
	return Boolean(props.readOnly)
})

const highlightClass = computed(() => {
	if (!props.highlight) return ""
	return "rounded-lg border border-orange-300 bg-orange-50 p-3"
})

const showSelectControl = computed(() => {
	if (props.segmentOptions?.length) return false
	const hasSelect = props.fieldtype === "Select"
	const hasList = Boolean(props.documentList)
	if (!hasSelect && !hasList) return false
	if (
		props.quickOptions?.length &&
		Array.isArray(props.documentList) &&
		props.documentList.length === 0
	) {
		return false
	}
	return true
})

const timeInputValue = computed(() => {
	const value = toTimeInputValue(props.modelValue)
	// Browsers draw a seconds box whenever the value carries seconds.
	return props.noSeconds ? value.slice(0, 5) : value
})

function toTimeInputValue(val) {
	if (val === null || val === undefined || val === "") return ""
	const s = String(val)
	const match = s.match(/(\d{1,2}):(\d{2})(?::(\d{2}))?/)
	if (!match) return ""
	const hours = String(match[1]).padStart(2, "0")
	const minutes = match[2]
	const seconds = match[3] || "00"
	return `${hours}:${minutes}:${seconds}`
}

function remainingLabel(opt) {
	if (opt?.is_lwp && (opt.remaining === null || opt.remaining === undefined || opt.remaining === "")) {
		return __("LWP")
	}
	if (opt?.remaining === null || opt?.remaining === undefined || opt?.remaining === "") {
		return "—"
	}
	return String(opt.remaining)
}

function isOptionDisabled(opt) {
	return Boolean(opt?.disabled)
}

function selectQuickOption(opt) {
	if (isReadOnly.value || isOptionDisabled(opt)) return
	emit("update:modelValue", opt.value)
}

function chipRemainingClass(opt) {
	if (isOptionDisabled(opt) && props.modelValue !== opt.value) return "text-gray-400"
	if (props.modelValue === opt.value) return "text-orange-50"
	return "text-orange-800"
}

function chipClass(opt) {
	if (isOptionDisabled(opt) && props.modelValue !== opt.value) {
		return "bg-gray-100 border-gray-200 text-gray-400 cursor-not-allowed opacity-60"
	}
	if (props.modelValue === opt.value) {
		return "bg-orange-600 border-orange-600 text-white shadow-sm"
	}
	if (props.highlight && !props.modelValue) {
		return "bg-white border-orange-400 text-orange-950"
	}
	return "bg-gray-50 border-gray-200 text-gray-800"
}

function onTimeInput(event) {
	const raw = event?.target?.value || ""
	if (!raw) {
		emit("update:modelValue", "")
		return
	}
	emit("update:modelValue", raw.length === 5 ? `${raw}:00` : raw)
}

const selectionList = computed(() => {
	if (props.fieldtype === "Link" && props.documentList) {
		return props.documentList
	} else if (props.fieldtype == "Select" && props.options) {
		const options = props.options.split("\n")
		return options.map((option) => ({
			label: __(option),
			value: option,
		}))
	}

	return []
})

function setDefaultValue() {
	// set default values
	if (props.modelValue) return

	if (props.default) {
		if (props.fieldtype === "Check") {
			emit("update:modelValue", props.default === "1" ? true : false)
		} else if (props.fieldtype === "Date" && props.default === "Today") {
			emit("update:modelValue", dayjs().format("YYYY-MM-DD"))
		} else if (isNumberType.value) {
			emit("update:modelValue", parseFloat(props.default || 0))
		} else {
			emit("update:modelValue", props.default)
		}
	} else if (props.fieldtype !== "Time") {
		props.fieldtype === "Check" ? emit("update:modelValue", false) : emit("update:modelValue", "")
	}
}

onMounted(() => {
	setDefaultValue()
})
</script>
