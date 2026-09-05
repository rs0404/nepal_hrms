frappe.ui.form.on("Salary Slip", {
    employee: function (frm) {
        if (!frm.doc.employee) return;

        frappe.call({
            method: "nepal_hrms.utils.get_suggested_payroll_dates",
            args: { employee: frm.doc.employee },
            callback: function (r) {
                if (r.message && r.message.start_date && r.message.end_date) {
                    frm.set_value("start_date", r.message.start_date);
                    frm.set_value("end_date", r.message.end_date);
                    frappe.show_alert({
                        message: __('Auto-populated dates based on Nepali calendar'),
                        indicator: 'green'
                    });
                }
            }
        });
    },

    start_date: function (frm) {
        if (frm.doc.start_date) {
            frappe.call({
                method: "nepal_hrms.utils.get_suggested_payroll_dates",
                args: { start_date: frm.doc.start_date },
                callback: function (r) {
                    if (r.message && r.message.is_first_day && r.message.end_date) {
                        frm.set_value("end_date", r.message.end_date);
                        frappe.show_alert({
                            message: __('End date auto-filled for the Nepali month'),
                            indicator: 'green'
                        });
                    }
                    validate_payroll_days(frm);
                }
            });
        } else {
            validate_payroll_days(frm);
        }
    },

    end_date: function (frm) {
        validate_payroll_days(frm);
    }
});

function validate_payroll_days(frm) {
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
