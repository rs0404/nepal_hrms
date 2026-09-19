// Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
// For license information, please see license.txt

const NEPAL_PAYROLL_PREFIX = "Nepal Payroll - ";

const EARNINGS_HELP_NEPAL = __(
	"Nepal Payroll structures only list fixed earnings here (Basic, Dearness Allowance, Grade, and similar).\n\nOther Allowances (transport, communication, housing, etc.) are not shown in this Earnings table.\n\nEnter them on Salary Structure Assignment → Other Allowances. When the Salary Slip is created, those rows are added automatically with the Assignment amounts.\n\nExample: Assignment has Transport Allowance = 3,000. The slip pays 3,000 even though Transport Allowance is not listed here."
);

const EARNINGS_HELP_CUSTOM = __(
	"This is not a Nepal Payroll structure, so Other Allowances are not injected automatically from the Assignment.\n\nTo pay an allowance from Salary Structure Assignment → Other Allowances:\n1. Add the same Salary Component here under Earnings.\n2. Set the component formula to nsa_<abbr> (the component's Abbr).\n\nExample: Component Transport Allowance, Abbr transport, formula nsa_transport. Assignment amount 3,000 → slip pays 3,000.\n\nIf you put only a fixed amount on this Earnings row, the slip uses that fixed amount and ignores the Assignment table.\n\nIf the allowance is only on the Assignment and missing here, it raises Base but is not paid."
);

frappe.ui.form.on("Salary Structure", {
	onload(frm) {
		frappe.require([
			"/assets/nepal_hrms/css/nepal_hrms_settings.css",
			"/assets/nepal_hrms/js/form_help.js",
		]);
	},

	refresh(frm) {
		frappe.require(
			[
				"/assets/nepal_hrms/css/nepal_hrms_settings.css",
				"/assets/nepal_hrms/js/form_help.js",
			],
			() => attach_earnings_help(frm)
		);
	},
});

function attach_earnings_help(frm) {
	const field = frm.fields_dict.earnings;
	if (!field?.$wrapper) return;

	frm.$wrapper.addClass("nh-help-form nh-salary-structure-form");

	const is_nepal = (frm.doc.name || "").startsWith(NEPAL_PAYROLL_PREFIX);
	const content = nepal_hrms.form_help.help_html(
		is_nepal ? EARNINGS_HELP_NEPAL : EARNINGS_HELP_CUSTOM
	);

	// Prefer the grid field label's help slot; fall back to a label next to the section.
	let $anchor = field.$wrapper.find("> .control-label .help, > .grid-field > .help").first();
	if (!$anchor.length) {
		$anchor = field.$wrapper.find("span.help").first();
	}
	if (!$anchor.length) {
		const $label = field.$wrapper.find(".control-label, .grid-heading-level").first();
		if ($label.length) {
			$anchor = $('<span class="help nh-earnings-help"></span>');
			$label.append($anchor);
		}
	}
	if (!$anchor.length) return;

	// Replace any previous popover so Nepal vs custom text updates after rename/reload.
	$anchor.find(".nh-field-help").remove();
	nepal_hrms.form_help.bind_help_button($anchor, content);
}
