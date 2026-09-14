frappe.ui.form.on("Leave Application", {
	setup(frm) {
		frm.set_df_property("description", "reqd", 1);
	},
	refresh(frm) {
		frm.set_df_property("description", "reqd", 1);
	},
});
