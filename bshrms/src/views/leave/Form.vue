<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<FormView
				v-if="formFields.data"
				doctype="Leave Application"
				v-model="leaveApplication"
				:isSubmittable="true"
				:fields="formFields.data"
				:id="props.id"
				:showAttachmentView="!isSplitLeave"
				:customSubmit="isSplitLeave"
				:submitLoading="splitCreate.loading"
				@validateForm="validateForm"
				@submitDocument="createSplitApplications"
			>
				<template #formHeader>
					<div
						v-if="isSplitLeave"
						class="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900"
					>
						<div class="font-semibold">
							{{
								__("{0} leave applications will be created", [leaveRanges.length])
							}}
						</div>
						<p class="mt-1 text-xs text-blue-800">
							{{
								__(
									"Same leave type, reason, and approver for each. Save creates drafts — not submitted."
								)
							}}
						</p>
						<ul class="mt-2 space-y-1 text-xs font-medium">
							<li
								v-for="(range, index) in leaveRanges"
								:key="range.from_date + '-' + range.to_date"
							>
								{{ __("Application {0}", [index + 1]) }}:
								{{ formatNepaliPeriod(range.from_date, range.to_date) }}
							</li>
						</ul>
						<p
							v-if="leaveApplication.total_leave_days"
							class="mt-2 text-xs text-blue-800"
						>
							{{
								__("{0} leave days in total", [leaveApplication.total_leave_days])
							}}
						</p>
					</div>
				</template>
			</FormView>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { createResource, toast, call } from "frappe-ui"
import { ref, watch, inject, onMounted, computed } from "vue"
import { useRoute, useRouter } from "vue-router"

import FormView from "@/components/FormView.vue"
import { decodeLeaveRanges } from "@/utils/leave_ranges"
import { formatNepaliPeriod } from "@/utils/nepali_date"
import { markAttendanceRefresh } from "@/utils/attendance_refresh"
import { myLeaves } from "@/data/leaves"

const SPLIT_HIDDEN_FIELDS = [
	"from_date",
	"to_date",
	"half_day",
	"half_day_date",
	"total_leave_days",
]

const dayjs = inject("$dayjs")
const __ = inject("$translate")
const today = dayjs().format("YYYY-MM-DD")
const route = useRoute()
const router = useRouter()

const props = defineProps({
	id: {
		type: String,
		required: false,
	},
})

const sessionEmployee = inject("$employee")
const currEmployee = ref(sessionEmployee.data.name)

// reactive object to store form data
const leaveApplication = ref({})
const leaveRanges = ref(props.id ? [] : decodeLeaveRanges(route.query?.ranges))
const isSplitLeave = computed(() => !props.id && leaveRanges.value.length > 1)

function applyPrefillFromQuery() {
	if (props.id) {
		leaveRanges.value = []
		return
	}
	const q = route.query || {}
	const decoded = decodeLeaveRanges(q.ranges)
	if (decoded.length) {
		leaveRanges.value = decoded
	} else if (q.prefill === "1" && q.from_date) {
		leaveRanges.value = [
			{
				from_date: String(q.from_date),
				to_date: String(q.to_date || q.from_date),
			},
		]
	}
	const first = leaveRanges.value[0]
	if (!first) return
	leaveApplication.value = {
		...leaveApplication.value,
		from_date: first.from_date,
		to_date: isSplitLeave.value ? first.to_date : String(q.to_date || first.to_date),
		employee: currEmployee.value,
		posting_date: today,
	}
	const singleDay = leaveRanges.value.length === 1 && first.from_date === first.to_date
	if (q.half_day === "1" && singleDay) {
		leaveApplication.value.half_day = 1
		leaveApplication.value.half_day_date = first.from_date
	}
}

onMounted(() => {
	applyPrefillFromQuery()
	hideSplitDateFields()
})

