<template>
	<div class="flex flex-col gap-2">
		<div class="flex items-center justify-between gap-3">
			<div class="flex flex-col">
				<span class="text-lg font-semibold tabular-nums" :class="zone.text">
					{{ selectedLabel }}
				</span>
				<span v-if="zone.hint" class="text-xs" :class="zone.text">{{ zone.hint }}</span>
			</div>
			<!-- Typed entry for a time between the slider's 15-minute stops. No seconds. -->
			<input
				type="time"
				class="form-input w-32 border-gray-400 rounded disabled:bg-gray-50 disabled:text-gray-700"
				:value="hhmm"
				:disabled="readOnly"
				:aria-label="__('Type a time')"
				@change="onTyped"
			/>
		</div>

		<div class="relative">
			<input
				type="range"
				class="shift-slider w-full"
				:style="{ '--track': trackGradient, '--thumb': zone.thumb }"
				:min="0"
				:max="props.window.span"
				:step="props.window.step"
				:value="sliderOffset"
				:disabled="readOnly"
				@input="onSlide"
			/>
			<!-- One tick per stop. Inset by the thumb radius so ticks sit under its centre. -->
			<div class="relative mx-[10px] h-5">
				<div
					v-for="tick in ticks"
					:key="tick.offset"
					class="absolute top-0 flex -translate-x-1/2 flex-col items-center"
					:style="{ left: `${(tick.offset / props.window.span) * 100}%` }"
				>
					<span
						class="h-1.5 w-px"
						:class="tick.offset === sliderOffset && selected !== null ? 'bg-gray-900' : 'bg-gray-400'"
					/>
					<span
						v-if="tick.label"
						class="mt-0.5 text-[10px] leading-none tabular-nums"
						:class="tick.offset === sliderOffset && selected !== null ? 'font-semibold text-gray-900' : 'text-gray-500'"
					>
						{{ tick.label }}
					</span>
				</div>
			</div>
		</div>

		<div v-if="props.window.grace" class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
			<span class="flex items-center gap-1.5">
				<span class="h-2 w-2 rounded-full bg-green-500" />{{ __("Grace, no deduction") }}
			</span>
			<span class="flex items-center gap-1.5">
				<span class="h-2 w-2 rounded-full bg-amber-500" />{{ __("Counts toward the monthly pool") }}
			</span>
		</div>

		<p v-if="outOfRange" class="text-xs text-red-600">
			{{ __("{0} is outside {1} – {2}. The application will be refused.", [hhmm, format(minMinutes), format(minMinutes + props.window.span)]) }}
		</p>
	</div>
</template>

<script setup>
import { computed, inject } from "vue"

const __ = inject("$translate")

const props = defineProps({
	modelValue: [String, null],
	// { min: "HH:MM", span, step, grace (minutes), kind: "late" | "early" } from get_cnr_time_window
	window: { type: Object, required: true },
	readOnly: { type: Boolean, default: false },
})
const emit = defineEmits(["update:modelValue"])

const DAY = 24 * 60
// Hex, not Tailwind classes: these go into an inline gradient.
const GREEN = "#22c55e"
const AMBER = "#f59e0b"
const MAX_LABELS = 7

function toMinutes(value) {
	const match = String(value || "").match(/(\d{1,2}):(\d{2})/)
	return match ? Number(match[1]) * 60 + Number(match[2]) : null
}

function format(minutes) {
	const m = ((minutes % DAY) + DAY) % DAY
	return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`
}

const minMinutes = computed(() => toMinutes(props.window.min) ?? 0)
const selected = computed(() => toMinutes(props.modelValue))
const hhmm = computed(() => (selected.value === null ? "" : format(selected.value)))
const selectedLabel = computed(() => hhmm.value || __("Slide or type a time"))

// Offset from the window start; modulo a day so a window that crosses
// midnight (a night shift) still lines up.
const offset = computed(() =>
	selected.value === null ? null : (selected.value - minMinutes.value + DAY) % DAY
)
const outOfRange = computed(() => offset.value !== null && offset.value > props.window.span)
const sliderOffset = computed(() =>
	offset.value === null || outOfRange.value ? 0 : offset.value
)

// Where grace ends, as an offset into the window. Late entry: grace is at the
// start (just after shift start). Early exit: at the end (just before shift end).
const graceEdge = computed(() => {
	const { span, grace = 0, kind } = props.window
	return kind === "early" ? span - grace : grace
})

function inGrace(value) {
	return props.window.kind === "early" ? value >= graceEdge.value : value <= graceEdge.value
}

const trackGradient = computed(() => {
	const { span, grace } = props.window
	if (!grace) return AMBER
	const edge = `${(graceEdge.value / span) * 100}%`
	const [first, second] = props.window.kind === "early" ? [AMBER, GREEN] : [GREEN, AMBER]
	return `linear-gradient(to right, ${first} 0 ${edge}, ${second} ${edge} 100%)`
})

const zone = computed(() => {
	if (selected.value === null) return { text: "text-gray-500", thumb: "#6b7280", hint: "" }
	if (outOfRange.value) return { text: "text-red-600", thumb: "#dc2626", hint: "" }
	if (props.window.grace && inGrace(offset.value)) {
		return { text: "text-green-700", thumb: GREEN, hint: __("Within grace") }
	}
	return { text: "text-amber-700", thumb: AMBER, hint: __("Needs approval") }
})

const ticks = computed(() => {
	const { span, step } = props.window
	const count = Math.floor(span / step)
	// Label every stop when they fit, otherwise every nth, always the ends.
	const every = Math.max(1, Math.ceil((count + 1) / MAX_LABELS))
	const list = []
	for (let i = 0; i <= count; i++) {
		const tickOffset = i * step
		const label = i % every === 0 || i === count ? format(minMinutes.value + tickOffset) : ""
		list.push({ offset: tickOffset, label })
	}
	return list
})

function emitMinutes(minutes) {
	emit("update:modelValue", `${format(minutes)}:00`)
}

function onSlide(event) {
	emitMinutes(minMinutes.value + Number(event.target.value))
}

function onTyped(event) {
	const minutes = toMinutes(event.target.value)
	if (minutes === null) emit("update:modelValue", "")
	else emitMinutes(minutes)
}
</script>

<style scoped>
.shift-slider {
	-webkit-appearance: none;
	appearance: none;
	height: 20px;
	background: transparent;
}
.shift-slider:disabled {
	opacity: 0.6;
}
.shift-slider::-webkit-slider-runnable-track {
	height: 6px;
	border-radius: 9999px;
	background: var(--track);
}
.shift-slider::-moz-range-track {
	height: 6px;
	border-radius: 9999px;
	background: var(--track);
}
.shift-slider::-webkit-slider-thumb {
	-webkit-appearance: none;
	width: 20px;
	height: 20px;
	margin-top: -7px;
	border-radius: 9999px;
	background: var(--thumb);
	border: 3px solid #fff;
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
}
.shift-slider::-moz-range-thumb {
	width: 14px;
	height: 14px;
	border-radius: 9999px;
	background: var(--thumb);
	border: 3px solid #fff;
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
}
</style>
