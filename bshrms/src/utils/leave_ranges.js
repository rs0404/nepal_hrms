/** Group YYYY-MM-DD dates into contiguous calendar-day stretches. */

function nextDay(iso) {
	const d = new Date(`${String(iso).slice(0, 10)}T12:00:00`)
	d.setDate(d.getDate() + 1)
	const y = d.getFullYear()
	const m = String(d.getMonth() + 1).padStart(2, "0")
	const day = String(d.getDate()).padStart(2, "0")
	return `${y}-${m}-${day}`
}

export function groupContiguousDates(dates) {
	const sorted = [...new Set((dates || []).filter(Boolean))].sort()
	const ranges = []
	for (const date of sorted) {
		const last = ranges[ranges.length - 1]
		if (last && nextDay(last.to_date) === date) {
			last.to_date = date
		} else {
			ranges.push({ from_date: date, to_date: date })
		}
	}
	return ranges
}

export function encodeLeaveRanges(ranges) {
	return (ranges || [])
		.map((r) => `${r.from_date}:${r.to_date || r.from_date}`)
		.join(",")
}

export function decodeLeaveRanges(value) {
	if (!value) return []
	const raw = Array.isArray(value) ? value.join(",") : String(value)
	return raw
		.split(",")
		.map((part) => {
			const [from_date, to_date] = part.split(":")
			if (!from_date) return null
			return { from_date, to_date: to_date || from_date }
		})
		.filter(Boolean)
}
