// One status wording and colour for every request row.
//
// A submitted request is the approver's decision, so its row says Approved or
// Rejected -- "Submitted" told the employee nothing. Drafts read Pending, and a
// draft already decided says so: nothing is final until it is submitted.

// A rejected Attendance Request is final as a draft; it is never submitted.
export function isFinalDraft(doc) {
	return doc?.doctype === "Attendance Request" && doc?.status === "Rejected"
}

export function isAwaitingSubmit(doc) {
	return (
		Number(doc?.docstatus) === 0 &&
		["Approved", "Rejected"].includes(doc?.status) &&
		!isFinalDraft(doc)
	)
}

export function notSubmittedLabel(status) {
	return `${status} · Not Submitted`
}

const THEMES = {
	Approved: "green",
	Paid: "green",
	Rejected: "red",
	Pending: "orange",
	Open: "orange",
	Cancelled: "gray",
	Submitted: "blue",
	[notSubmittedLabel("Approved")]: "orange",
	[notSubmittedLabel("Rejected")]: "orange",
}

export function requestStatus(doc, workflowStateField) {
	let label
	if (workflowStateField && doc?.[workflowStateField]) {
		label = doc[workflowStateField]
	} else if (Number(doc?.docstatus) === 2) {
		label = "Cancelled"
	} else if (Number(doc?.docstatus) === 1) {
		label = ["Approved", "Rejected"].includes(doc.status) ? doc.status : "Approved"
	} else if (isAwaitingSubmit(doc)) {
		label = notSubmittedLabel(doc.status)
	} else {
		label = ["Approved", "Rejected", "Cancelled"].includes(doc?.status) ? doc.status : "Pending"
	}
	return { label, theme: THEMES[label] || "gray" }
}
