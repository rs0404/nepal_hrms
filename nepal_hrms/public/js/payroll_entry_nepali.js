frappe.ui.form.on("Payroll Entry", {
    // Stock posts the accrual JV once, inside the slip-submission job. Cancel that
    // JV and there is no way back short of cancelling the whole payroll run, so
    // offer the entry again whenever nothing live is posted against this run.
    refresh: function (frm) {
        if (frm.doc.docstatus !== 1) return;

        frm.call("accrual_jv_status").then((r) => {
            const status = (r && r.message) || {};
            if (!status.can_create) return;

            const label = status.cancelled && status.cancelled.length
                ? __("Recreate Accrual Journal Entry")
                : __("Create Accrual Journal Entry");

            frm.add_custom_button(label, function () {
                create_accrual_journal_entry(frm, status);
            }).addClass("btn-primary");
        });
    },

    onload_post_render: function(frm) {
        if (frm.is_new() && !frm.doc.start_date && !frm.doc.end_date) {
            frappe.call({
                method: "nepal_hrms.utils.get_suggested_payroll_dates",
                args: {},
                callback: function(r) {
                    if (r.message && r.message.start_date && r.message.end_date) {
                        frm.set_value("start_date", r.message.start_date);
                        frm.set_value("end_date", r.message.end_date);
                        frappe.show_alert({
                            message: __('Auto-populated dates for the current payroll period'),
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    },

    start_date: function(frm) {
        if (frm.doc.start_date) {
            frappe.call({
                method: "nepal_hrms.utils.get_suggested_payroll_dates",
                args: { start_date: frm.doc.start_date },
                callback: function (r) {
                    if (r.message && r.message.is_first_day && r.message.end_date) {
                        frm.set_value("end_date", r.message.end_date);
                        frappe.show_alert({
                            message: __('End date auto-filled for the payroll period'),
                            indicator: 'green'
                        });
                    }
                    validate_payroll_entry_days(frm);
                }
            });
        } else {
            validate_payroll_entry_days(frm);
        }
    },

    end_date: function(frm) {
        validate_payroll_entry_days(frm);
    }
});

function create_accrual_journal_entry(frm, status) {
    let message = __("This will post the accrual Journal Entry for {0} salary slip(s).", [
        status.pending_slips,
    ]);
    if (status.cancelled && status.cancelled.length) {
        message += " " + __("The cancelled entry {0} is left as it is.", [status.cancelled[0]]);
    }

    frappe.confirm(message, function () {
        frm.call({
            method: "create_accrual_journal_entry",
            doc: frm.doc,
            freeze: true,
            freeze_message: __("Creating Journal Entry..."),
        }).then((r) => {
            const journal_entry = r && r.message && r.message.journal_entry;
            if (!journal_entry) {
                frm.reload_doc();
                return;
            }
            frappe.show_alert({
                message: __("Journal Entry {0} created", [journal_entry]),
                indicator: "green",
            });
            frappe.set_route("Form", "Journal Entry", journal_entry);
        });
    });
}

function validate_payroll_entry_days(frm) {
    if (frm.doc.start_date && frm.doc.end_date) {
        let diff = frappe.datetime.get_day_diff(frm.doc.end_date, frm.doc.start_date) + 1;
        if (diff > 32) {
            frappe.msgprint({
                title: __('Warning'),
                indicator: 'orange',
                message: __('The selected period is {0} days, which is greater than 32 days. Please verify the dates. You may have selected 2 months period.', [diff])
            });
        }
    }
}
