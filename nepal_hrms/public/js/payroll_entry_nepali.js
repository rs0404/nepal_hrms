frappe.ui.form.on("Payroll Entry", {
    // Stock posts the accrual JV once, inside the slip-submission job. Cancel that
    // JV and there is no way back short of cancelling the whole payroll run, so
    // offer the entry again whenever nothing live is posted against this run.
    refresh: function (frm) {
        if (frm.doc.docstatus !== 1) return;

        add_payroll_download_buttons(frm);

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
            // Payroll Journal Entries open only for the Payroll Journal Viewer role.
            if (can_see_payroll_journals()) {
                frappe.set_route("Form", "Journal Entry", journal_entry);
            } else {
                frm.reload_doc();
            }
        });
    });
}

// Excel downloads built by nepal_hrms.api.payroll_exports. Net Pay downloads at
// once; the rest open a dialog for their choices. Either way, whatever would make
// the file short is said out loud, so nobody uploads a bank file and discovers
// afterwards who was not on it.
const PAYROLL_EXPORTS = "nepal_hrms.api.payroll_exports";

function add_payroll_download_buttons(frm) {
    const group = __("Download");
    frm.add_custom_button(__("Net Pay (Corporate Pay format)"), () => download_net_pay(frm), group);
    frm.add_custom_button(__("Net Pay by Component (Corporate Pay format)"), () => open_payroll_download(frm, "component_net_pay"), group);
    frm.add_custom_button(__("Component Payment (Corporate Pay format)"), () => open_payroll_download(frm, "components"), group);
    frm.add_custom_button(__("Salary & Tax Sheet"), () => run_payroll_download({ payroll_entry: frm.doc.name, kind: "salary_sheet" }), group);
    frm.add_custom_button(__("SSF Contribution"), () => open_payroll_download(frm, "ssf"), group);
    frm.add_custom_button(__("CIT Contribution"), () => open_payroll_download(frm, "cit"), group);
    if (can_see_payroll_journals()) {
        frm.add_custom_button(__("Accrual Journal Entry"), () => open_payroll_download(frm, "jv"), group);
    }
}

// A server-side refusal (a slip that cannot go on the bank file) would come back
// as a downloaded error page, so the same call is made first as a check.
function run_payroll_download(args) {
    return frappe.call({
        method: `${PAYROLL_EXPORTS}.download_payroll_export`,
        args: Object.assign({ validate_only: 1 }, args),
        freeze: true,
        freeze_message: __("Preparing file..."),
    }).then(() => {
        open_url_post(frappe.request.url, Object.assign({ cmd: `${PAYROLL_EXPORTS}.download_payroll_export` }, args));
    });
}

// The ERP's net pay as it stands: nothing to choose, so no dialog. Anyone left
// off the file is named once it is on its way.
function download_net_pay(frm) {
    frappe.call({
        method: `${PAYROLL_EXPORTS}.get_payroll_export_options`,
        args: { payroll_entry: frm.doc.name },
        freeze: true,
    }).then((r) => {
        const opts = r.message || {};
        return run_payroll_download({ payroll_entry: frm.doc.name, kind: "net_pay" }).then(() => {
            if (opts.draft_count || (opts.no_account || []).length || (opts.no_bank_code || []).length) {
                frappe.msgprint({
                    title: __("Net Pay downloaded · check these"),
                    indicator: "orange",
                    message: payroll_download_checks_html(opts, "net_pay"),
                });
            }
        });
    });
}

