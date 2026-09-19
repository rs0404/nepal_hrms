frappe.ui.form.on("Salary Slip", {
	onload(frm) {
		frappe.require([
			"/assets/nepal_hrms/css/nepal_hrms_settings.css?v=20260919b",
			"/assets/nepal_hrms/js/form_help.js",
		]);
	},

	refresh(frm) {
		frm.set_df_property("absent_days", "read_only", 0);
		configure_fixed_and_earned_columns(frm);
		configure_total_deduction_help(frm);
		apply_dynamic_rate_help(frm);
		frappe.require(
			[
				"/assets/nepal_hrms/css/nepal_hrms_settings.css?v=20260919b",
				"/assets/nepal_hrms/js/form_help.js",
			],
			() => attach_salary_slip_help(frm)
		);
	},

	employee: function (frm) {
        clear_manual_absent_override(frm);
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
        clear_manual_absent_override(frm);
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
                    validate_payroll_days(frm);
                }
            });
        } else {
            validate_payroll_days(frm);
        }
    },

    end_date: function (frm) {
        clear_manual_absent_override(frm);
        validate_payroll_days(frm);
    },

	absent_days(frm) {
		recalculate_salary_from_working_days(frm, { use_manual_absent: true });
	},
});

function clear_manual_absent_override(frm) {
	if (frm.fields_dict.custom_absent_days_manual) {
		frm.set_value("custom_absent_days_manual", 0);
	}
}

function mark_manual_absent_override(frm) {
	if (frm.fields_dict.custom_absent_days_manual) {
		frm.set_value("custom_absent_days_manual", 1);
	}
}

function recalculate_salary_from_working_days(frm, options) {
	options = options || {};
	if (!frm.doc.employee || !frm.doc.start_date || !frm.doc.end_date) {
		return;
	}
	if (options.use_manual_absent) {
		mark_manual_absent_override(frm);
	}
	return frappe.call({
		method: "process_salary_based_on_working_days",
		doc: frm.doc,
		args: {
			use_manual_absent: options.use_manual_absent ? 1 : 0,
		},
		callback() {
			frm.refresh();
		},
	});
}

function configure_fixed_and_earned_columns(frm) {
	const grids = [
		frm.fields_dict.earnings?.grid,
		frm.fields_dict.deductions?.grid,
	].filter(Boolean);

	for (const grid of grids) {
		if (!grid.docfields?.some((df) => df.fieldname === "custom_fixed_amount")) {
			continue;
		}

		grid.update_docfield_property("amount", "label", __("Earned / Actual Amount"));
		grid.update_docfield_property("custom_fixed_amount", "in_list_view", 1);
		grid.update_docfield_property("custom_fixed_amount", "columns", 2);
		grid.set_column_disp("custom_fixed_amount", true);
		grid.update_docfield_property(
			"do_not_include_in_total",
			"label",
			__("Calculation Only")
		);
		grid.update_docfield_property("do_not_include_in_total", "in_list_view", 1);
		grid.update_docfield_property("do_not_include_in_total", "columns", 1);
		grid.set_column_disp("do_not_include_in_total", true);
	}

	frm.set_df_property("gross_pay", "label", __("Earned Gross"));
}

function configure_total_deduction_help(frm) {
	const render_help = (earned_salary_mode, proportional) => {
		const deductions = frm.doc.deductions || [];
		const included = deductions
			.filter((row) => !row.do_not_include_in_total && flt(row.amount))
			.map((row) => frappe.utils.escape_html(row.salary_component));
		const excluded = deductions
			.filter((row) => row.do_not_include_in_total && flt(row.amount))
			.map((row) => frappe.utils.escape_html(row.salary_component));

		let mode_explanation;
		if (!earned_salary_mode) {
			mode_explanation = __(
				"Legacy mode: attendance deductions are included here and earnings remain fixed."
			);
		} else if (proportional) {
			mode_explanation = __(
				"Earned-salary mode: attendance deductions reduce fixed earnings proportionally and are excluded here."
			);
		} else {
			mode_explanation = __(
				"Earned-salary mode: attendance deductions reduce allowances first, then the contribution base if needed, and are excluded here."
			);
		}

		const description = [
			mode_explanation,
			__("Included in Total Deduction: {0}", [included.join(", ") || __("None")]),
			__("Excluded (Calculation Only): {0}", [excluded.join(", ") || __("None")]),
		].join("<br>");
		frm.set_df_property("total_deduction", "description", description);
		frm.refresh_field("total_deduction");

		const field = frm.get_field("total_deduction");
		const label = field?.$wrapper?.find(".control-label");
		field?.$wrapper?.find(".nepal-total-deduction-help").remove();
		if (label?.length) {
			$(
				'<button type="button" class="btn btn-xs btn-default nepal-total-deduction-help">?</button>'
			)
				.css("margin-left", "6px")
				.attr("title", __("Explain Total Deduction"))
				.on("click", () => {
					frappe.msgprint({
						title: __("Total Deduction"),
						message: description,
						indicator: "blue",
					});
				})
				.insertAfter(label);
		}
	};

	const row_indicates_earned_salary = (frm.doc.deductions || []).some(
		(row) => row.do_not_include_in_total
	);
	render_help(row_indicates_earned_salary, false);

	Promise.all([
		frappe.db.get_single_value(
			"Nepal HRMS Settings",
			"calculate_attendance_deductions_through_earned_salary"
		),
		frappe.db.get_single_value(
			"Nepal HRMS Settings",
			"proportionally_reduce_earnings_for_attendance_deductions"
		),
	])
		.then(([earned_salary_mode, proportional]) => {
			render_help(cint(earned_salary_mode), cint(proportional));
		})
		.catch(() => {
			// The row-level flags still provide accurate included/excluded lists
			// when the viewer cannot read Nepal HRMS Settings.
		});
}

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

