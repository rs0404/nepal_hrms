frappe.ui.form.on("Attendance Request", {
	setup(frm) {
		frm.set_df_property("explanation", "reqd", 1);
		frm.set_df_property("explanation", "label", __("Reason / Explanation"));
	},
	refresh(frm) {
		frm.set_df_property("explanation", "reqd", 1);
	},
});
