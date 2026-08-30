// Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings["Attendance"] = frappe.listview_settings["Attendance"] || {};

const _attendance_list_onload = frappe.listview_settings["Attendance"].onload;

frappe.listview_settings["Attendance"].onload = function (listview) {
	if (_attendance_list_onload) {
		_attendance_list_onload(listview);
	}

	listview.page.add_inner_button(__("Recalculate C&R for Period…"), () => {
		nepal_hrms.attendance_cnr_bulk.open_dialog({});
	});
};