const SALARY_SLIP_HELP_FIELDS = [
	"custom_ssf_base",
	"custom_daily_divisor_used",
	"custom_overtime_hours",
	"custom_paid_leave_days",
	"custom_late_entry_half_days",
	"custom_late_entry_full_days",
	"custom_early_exit_half_days",
	"custom_early_exit_full_days",
	"custom_out_of_office_half_days",
	"custom_unapproved_absent_days",
	"custom_penalty_days",
	"custom_late_deduction_rate",
	"custom_lwp_deduction_rate",
	"custom_unapproved_absent_rate",
	"custom_penalty_deduction_rate",
	"custom_is_continuous_lwp_gross",
	"custom_is_period_leave_gross",
	"custom_late_deduction_amount",
	"custom_lwp_deduction_amount",
	"custom_unapproved_absent_deduction_amount",
	"custom_penalty_deduction_amount",
	"custom_leave_late_deduction_total",
	"custom_annual_tax_projection_section",
	"custom_projected_annual_tds",
	"custom_tds_paid_till_date",
	"custom_remaining_payroll_periods",
	"custom_current_period_tds",
	"custom_assessable_employment_income",
	"custom_one_third_assessable_income",
	"custom_total_retirement_contribution",
	"custom_annual_retirement_limit",
	"custom_allowed_retirement_deduction",
	"custom_annual_taxable_deductions",
];


// The server writes one explanation per daily rate into
// custom_attendance_breakdown_data: the base it was charged on, the salary
// components inside that base, and the divisor. Render each into the field's
// description so the shared ? popover shows the arithmetic for *this* slip
// instead of the generic sentence. The static description stays as the
// fallback for a slip that has not been calculated yet.
function apply_dynamic_rate_help(frm) {
	const raw = frm.doc.custom_attendance_breakdown_data;
	if (!raw) return;

	let payload;
	try {
		payload = JSON.parse(raw);
	} catch (e) {
		return;
	}

	const explanations = Object.assign({}, payload.rate_explanations || {});
	if (payload.ssf_base_explanation) {
		explanations.custom_ssf_base = payload.ssf_base_explanation;
	}

	for (const [fieldname, explanation] of Object.entries(explanations)) {
		const field = frm.fields_dict[fieldname];
		if (!field || !explanation) continue;

		const html = render_rate_explanation(frm, field.df.label, explanation);
		if (!html) continue;

		field.df.description = html;
		frm.refresh_field(fieldname);

		// form_help binds a popover once and closes over its content, so drop
		// any button from an earlier calculation and let attach rebuild it.
		const $existing = field.$wrapper?.find(".nh-field-help");
		if ($existing?.length) {
			try {
				$existing.popover("dispose");
			} catch (e) {
				// Bootstrap 4 vs 5 naming; removing the node is enough.
			}
			$existing.remove();
		}
	}
}

function render_rate_explanation(frm, label, explanation) {
	const currency = frm.doc.currency;
	const money = (value) => format_currency(flt(value), currency);
	const esc = (value) => frappe.utils.escape_html(String(value == null ? "" : value));

	const components = explanation.components || [];
	if (!components.length) return "";

	const rows = components
		.map(
			(row) =>
				`<tr><td>${esc(row.label)}</td><td class="nh-rate-num">${money(
					row.amount
				)}</td></tr>`
		)
		.join("");

	const base_amount = flt(explanation.base_amount);
	const divisor = flt(explanation.divisor);
	const multiplier = flt(explanation.multiplier) || 1;

	// A single-component base already reads as its own total.
	const total_row =
		components.length > 1
			? `<tr class="nh-rate-total"><td>${__("Monthly base")}</td>` +
				`<td class="nh-rate-num">${money(base_amount)}</td></tr>`
			: "";

	const parts = [
		`<div class="nh-rate-base">${__("Base")}: <b>${esc(explanation.base_name)}</b></div>`,
		`<table class="nh-rate-help">${rows}${total_row}</table>`,
	];

	if (divisor > 0) {
		const multiplier_part = multiplier === 1 ? "" : ` × ${multiplier}`;
		parts.push(
			`<div class="nh-rate-formula">${esc(label)} = ${money(base_amount)} ÷ ${divisor}` +
				`${multiplier_part} = <b>${money(explanation.rate)}</b></div>`
		);
		if (explanation.divisor_basis) {
			parts.push(
				`<div class="nh-rate-note">${__("Divisor: {0} days ({1})", [
					divisor,
					esc(explanation.divisor_basis),
				])}</div>`
			);
		}
	}

	for (const note of explanation.notes || []) {
		parts.push(`<div class="nh-rate-note">${esc(note)}</div>`);
	}

	return parts.join("");
}

function attach_salary_slip_help(frm) {
	if (!nepal_hrms?.form_help?.attach) return;
	nepal_hrms.form_help.attach(frm, {
		form_class: "nh-salary-slip-form",
		fieldnames: SALARY_SLIP_HELP_FIELDS,
		include_sections: true,
		hide_all_descriptions: false,
	});
}
