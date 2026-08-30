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

export function formatNepaliPeriod(fromDate, toDate) {
	if (!fromDate) return ""
	const fromBS = formatNepaliDate(fromDate)
	if (!toDate || fromDate === toDate) return fromBS
	const toBS = formatNepaliDate(toDate)
	return `${fromBS} to ${toBS}`
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
