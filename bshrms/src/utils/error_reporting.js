// Send errors that happen in the app itself to Error Log.
//
// Server errors are not sent: the after_request hook in
// nepal_hrms.api.error_capture already logs every one the app is shown.
// What is left is the app's own failures -- a component that crashed, a
// promise nobody caught -- which otherwise die in the phone's console.
import { call } from "frappe-ui"

const MAX_PER_SESSION = 20
const seen = new Set()

function cameFromServer(error) {
	return Boolean(error?.exc_type || error?.messages || error?.exception)
}

export function reportClientError(error, context = "") {
	try {
		if (!error || cameFromServer(error)) return
		const message = String(error?.message || error)
		const key = `${message}|${context}`
		if (seen.has(key) || seen.size >= MAX_PER_SESSION) return
		seen.add(key)
		call("nepal_hrms.api.error_capture.log_client_error", {
			message,
			stack: error?.stack || "",
			url: window.location.href,
			context,
		}).catch(() => {})
	} catch (e) {
		// Reporting must never raise an error of its own.
	}
}

export function installErrorReporting(app) {
	const previous = app.config.errorHandler
	app.config.errorHandler = (error, instance, info) => {
		reportClientError(error, `vue: ${info}`)
		if (previous) previous(error, instance, info)
		else console.error(error)
	}
	window.addEventListener("error", (event) =>
		reportClientError(event.error || event.message, "window error")
	)
	window.addEventListener("unhandledrejection", (event) =>
		reportClientError(event.reason, "unhandled promise")
	)
}
