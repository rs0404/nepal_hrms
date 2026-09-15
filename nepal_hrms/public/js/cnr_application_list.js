// Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
// For license information, please see license.txt

const CNR_STATUS_COLORS = {
	Approved: "green",
	Rejected: "red",
	Draft: "orange",
};

function cnr_list_indicator(doc) {
	if (cint(doc.docstatus) === 2) {
		return [__("Cancelled"), "gray", "docstatus,=,2"];
	}
	const status = doc.status || "Draft";
	return [__(status), CNR_STATUS_COLORS[status] || "gray", "status,=," + status];
}

["Late Entry Application", "Early Exit Application", "Out of Office Application"].forEach(
	(doctype) => {
		frappe.listview_settings[doctype] = {
			add_fields: ["status"],
			has_indicator_for_draft: 1,
			has_indicator_for_cancelled: 1,
			get_indicator: cnr_list_indicator,
		};
	}
);
