frappe.listview_settings["Salary Slip"] = frappe.listview_settings["Salary Slip"] || {};

const _salary_slip_list_onload = frappe.listview_settings["Salary Slip"].onload;

frappe.listview_settings["Salary Slip"].onload = function (listview) {
	if (_salary_slip_list_onload) {
		_salary_slip_list_onload(listview);
	}

	listview.page.add_actions_menu_item(__("Sync with Attendance"), () => {
		const slips = listview.get_checked_items(true);
		if (!slips.length) {
			frappe.msgprint(__("Select the draft Salary Slips to sync."));
			return;
		}
		frappe.require("/assets/nepal_hrms/js/salary_slip_attendance_sync.js", () => {
			nepal_hrms.salary_slip_sync.run(slips, () => listview.refresh());
		});
	});
};
