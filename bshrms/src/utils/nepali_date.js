export function formatNepaliDate(adDate) {
	if (!adDate || !window.NepaliDateLib) return adDate
	try {
		const nd = window.NepaliDateLib.NepaliDate.fromAD(new Date(adDate))
		return nd.format({ format: "YYYY-MM-DD", calendar: "BS" })
	} catch (e) {
		console.error("Nepali Date Conversion Error:", e)
		return adDate
	}
}

/** Calendar-day label relative to today. */
export function formatDaysFromToday(adDate) {
	if (!adDate) return ""
	const target = new Date(`${String(adDate).slice(0, 10)}T12:00:00`)
	if (Number.isNaN(target.getTime())) return ""
	const now = new Date()
	const today = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12)
	const diff = Math.round((target.getTime() - today.getTime()) / 86400000)
	if (diff === 0) return "today"
	if (diff === 1) return "after 1 day"
	if (diff > 1) return `after ${diff} days`
	if (diff === -1) return "1 day ago"
	return `${Math.abs(diff)} days ago`
}

export function formatNepaliPeriod(fromDate, toDate) {
	if (!fromDate) return ""
	const fromBS = formatNepaliDate(fromDate)
	if (!toDate || fromDate === toDate) return fromBS
	const toBS = formatNepaliDate(toDate)
	return `${fromBS} to ${toBS}`
}

/** BS month + year, e.g. "Shrawan 2083". */
export function formatNepaliMonthYear(adDate) {
	if (!adDate || !window.NepaliDateLib) return ""
	try {
		const nd = window.NepaliDateLib.NepaliDate.fromAD(new Date(adDate))
		const months = window.NepaliDateLib.MONTH_NAMES_EN_BS
		const monthName = months?.[nd.monthIndex]
		if (monthName && nd.year) return `${monthName} ${nd.year}`
		return nd.format({ format: "YYYY-MM", calendar: "BS" })
	} catch (e) {
		console.error("Nepali month/year conversion error:", e)
		return ""
	}
}

/** BS month range, collapsing to one label when start and end are the same month. */
export function formatNepaliMonthYearPeriod(fromDate, toDate) {
	const from = formatNepaliMonthYear(fromDate)
	if (!from) return ""
	const to = formatNepaliMonthYear(toDate)
	if (!to || to === from) return from
	return `${from} – ${to}`
}

/** BS { year, month } (month 1-based) for an AD date, or null. */
export function getBsYearMonth(adDate) {
	const NepaliDate = window.NepaliDateLib?.NepaliDate
	if (!NepaliDate || !adDate) return null
	try {
		const nd = NepaliDate.fromAD(adDate instanceof Date ? adDate : new Date(adDate))
		return { year: nd.year, month: nd.monthIndex + 1 }
	} catch (e) {
		console.error("BS year/month conversion error:", e)
		return null
	}
}

/** AD YYYY-MM-DD bounds for the BS month containing `refDate` (default: today). */
export function getBsMonthAdRange(refDate = new Date()) {
	const NepaliDate = window.NepaliDateLib?.NepaliDate
	if (!NepaliDate) return null
	try {
		const today =
			refDate instanceof Date
				? NepaliDate.fromAD(refDate)
				: NepaliDate.fromAD(new Date(refDate))
		const first = new NepaliDate(today.year, today.monthIndex, 1)
		let last = first
		for (let d = 32; d >= 28; d--) {
			try {
				const candidate = new NepaliDate(today.year, today.monthIndex, d)
				if (candidate.monthIndex === today.monthIndex) {
					last = candidate
					break
				}
			} catch {
				/* day out of range */
			}
		}
		return {
			from_date: first.format({ format: "YYYY-MM-DD", calendar: "AD" }),
			to_date: last.format({ format: "YYYY-MM-DD", calendar: "AD" }),
		}
	} catch (e) {
		console.error("BS month range error:", e)
		return null
	}
}

/** Format AD datetime / time string as HH:MM:SS for CNR time fields. */
export function timeFromDatetime(dt) {
	if (!dt) return null
	const s = String(dt)
	const part = s.includes("T") ? s.split("T")[1] : s.split(" ").pop()
	return (part || "").slice(0, 8) || null
}

/** BS date with the English month name, e.g. "7 Asoj 2083". Falls back to the AD date. */
export function formatNepaliDateLong(adDate, { withYear = true } = {}) {
	if (!adDate || !window.NepaliDateLib) return adDate || ""
	try {
		const nd = window.NepaliDateLib.NepaliDate.fromAD(new Date(`${String(adDate).slice(0, 10)}T12:00:00`))
		const month = window.NepaliDateLib.MONTH_NAMES_EN_BS?.[nd.monthIndex]
		if (!month) return formatNepaliDate(adDate)
		return withYear ? `${nd.day} ${month} ${nd.year}` : `${nd.day} ${month}`
	} catch (e) {
		console.error("Nepali date conversion error:", e)
		return adDate
	}
}

const AD_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

/** AD date, e.g. "23 Sep 2026". Months spelled here: some locales print "Sept". */
export function formatEnglishDate(adDate, { withYear = true } = {}) {
	if (!adDate) return ""
	const date = new Date(`${String(adDate).slice(0, 10)}T12:00:00`)
	if (Number.isNaN(date.getTime())) return String(adDate)
	const dayMonth = `${date.getDate()} ${AD_MONTHS[date.getMonth()]}`
	return withYear ? `${dayMonth} ${date.getFullYear()}` : dayMonth
}

/** Both calendars, BS first: "7 Asoj 2083 · 23 Sep 2026". */
export function formatDualDate(adDate) {
	if (!adDate) return ""
	return `${formatNepaliDateLong(adDate)} · ${formatEnglishDate(adDate)}`
}

/** A date range in both calendars; a single day collapses to formatDualDate. */
export function formatDualPeriod(fromDate, toDate) {
	if (!fromDate) return ""
	if (!toDate || String(fromDate).slice(0, 10) === String(toDate).slice(0, 10)) {
		return formatDualDate(fromDate)
	}
	const bs = `${formatNepaliDateLong(fromDate, { withYear: false })} – ${formatNepaliDateLong(toDate)}`
	const ad = `${formatEnglishDate(fromDate, { withYear: false })} – ${formatEnglishDate(toDate)}`
	return `${bs} · ${ad}`
}

/** "10:13:36" -> "10:13". */
export function formatShortTime(value) {
	const match = String(value || "").match(/(\d{1,2}):(\d{2})/)
	return match ? `${match[1].padStart(2, "0")}:${match[2]}` : ""
}
