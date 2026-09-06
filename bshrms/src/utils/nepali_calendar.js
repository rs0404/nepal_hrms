const DATE_LIB = "/assets/nepal_compliance/js/nepali_date_lib.js?v=20260812e"
const CALENDAR_LIB = "/assets/nepal_compliance/js/nepali_calendar_lib.js?v=20260901a"
const REACT = "https://unpkg.com/react@18.3.1/umd/react.production.min.js"
const REACT_DOM = "https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js"

function loadScript(src) {
	const path = src.split("?")[0]
	if ([...document.scripts].some((script) => script.src.includes(path))) {
		return Promise.resolve()
	}
	return new Promise((resolve, reject) => {
		const el = document.createElement("script")
		el.src = src
		el.async = true
		el.onload = resolve
		el.onerror = () => reject(new Error(`Failed to load ${src}`))
		document.head.appendChild(el)
	})
}

export function ensureNepaliDateLib() {
	if (window.NepaliDateLib) return Promise.resolve()
	return loadScript(DATE_LIB)
}

let calendarPromise = null
export function ensureNepaliCalendar() {
	if (window.NepaliCalendarLib) return Promise.resolve()
	if (!calendarPromise) {
		calendarPromise = (async () => {
			await ensureNepaliDateLib()
			if (!window.React) await loadScript(REACT)
			if (!window.ReactDOM) await loadScript(REACT_DOM)
			await loadScript(CALENDAR_LIB)
		})()
	}
	return calendarPromise
}
