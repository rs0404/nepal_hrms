<template>
	<div class="flex flex-col gap-2 w-full">
		<div class="text-gray-600 text-base">
			{{ __("Comments") }}
			<span v-if="comments.data?.length" class="text-gray-400">({{ comments.data.length }})</span>
		</div>

		<div v-if="comments.data?.length" class="flex flex-col gap-2">
			<div
				v-for="c in comments.data"
				:key="c.name"
				class="flex gap-2.5 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5"
			>
				<EmployeeAvatar :userID="c.user" size="md" />
				<div class="flex min-w-0 flex-col gap-0.5">
					<div class="flex flex-wrap items-baseline gap-x-2">
						<span class="text-sm font-medium text-gray-900">{{ c.full_name }}</span>
						<span class="text-xs text-gray-500">{{ dayjs(c.creation).fromNow() }}</span>
					</div>
					<div class="whitespace-pre-line break-words text-sm text-gray-800">
						<template v-for="(p, i) in c.parts" :key="i">
							<span v-if="p.mention" class="rounded bg-blue-50 px-0.5 font-medium text-blue-700">@{{ p.mention }}</span>
							<template v-else>{{ p.text }}</template>
						</template>
					</div>
				</div>
			</div>
		</div>

		<!-- New comment. "@" opens a picker of employees to tag. -->
		<div class="relative">
			<textarea
				ref="input"
				v-model="draft"
				rows="2"
				class="w-full rounded-lg border border-gray-300 bg-white p-3 pr-12 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-400"
				:placeholder="__('Add a comment. Type @ to tag someone')"
				@input="onInput"
				@click="onInput"
				@keydown="onKeydown"
			/>
			<button
				type="button"
				class="absolute bottom-3 right-2 flex h-8 w-8 items-center justify-center rounded-full bg-gray-900 text-white disabled:bg-gray-300"
				:disabled="!draft.trim() || posting"
				:aria-label="__('Post comment')"
				@click="post"
			>
				<FeatherIcon :name="posting ? 'loader' : 'send'" class="h-4 w-4" />
			</button>

			<div
				v-if="suggestions.length"
				class="absolute bottom-full left-0 z-20 mb-1 max-h-56 w-full overflow-auto rounded-lg border border-gray-200 bg-white shadow-lg"
			>
				<button
					v-for="(e, i) in suggestions"
					:key="e.user_id"
					type="button"
					class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm"
					:class="i === activeIndex ? 'bg-gray-100' : ''"
					@mousedown.prevent="pick(e)"
				>
					<EmployeeAvatar :employeeID="e.name" size="sm" />
					<span class="truncate text-gray-900">{{ e.employee_name }}</span>
					<span v-if="e.designation" class="truncate text-xs text-gray-500">{{ e.designation }}</span>
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { call, createResource, FeatherIcon, toast } from "frappe-ui"

import EmployeeAvatar from "@/components/EmployeeAvatar.vue"
import { employees } from "@/data/employees"
import dayjs from "@/utils/dayjs"

const __ = inject("$translate")
const props = defineProps({
	doctype: { type: String, required: true },
	name: { type: String, required: true },
})

const emit = defineEmits(["count"])

const comments = createResource({
	url: "nepal_hrms.api.request_comments.get_request_comments",
	params: { doctype: props.doctype, name: props.name },
	auto: true,
	// Keeps the list row's comment badge in step with what is shown here.
	onSuccess: (data) => emit("count", data?.length || 0),
})

if (!employees.data && !employees.loading) employees.fetch()

const input = ref(null)
const draft = ref("")
const posting = ref(false)
// Tags picked so far; only those still present as "@Name" in the text are sent.
const tagged = ref([])
// The "@query" being typed: where it starts and what follows the @.
const query = ref(null)
const activeIndex = ref(0)

const suggestions = computed(() => {
	if (query.value === null) return []
	const q = query.value.text.toLowerCase()
	return (employees.data || [])
		.filter((e) => e.isActive && e.user_id && e.employee_name?.toLowerCase().includes(q))
		.sort((a, b) => {
			const ai = a.employee_name.toLowerCase().startsWith(q) ? 0 : 1
			const bi = b.employee_name.toLowerCase().startsWith(q) ? 0 : 1
			return ai - bi || a.employee_name.localeCompare(b.employee_name)
		})
		.slice(0, 8)
})

function onInput() {
	const el = input.value
	const before = draft.value.slice(0, el?.selectionStart ?? draft.value.length)
	// An @ at the start or after a space, followed by up to three words.
	const match = before.match(/(?:^|\s)@([^\s@]*(?: [^\s@]*){0,2})$/)
	query.value = match ? { start: before.length - match[1].length - 1, text: match[1] } : null
	activeIndex.value = 0
}

function onKeydown(event) {
	if (!suggestions.value.length) return
	if (event.key === "ArrowDown" || event.key === "ArrowUp") {
		event.preventDefault()
		const step = event.key === "ArrowDown" ? 1 : -1
		const n = suggestions.value.length
		activeIndex.value = (activeIndex.value + step + n) % n
	} else if (event.key === "Enter" || event.key === "Tab") {
		event.preventDefault()
		pick(suggestions.value[activeIndex.value])
	} else if (event.key === "Escape") {
		query.value = null
	}
}

function pick(employee) {
	const el = input.value
	const caret = el?.selectionStart ?? draft.value.length
	const label = `@${employee.employee_name} `
	const start = query.value.start
	draft.value = draft.value.slice(0, start) + label + draft.value.slice(caret)
	if (!tagged.value.some((t) => t.user === employee.user_id)) {
		tagged.value.push({ user: employee.user_id, name: employee.employee_name })
	}
	query.value = null
	const pos = start + label.length
	requestAnimationFrame(() => {
		el?.focus()
		el?.setSelectionRange(pos, pos)
	})
}

async function post() {
	const content = draft.value.trim()
	if (!content) return
	posting.value = true
	try {
		await call("nepal_hrms.api.request_comments.add_request_comment", {
			doctype: props.doctype,
			name: props.name,
			content,
			mentions: tagged.value.filter((t) => content.includes(`@${t.name}`)),
		})
		draft.value = ""
		tagged.value = []
		comments.reload()
	} catch (error) {
		toast({
			title: __("Error"),
			text: error?.messages?.join?.(" ") || error?.message || __("Could not post the comment"),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	} finally {
		posting.value = false
	}
}
</script>