// get form fields
const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: "Leave Application" },
	transform(data) {
		let fields = getFilteredFields(data)

		return fields.map((field) => {
			if (field.fieldname === "half_day_date") field.hidden = true

			if (field.fieldname === "posting_date") field.default = today

			if (field.fieldname === "section_break_5") {
				field.label = __("Reason & Dates")
			}

			if (field.fieldname === "leave_type") {
				field.highlight = true
				field.hint = __("Required — tap a leave type")
			}

			if (field.fieldname === "description") {
				field.reqd = 1
				field.highlight = true
				field.placeholder = __("Why are you taking this leave?")
				field.hint = __("Required — this is sent to your approver")
			}

			if (isSplitLeave.value && SPLIT_HIDDEN_FIELDS.includes(field.fieldname)) {
				field.hidden = true
			}

			return field
		})
	},
	onSuccess(_data) {
		leaveApprovalDetails.reload()
		leaveTypes.reload()
		frequentLeaveTypes.reload()
		leaveTypeBalances.reload()
		hideSplitDateFields()
	},
})
formFields.reload()

const leaveApprovalDetails = createResource({
	url: "hrms.api.get_leave_approval_details",
	params: { employee: currEmployee.value },
	onSuccess(data) {
		setLeaveApprovers(data)
	},
})

const leaveTypes = createResource({
	url: "hrms.api.get_leave_types",
	params: {
		employee: currEmployee.value,
		date: today,
	},
	onSuccess(data) {
		setLeaveTypes(data)
	},
})

const frequentLeaveTypes = createResource({
	url: "nepal_hrms.api.leave_application.get_frequent_leave_types",
	params: {
		employee: currEmployee.value,
		date: today,
	},
	auto: false,
	onSuccess() {
		if (leaveTypes.data) setLeaveTypes(leaveTypes.data)
	},
})

const leaveTypeBalances = createResource({
	url: "nepal_hrms.api.leave_application.get_leave_type_balances",
	params: {
		employee: currEmployee.value,
		date: today,
	},
	auto: false,
	onSuccess() {
		if (leaveTypes.data) setLeaveTypes(leaveTypes.data)
	},
})

// form scripts
watch(
	() => leaveApplication.value.employee,
	(employee_id) => {
		if (props.id && employee_id !== currEmployee.value) {
			// if employee is not the current user, set form as read only
			setFormReadOnly()
		}
		currEmployee.value = employee_id
		const date = leaveApplication.value.from_date || today
		leaveTypes.fetch({ employee: currEmployee.value, date })
		frequentLeaveTypes.fetch({ employee: currEmployee.value, date })
		leaveTypeBalances.fetch({ employee: currEmployee.value, date })
		leaveApprovalDetails.fetch({ employee: currEmployee.value })
	}
)
watch(
	() => leaveApplication.value.leave_type,
	(leave_type) => {
		setLeaveBalance(leave_type)
		setTotalLeaveDays()
	}
)

watch(
	() => leaveApplication.value.half_day,
	(half_day) => setHalfDayDate(half_day)
)

watch(
	() => leaveApplication.value.half_day && leaveApplication.value.half_day_date,
	() => setTotalLeaveDays()
)

watch(
	() => leaveApplication.value.from_date,
	(from_date) => {
		if (!leaveApplication.value.to_date) {
			leaveApplication.value.to_date = from_date
		}

		// fetch leave types for the selected date
		leaveTypes.fetch({
			employee: currEmployee.value,
			date: from_date,
		})
		frequentLeaveTypes.fetch({
			employee: currEmployee.value,
			date: from_date,
		})
		leaveTypeBalances.fetch({
			employee: currEmployee.value,
			date: from_date,
		})
	}
)

watch(
	() => [leaveApplication.value.from_date, leaveApplication.value.to_date],
	([from_date, to_date]) => {
		validateDates(from_date, to_date)
		setHalfDayDateRange()
		setTotalLeaveDays()
	}
)

watch(
	() => leaveApplication.value.leave_approver,
  	(newApprover) => {
			const approverField = formFields.data.find(f => f.fieldname === "leave_approver")
			const selected = approverField?.documentList?.find(opt => opt.value === newApprover)
			leaveApplication.value.leave_approver_name = selected?.label?.split(" : ")[1] || ""
  }
)

// helper functions
function getFilteredFields(fields) {
	// reduce noise from the form view by excluding unnecessary fields
	// ex: employee and other details can be fetched from the session user
	const excludeFields = [
		"naming_series",
		"sb_other_details",
		"salary_slip",
		"letter_head",
	]

	const employeeFields = [
		"employee",
		"employee_name",
		"department",
		"company",
		"follow_via_email",
		"status",
		"posting_date",
	]

	if (!props.id) excludeFields.push(...employeeFields)

	return moveReasonBeforeDates(
		fields.filter((field) => !excludeFields.includes(field.fieldname))
	)
}

