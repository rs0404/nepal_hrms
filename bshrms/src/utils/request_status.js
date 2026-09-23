// One status wording and colour for every request row.
//
// A submitted request is the approver's decision, so its row says Approved or
// Rejected -- "Submitted" told the employee nothing. Drafts read Pending.

const THEMES = {
	Approved: "green",
	Paid: "green",
	Rejected: "red",
	Pending: "orange",
	Open: "orange",
	Cancelled: "gray",
	Submitted: "blue",
}

export function requestStatus(doc, workflowStateField) {
	let label
	if (workflowStateField && doc?.[workflowStateField]) {
		label = doc[workflowStateField]
	} else if (Number(doc?.docstatus) === 2) {
		label = "Cancelled"
	} else if (Number(doc?.docstatus) === 1) {
		label = ["Approved", "Rejected"].includes(doc.status) ? doc.status : "Approved"
	} else {
		label = ["Approved", "Rejected", "Cancelled"].includes(doc?.status) ? doc.status : "Pending"
	}
	return { label, theme: THEMES[label] || "gray" }
}