function open_payroll_download(frm, kind) {
    frappe.call({
        method: `${PAYROLL_EXPORTS}.get_payroll_export_options`,
        args: { payroll_entry: frm.doc.name },
        freeze: true,
    }).then((r) => {
        const opts = r.message || {};
        const to_options = (list, checked) => (list || []).map((c) => ({
            label: `${c.root} (${format_currency(c.total, frappe.defaults.get_default("currency"), 2)})`,
            value: c.root,
            checked: checked ? 1 : 0,
        }));
        const options = to_options(opts.components);
        const titles = {
            component_net_pay: __("Download Net Pay by Component (Corporate Pay format) · {0}", [opts.period]),
            components: __("Download Component Payment (Corporate Pay format) · {0}", [opts.period]),
            ssf: __("Download SSF Contribution · {0}", [opts.period]),
            cit: __("Download CIT Contribution · {0}", [opts.period]),
            jv: __("Download Accrual Journal Entry · {0}", [opts.period]),
        };
        const fields = [
            { fieldtype: "HTML", fieldname: "checks", options: payroll_download_checks_html(opts, kind) },
        ];
        if (kind === "component_net_pay") {
            // Everything starts ticked, which is the slip's own net pay; untick
            // what this payment should not carry.
            fields.push({
                fieldtype: "MultiCheck", fieldname: "components", columns: 2, select_all: true,
                options: to_options(opts.components, true),
                label: __("Earnings to pay"),
            });
            fields.push({
                fieldtype: "MultiCheck", fieldname: "deductions", columns: 2, select_all: true,
                options: to_options(opts.deductions, true),
                label: __("Deductions to take off"),
                description: __("Amount paid = ticked earnings − ticked deductions. Calculation Only rows are never counted, so with everything ticked this is the ERP net pay."),
            });
        } else if (kind === "components") {
            fields.push({
                fieldtype: "MultiCheck", fieldname: "components", columns: 2, options, reqd: 1, select_all: true,
                label: __("Components to pay"),
                description: __("Salary and Wages variants of a component are paid together. Their tax stays deducted in Net Pay."),
            });
        }

        const d = new frappe.ui.Dialog({
            title: titles[kind],
            fields,
            primary_action_label: __("Download"),
            primary_action(values) {
                const args = { payroll_entry: frm.doc.name, kind };
                if (kind === "component_net_pay") {
                    if (!(values.components || []).length) {
                        frappe.msgprint(__("Tick at least one earning that makes up the payment."));
                        return;
                    }
                    args.components = JSON.stringify(values.components);
                    args.deductions = JSON.stringify(values.deductions || []);
                }
                if (kind === "components") {
                    if (!(values.components || []).length) {
                        frappe.msgprint(__("Pick at least one component to pay."));
                        return;
                    }
                    args.components = JSON.stringify(values.components);
                }
                run_payroll_download(args).then(() => d.hide());
            },
        });
        d.show();
    });
}

function payroll_download_checks_html(opts, kind) {
    const esc = frappe.utils.escape_html;
    const names = (list) => list.map(esc).join(", ");
    const notes = [];
    const bank = ["net_pay", "component_net_pay", "components"].includes(kind);

    if (opts.draft_count) {
        notes.push(["orange", __("{0} of {1} salary slip(s) are still drafts and are included as they stand.", [opts.draft_count, opts.slip_count])]);
    }
    if (bank && (opts.no_account || []).length) {
        notes.push(["orange", __("No bank account, so not in this file — pay separately: {0}", [names(opts.no_account)])]);
    }
    if (bank && (opts.no_bank_code || []).length) {
        notes.push(["orange", __("No NCHL bank code for bank {0}: the Bank Code column is left blank for them. Fill it in before uploading, or set it on the Bank record.", [names(opts.no_bank_code)])]);
    }
    if (kind === "ssf" && (opts.no_ssf_number || []).length) {
        notes.push(["orange", __("No SSF Number on the employee: {0}", [names(opts.no_ssf_number)])]);
    }
    if (kind === "cit" && (opts.no_cit_number || []).length) {
        notes.push(["orange", __("No CIT Number on the employee: {0}", [names(opts.no_cit_number)])]);
    }
    if (kind === "jv") {
        notes.push(["blue", __("Shows the posted accrual Journal Entry, or, until the salary slips are submitted, a preview of the one that will be posted. Nothing is saved.")]);
    }
    if (!notes.length) {
        return `<p class="text-muted">${__("{0} salary slip(s). Nothing needs attention.", [opts.slip_count])}</p>`;
    }
    return notes
        .map(([color, text]) => `<div class="alert alert-${{ red: "danger", blue: "info" }[color] || "warning"} small" style="margin-bottom:8px;">${text}</div>`)
        .join("");
}

// Mirrors nepal_hrms.custom_code.payroll.journal_access; the server enforces it.
function can_see_payroll_journals() {
    return frappe.session.user === "Administrator" || frappe.user.has_role("Payroll Journal Viewer");
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