function moveReasonBeforeDates(fields) {
	const reasonIdx = fields.findIndex((field) => field.fieldname === "description")
	const fromIdx = fields.findIndex((field) => field.fieldname === "from_date")
	if (reasonIdx === -1 || fromIdx === -1 || reasonIdx === fromIdx) return fields

	const next = [...fields]
	const [reason] = next.splice(reasonIdx, 1)
	const insertAt = next.findIndex((field) => field.fieldname === "from_date")
	next.splice(insertAt, 0, reason)
	return next
}

function setFormReadOnly() {
	if (leaveApplication.value.leave_approver === sessionEmployee.data.user_id) return
	formFields.data.map((field) => (field.read_only = true))
}

function validateDates(from_date, to_date) {
	if (!(from_date && to_date) || isSplitLeave.value) return

	const error_message =
		from_date > to_date ? __("To Date cannot be before From Date") : ""

	const from_date_field = formFields.data?.find(
		(field) => field.fieldname === "from_date"
	)
	if (from_date_field) from_date_field.error_message = error_message
}

function hideSplitDateFields() {
	if (!isSplitLeave.value || !formFields.data) return
	for (const field of formFields.data) {
		if (SPLIT_HIDDEN_FIELDS.includes(field.fieldname)) {
			field.hidden = true
		}
	}
}

function setTotalLeaveDays() {
	if (isSplitLeave.value) {
		setSplitTotalLeaveDays()
		setLeaveBalance()
		return
	}
	if (!areValuesSet()) return

	const leaveDays = createResource({
		url: "hrms.hr.doctype.leave_application.leave_application.get_number_of_leave_days",
		params: {
			employee: currEmployee.value,
			leave_type: leaveApplication.value.leave_type,
			from_date: leaveApplication.value.from_date,
			to_date: leaveApplication.value.to_date,
			half_day: leaveApplication.value.half_day,
			half_day_date: leaveApplication.value.half_day_date,
		},
		onSuccess(data) {
			leaveApplication.value.total_leave_days = data
		},
	})
	leaveDays.reload()
	setLeaveBalance()
}

function setLeaveBalance() {
	if (!areValuesSet()) return

	const leaveBalance = createResource({
		url: "hrms.hr.doctype.leave_application.leave_application.get_leave_balance_on",
		params: {
			employee: currEmployee.value,
			date: leaveApplication.value.from_date,
			to_date: leaveApplication.value.to_date,
			leave_type: leaveApplication.value.leave_type,
			consider_all_leaves_in_the_allocation_period: 1,
		},
		onSuccess(data) {
			leaveApplication.value.leave_balance = data
		},
	})
	leaveBalance.reload()
}

function setHalfDayDate(half_day) {
	if (isSplitLeave.value) return
	const half_day_date = formFields.data?.find(
		(field) => field.fieldname === "half_day_date"
	)
	if (!half_day_date) return
	half_day_date.hidden = !half_day
	half_day_date.reqd = half_day

	if (!half_day) return

	if (leaveApplication.value.from_date === leaveApplication.value.to_date) {
		leaveApplication.value.half_day_date = leaveApplication.value.from_date
	} else {
		setHalfDayDateRange()
	}
}

function setHalfDayDateRange() {
	if (isSplitLeave.value) return
	const half_day_date = formFields.data?.find(
		(field) => field.fieldname === "half_day_date"
	)
	if (!half_day_date) return
	half_day_date.minDate = leaveApplication.value.from_date
	half_day_date.maxDate = leaveApplication.value.to_date
}

function setLeaveApprovers(data) {
	const leave_approver = formFields.data?.find(
		(field) => field.fieldname === "leave_approver"
	)
	leave_approver.reqd = data?.is_mandatory
	leave_approver.documentList = data?.department_approvers.map((approver) => ({
		label: approver.full_name
			? `${approver.name} : ${approver.full_name}`
			: approver.name,
		value: approver.name,
	}))
	if (!leaveApplication.value.leave_approver){
		leaveApplication.value.leave_approver = data?.leave_approver
		leaveApplication.value.leave_approver_name = data?.leave_approver_name
	}
	
}

function typeHasAvailableLeave(name) {
	const frequent = (frequentLeaveTypes.data || []).find((row) => row.leave_type === name)
	const row = frequent || leaveTypeBalances.data?.[name]
	if (!row) return true
	if (row.is_lwp) return true
	if (row.remaining === null || row.remaining === undefined || row.remaining === "") {
		return false
	}
	return Number(row.remaining) > 0
}

