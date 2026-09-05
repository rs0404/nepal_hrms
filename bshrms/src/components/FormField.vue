<template>
	<div v-if="showField" class="flex flex-col gap-1.5">
		<!-- Label -->
		<span
			v-if="!['Check', 'Section Break', 'Column Break'].includes(props.fieldtype)"
			:class="[
				// mark field as mandatory
				props.reqd ? `after:content-['_*'] after:text-red-600` : ``,
				`block text-sm leading-5 text-gray-700`,
			]"
		>
			{{ props.label }}
		</span>

		<!-- Select or Link field with predefined options -->
		<Autocomplete
			v-if="props.fieldtype === 'Select' || props.documentList"
			:class="isReadOnly ? 'pointer-events-none' : ''"
			:placeholder="__('Select {0}', [props.label])"
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
			:placeholder="__('Enter {0}', [props.label])"
			@input="(v) => emit('update:modelValue', v)"
			@change="(v) => emit('change', v)"
			v-bind="$attrs"
			:disabled="isReadOnly"
			class="h-15"
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
						{{ dayjs(modelValue).format("DD-MM-YYYY") }}
					</div>
					<div class="text-sm text-gray-400 italic" v-else>
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

		<!-- Time (Frappe Time is HH:MM:SS; native input uses HH:MM or HH:MM:SS) -->
		<input
			v-else-if="props.fieldtype === 'Time'"
			type="time"
			step="1"
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
import { computed, onMounted, inject, ref } from "vue"

import Link from "@/components/Link.vue"
import NepaliDatePickerDialog from "@/components/NepaliDatePickerDialog.vue"
import { formatNepaliDate } from "@/utils/nepali_date"

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
})

const emit = defineEmits(["change", "update:modelValue"])
const dayjs = inject("$dayjs")

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

const timeInputValue = computed(() => toTimeInputValue(props.modelValue))

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
