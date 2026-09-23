<template>
	<ListItem>
		<template #left>
			<SalaryIcon class="h-5 w-5 text-gray-500" />
			<div class="flex flex-col items-start gap-1.5">
				<div class="text-base font-normal text-gray-800" :lang="bsTitle ? 'ne' : undefined">
					{{ title }}
				</div>
				<div v-if="bsDates" class="text-xs font-medium text-gray-700" lang="ne">
					{{ bsDates }}
				</div>
				<div class="text-xs font-normal text-gray-500">
					<span v-if="adPeriod">{{ adPeriod }}</span>
					<span v-if="adPeriod && doc?.gross_pay" class="whitespace-pre"> &middot; </span>
					<span v-if="doc?.gross_pay">
						{{
							__("{0}: {1}", [
								__("Gross Pay"),
								maskedAmount(formatCurrency(doc.gross_pay, doc.currency)),
							])
						}}
					</span>
				</div>
			</div>
		</template>
		<template #right>
			<span v-if="doc?.net_pay" class="text-gray-700 font-normal rounded text-base">
				{{ maskedAmount(formatCurrency(doc.net_pay, doc.currency)) }}
			</span>
			<FeatherIcon name="chevron-right" class="h-5 w-5 text-gray-500" />
		</template>
	</ListItem>
</template>

<script setup>
import { computed, inject } from "vue"
import { FeatherIcon } from "frappe-ui"

import ListItem from "@/components/ListItem.vue"
import SalaryIcon from "@/components/icons/SalaryIcon.vue"

import { formatCurrency } from "@/utils/formatters"
import { maskedAmount } from "@/data/salary_lock"
import {
	formatNepaliDatePeriodNe,
	formatNepaliMonthPeriodNe,
	formatNepaliMonthYearPeriod,
} from "@/utils/nepali_date"

const dayjs = inject("$dayjs")

const props = defineProps({
	doc: {
		type: Object,
	},
})

// The BS months in Nepali lead; the exact BS dates follow, then the AD months.
const bsTitle = computed(() => formatNepaliMonthPeriodNe(props.doc.start_date, props.doc.end_date))
const bsDates = computed(() => formatNepaliDatePeriodNe(props.doc.start_date, props.doc.end_date))

const title = computed(() => {
	if (bsTitle.value) return bsTitle.value
	const bs = formatNepaliMonthYearPeriod(props.doc.start_date, props.doc.end_date)
	if (bs) return bs
	return adPeriod.value
})

const adPeriod = computed(() => {
	if (dayjs(props.doc.start_date).isSame(props.doc.end_date, "month")) {
		return dayjs(props.doc.start_date).format("MMM YYYY")
	}
	return `${dayjs(props.doc.start_date).format("MMM YYYY")} – ${dayjs(
		props.doc.end_date
	).format("MMM YYYY")}`
})
</script>
