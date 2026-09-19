// Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.provide("nepal_hrms.form_help");

(() => {
	const CSS = "/assets/nepal_hrms/css/nepal_hrms_settings.css?v=20260919b";
	const SKIP = new Set([
		"Tab Break",
		"Section Break",
		"Column Break",
		"HTML",
		"Heading",
		"Fold",
	]);

	let dismiss_bound = false;

	function help_html(text) {
		if (!text) return "";
		return String(__(text)).replace(/\n/g, "<br>");
	}

	function hide_popovers() {
		$(".nh-field-help").popover("hide");
	}

	function is_help_target(target) {
		return $(target).closest(".nh-field-help, .popover.nh-help-popover").length > 0;
	}

	function ensure_dismiss_on_outside() {
		if (dismiss_bound) return;
		dismiss_bound = true;

		// Capture phase so Desk/form handlers that stopPropagation still dismiss.
		document.addEventListener(
			"pointerdown",
			(e) => {
				if (!is_help_target(e.target)) hide_popovers();
			},
			true
		);
		document.addEventListener(
			"keydown",
			(e) => {
				if (e.key === "Escape") hide_popovers();
			},
			true
		);
	}

	function bind_help_button($anchor, content) {
		if (!$anchor.length || !content) return;
		if ($anchor.find(".nh-field-help").length) return;

		ensure_dismiss_on_outside();

		const $btn = $(`<button type="button" class="btn-reset nh-field-help" aria-label="${__(
			"Help"
		)}">${frappe.utils.icon("help", "sm")}</button>`);
		$anchor.append($btn);

		$btn.popover({
			trigger: "manual",
			placement: "auto",
			html: true,
			sanitize: false,
			container: "body",
			template: `<div class="popover nh-help-popover" role="tooltip">
				<div class="arrow"></div>
				<div class="popover-body"></div>
			</div>`,
			content: () => `<div class="nh-help-body">${content}</div>`,
		});

		$btn.on("click", (e) => {
			e.preventDefault();
			e.stopPropagation();
			const open = $btn.attr("aria-describedby");
			hide_popovers();
			if (!open) $btn.popover("show");
		});
	}

	function anchor_for_field(field) {
		if (field.df.fieldtype === "Button") {
			const $button = field.$wrapper.find("button").first();
			if (!$button.length) return $();
			let $help = field.$wrapper.find(".nh-button-help");
			if (!$help.length) {
				$help = $('<span class="help nh-button-help"></span>');
				$button.after($help);
			}
			return $help;
		}

		if (field.df.fieldtype === "Check") {
			const $label = field.$wrapper.find(".checkbox label");
			let $help = field.$wrapper.find(".nh-check-help");
			if (!$help.length) {
				$help = field.$wrapper.find("span.help").first();
				if ($help.parent().is("label")) {
					$help.addClass("nh-check-help").insertAfter($label);
				} else {
					$help = $('<span class="help nh-check-help"></span>').insertAfter($label);
				}
			}
			return $help;
		}

		return field.$wrapper.find("span.help").first();
	}

	function attach(frm, opts = {}) {
		const fieldnames = opts.fieldnames || null;
		const include_sections = opts.include_sections !== false;
		const hide_all_descriptions = opts.hide_all_descriptions !== false;

		frm.$wrapper.addClass("nh-help-form");
		if (hide_all_descriptions) frm.$wrapper.addClass("nh-help-hide-all");
		if (opts.form_class) frm.$wrapper.addClass(opts.form_class);

		Object.values(frm.fields_dict || {}).forEach((field) => {
			if (!field?.df || !field.$wrapper) return;
			if (SKIP.has(field.df.fieldtype)) return;
			if (fieldnames && !fieldnames.includes(field.df.fieldname)) return;
			const content = help_html(field.df.description);
			if (!content) return;
			field.$wrapper.addClass("nh-help-attached");
			bind_help_button(anchor_for_field(field), content);
		});

		if (include_sections) {
			(frm.layout.sections || []).forEach((section) => {
				const fname = section.df?.fieldname;
				if (fieldnames && fname && !fieldnames.includes(fname)) return;
				const content = help_html(section.df?.description);
				if (!content || !section.head?.length) return;
				if (section.head.find(".nh-field-help").length) return;

				const $help = $('<span class="help nh-section-help"></span>');
				const $indicator = section.head.find(".collapse-indicator");
				if ($indicator.length) {
					$indicator.before($help);
				} else {
					section.head.append($help);
				}
				bind_help_button($help, content);
				$help.on("click", (e) => e.stopPropagation());
				$(section.wrapper || section.head.closest(".form-section")).addClass(
					"nh-help-attached"
				);
			});
		}

		frm.$wrapper
			.off("shown.bs.tab.nh-help")
			.on("shown.bs.tab.nh-help", ".form-tabs a", hide_popovers);

		ensure_dismiss_on_outside();
	}

	nepal_hrms.form_help = {
		css: CSS,
		attach,
		help_html,
		bind_help_button,
		hide_popovers,
	};
})();
