const KEY = "bshrms:refresh-attendance"

export function markAttendanceRefresh() {
	try {
		sessionStorage.setItem(KEY, String(Date.now()))
	} catch {
		/* ignore */
	}
}

export function consumeAttendanceRefresh() {
	try {
		if (!sessionStorage.getItem(KEY)) return false
		sessionStorage.removeItem(KEY)
		return true
	} catch {
		return false
	}
}
