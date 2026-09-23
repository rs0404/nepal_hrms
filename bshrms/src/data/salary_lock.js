import { computed, reactive } from "vue"
import { call, createResource } from "frappe-ui"

// Salary figures stay masked until the employee types the value of the
// Employee field they chose (see nepal_hrms/api/salary_privacy.py). An unlock
// lasts a few minutes and lives in memory only: reloading the app locks again.

export const SALARY_MASK = "xxxxx"
const UNLOCK_MS = 5 * 60 * 1000

const state = reactive({ unlockedUntil: 0, now: Date.now() })
setInterval(() => (state.now = Date.now()), 10 * 1000)

export const salaryPrivacy = createResource({
	url: "nepal_hrms.api.salary_privacy.get_salary_privacy",
	auto: true,
})

/** True while amounts must be hidden. Locked until the setting has loaded. */
export const salaryLocked = computed(() => {
	if (!salaryPrivacy.data) return true
	if (!salaryPrivacy.data.enabled) return false
	return state.now >= state.unlockedUntil
})

export async function unlockSalary(value) {
	const result = await call("nepal_hrms.api.salary_privacy.verify_salary_unlock", { value })
	if (result?.ok) {
		state.unlockedUntil = Date.now() + UNLOCK_MS
		state.now = Date.now()
	}
	return Boolean(result?.ok)
}

export function lockSalary() {
	state.unlockedUntil = 0
	state.now = Date.now()
}

/** The amount, or the mask while locked. */
export function maskedAmount(formatted) {
	return salaryLocked.value ? SALARY_MASK : formatted
}
