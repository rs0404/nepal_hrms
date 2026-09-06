export function syncCsrfFromCookie() {
	try {
		const cookies = new URLSearchParams(document.cookie.split("; ").join("&"))
		const token = cookies.get("csrf_token")
		if (token) window.csrf_token = token
	} catch {
		/* ignore */
	}
}

export async function waitForResourceData(resource, timeoutMs = 80) {
	if (resource?.data) return true
	const started = Date.now()
	while (Date.now() - started < timeoutMs) {
		await new Promise((resolve) => setTimeout(resolve, 8))
		if (resource?.data) return true
	}
	return Boolean(resource?.data)
}

export function identityMatches(userResource, employeeResource) {
	return Boolean(
		userResource?.data?.name &&
			employeeResource?.data?.user_id &&
			employeeResource.data.user_id === userResource.data.name
	)
}