function setLeaveTypes(data) {
	const leave_type = formFields.data?.find(
		(field) => field.fieldname === "leave_type"
	)
	if (!leave_type) return

	const available = data || []
	const frequent = (frequentLeaveTypes.data || []).filter((row) =>
		available.includes(row.leave_type)
	)
	leave_type.quickOptions = frequent.map((row) => ({
		label: row.leave_type,
		value: row.leave_type,
		remaining: row.remaining,
		pending: row.pending,
		is_lwp: Boolean(row.is_lwp),
		disabled: !row.is_lwp && !(Number(row.remaining) > 0),
	}))
	const frequentNames = new Set(frequent.map((row) => row.leave_type))
	leave_type.placeholder = frequent.length ? __("Other leave types") : ""
	leave_type.documentList = available
		.filter((name) => !frequentNames.has(name))
		.filter((name) => typeHasAvailableLeave(name))
		.map((name) => ({
			label: name,
			value: name,
		}))

	const selected = leaveApplication.value.leave_type
	if (!props.id && selected && !typeHasAvailableLeave(selected)) {
		leaveApplication.value.leave_type = ""
	}
}

function areValuesSet() {
	return (
		leaveApplication.value.from_date &&
		leaveApplication.value.to_date &&
		leaveApplication.value.leave_type
	)
}

async function setSplitTotalLeaveDays() {
	if (!leaveApplication.value.leave_type || !leaveRanges.value.length) return
	let total = 0
	for (const range of leaveRanges.value) {
		try {
			const days = await call(
				"hrms.hr.doctype.leave_application.leave_application.get_number_of_leave_days",
				{
					employee: currEmployee.value,
					leave_type: leaveApplication.value.leave_type,
					from_date: range.from_date,
					to_date: range.to_date,
					half_day: 0,
				}
			)
			total += Number(days) || 0
		} catch (error) {
			console.warn("Leave days lookup failed", error)
		}
	}
	leaveApplication.value.total_leave_days = total
}

const splitCreate = createResource({
	url: "nepal_hrms.api.leave_application.create_leave_applications",
	auto: false,
	makeParams() {
		return {
			employee: currEmployee.value,
			leave_type: leaveApplication.value.leave_type,
			ranges: JSON.stringify(leaveRanges.value),
			description: leaveApplication.value.description,
			leave_approver: leaveApplication.value.leave_approver || "",
			leave_approver_name: leaveApplication.value.leave_approver_name || "",
		}
	},
	onSuccess(data) {
		myLeaves.reload()
		markAttendanceRefresh()
		toast({
			title: __("Success"),
			text: __("{0} leave applications created", [data?.count || leaveRanges.value.length]),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
		router.replace({ name: "AttendanceDashboard" })
	},
	onError(error) {
		toast({
			title: __("Error"),
			text:
				error?.messages?.[0] ||
				error?.message ||
				__("Could not create leave applications"),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	},
})

function remainingForSelectedType() {
	const type = leaveApplication.value.leave_type
	if (!type) return null
	if (/without\s*pay|\blwp\b/i.test(type)) return null
	const frequent = (frequentLeaveTypes.data || []).find((row) => row.leave_type === type)
	if (frequent?.is_lwp) return null
	if (frequent?.remaining != null && frequent.remaining !== "") {
		return Number(frequent.remaining)
	}
	if (
		leaveApplication.value.leave_balance != null &&
		leaveApplication.value.leave_balance !== ""
	) {
		return Number(leaveApplication.value.leave_balance)
	}
	return null
}

function createSplitApplications() {
	if (!isSplitLeave.value) return
	const remaining = remainingForSelectedType()
	const total = Number(leaveApplication.value.total_leave_days || 0)
	if (remaining != null && total > remaining) {
		toast({
			title: __("Insufficient Balance"),
			text: __(
				"Insufficient leave balance for Leave Type {0}. {1} day(s) selected, {2} remaining.",
				[leaveApplication.value.leave_type, total, remaining]
			),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
		return
	}
	splitCreate.submit()
}

function validateForm() {
	setHalfDayDate(leaveApplication.value.half_day)
	leaveApplication.value.employee = currEmployee.value
}
</script>
