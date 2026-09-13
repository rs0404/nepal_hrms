frappe.provide("nepal_hrms");

/**
 * Weekday + relative day vs today, e.g. "Wednesday · 2 days ago".
 */
nepal_hrms.format_date_approval_hint = function (date) {
	if (!date) return "";

	const dateStr = String(date).split(" ")[0];
	let weekday = "";
	try {
		const m = frappe.datetime.str_to_obj(dateStr);
		if (m && typeof moment !== "undefined") {
			weekday = moment(m).format("dddd");
		} else if (m instanceof Date && !Number.isNaN(m.getTime())) {
			weekday = [
				"Sunday",
				"Monday",
				"Tuesday",
				"Wednesday",
				"Thursday",
				"Friday",
				"Saturday",
			][m.getDay()];
		}
	} catch (e) {
		weekday = "";
	}

	const today = frappe.datetime.get_today();
	const diff = frappe.datetime.get_diff(dateStr, today);
	let relative = "";
	if (diff === 0) {
		relative = __("Today");
	} else if (diff === 1) {
		relative = __("1 day after");
	} else if (diff === -1) {
		relative = __("1 day ago");
	} else if (diff > 1) {
		relative = __("{0} days after", [diff]);
	} else {
		relative = __("{0} days ago", [Math.abs(diff)]);
	}

	if (weekday && relative) {
		return `${__(weekday)} · ${relative}`;
	}
	return weekday || relative;
};

nepal_hrms.DATE_APPROVAL_HINT_FIELDS = new Set([
	"attendance_date",
	"from_date",
	"to_date",
	"half_day_date",
	"posting_date",
]);

nepal_hrms.append_date_approval_hint = function (control, text) {
	const fieldname = control && control.df && control.df.fieldname;
	if (!fieldname || !nepal_hrms.DATE_APPROVAL_HINT_FIELDS.has(fieldname)) {
		return text;
	}
	const value = control.get_value ? control.get_value() : null;
	const hint = nepal_hrms.format_date_approval_hint(value);
	if (!hint) return text || "";

	let base = String(text || "");
	// Avoid stacking duplicate hints when the control refreshes.
	base = base
		.replace(
			/\s*[·•]\s*(Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday)\s*[·•].*$/i,
			""
		)
		.trim();
	return base ? `${base} · ${hint}` : hint;
};

nepal_hrms.patch_date_equivalent_display = function () {
	const proto = frappe.ui.form.ControlDate && frappe.ui.form.ControlDate.prototype;
	if (!proto || !proto.show_equivalent_date || proto.__nepal_hrms_approval_hint_patched) {
		return false;
	}
	const original = proto.show_equivalent_date;
	proto.show_equivalent_date = function (text) {
		return original.call(this, nepal_hrms.append_date_approval_hint(this, text));
	};
	proto.__nepal_hrms_approval_hint_patched = true;
	return true;
};

// nepal_compliance replaces ControlDate; patch after it, and retry briefly.
$(function () {
	nepal_hrms.patch_date_equivalent_display();
	setTimeout(nepal_hrms.patch_date_equivalent_display, 300);
	setTimeout(nepal_hrms.patch_date_equivalent_display, 1200);
});
