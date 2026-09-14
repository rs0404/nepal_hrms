function cnr_time_from_datetime(dt) {
	if (!dt) return null;
	const s = String(dt);
	// "YYYY-MM-DD HH:MM:SS" or ISO → HH:MM:SS
	const part = s.includes('T') ? s.split('T')[1] : s.split(' ').pop();
	return (part || '').slice(0, 8);
}

async function cnr_fill_from_attendance(frm) {
	if (!frm.doc.attendance) return;

	const att = await frappe.db.get_value('Attendance', frm.doc.attendance, [
		'employee',
		'attendance_date',
		'company',
		'in_time',
		'out_time',
	]);
	const d = att && att.message;
	if (!d) return;

	if (!frm.doc.employee && d.employee) await frm.set_value('employee', d.employee);
	if (!frm.doc.attendance_date && d.attendance_date) {
		await frm.set_value('attendance_date', d.attendance_date);
	}
	if (!frm.doc.company && d.company) await frm.set_value('company', d.company);

	if (frm.doctype === 'Early Exit Application' && !frm.doc.early_exit_time && d.out_time) {
		await frm.set_value('early_exit_time', cnr_time_from_datetime(d.out_time));
	}
}

async function cnr_link_attendance(frm) {
	if (frm.doc.attendance || !frm.doc.employee || !frm.doc.attendance_date) return;

	const rows = await frappe.db.get_list('Attendance', {
		filters: {
			employee: frm.doc.employee,
			attendance_date: frm.doc.attendance_date,
			docstatus: ['<', 2],
		},
		fields: ['name'],
		limit: 1,
	});
	if (rows && rows.length) {
		await frm.set_value('attendance', rows[0].name);
	}
}

async function cnr_warn_application_deadline(frm) {
	if (
		![
			'Late Entry Application',
			'Early Exit Application',
			'Out of Office Application',
		].includes(frm.doctype)
	) return;
	if (!frm.doc.attendance_date) return;

	try {
		const r = await frappe.call({
			method: 'nepal_hrms.api.cnr_applications.get_late_early_application_deadline_settings',
			freeze: false,
		});
		const s = r && r.message;
		if (!s || !cint(s.enable_late_early_application_deadline)) return;

		const maxDays = cint(s.late_early_application_max_days) || 2;
		const deadlineStr = frappe.datetime.add_days(frm.doc.attendance_date, maxDays);
		if (frappe.datetime.get_diff(frappe.datetime.get_today(), deadlineStr) > 0) {
			frappe.msgprint({
				title: __('Application Deadline Passed'),
				indicator: 'red',
				message: __(
						'{0} cannot be filed for {1}. Applications must be filed within {2} day(s) of the attendance date (deadline was {3}).',
					[
						__(frm.doctype),
						frappe.datetime.str_to_user(frm.doc.attendance_date),
						maxDays,
						frappe.datetime.str_to_user(deadlineStr),
					]
				),
			});
		}
	} catch (e) {
		// Never block the form UI if deadline settings cannot be read
		console.warn('cnr deadline check skipped', e);
	}
}

async function cnr_apply_approval_ui(frm) {
	if (frm.doc.docstatus !== 0) return;

	let canApprove = false;
	try {
		const r = await frappe.call({
			method: 'nepal_hrms.api.cnr_applications.can_approve_cnr_application',
			args: { employee: frm.doc.employee },
			freeze: false,
		});
		canApprove = !!(r && r.message);
	} catch (e) {
		canApprove = frappe.user_roles.some((role) =>
			['Leave Approver', 'HR Manager', 'System Manager', 'Administrator'].includes(role)
		);
	}

	frm.set_df_property('status', 'read_only', canApprove ? 0 : 1);
	frm._cnr_can_approve = canApprove;
}

function cnr_notify_draft_filed(frm) {
	if (frm.doc.docstatus !== 0 || frm.doc.status !== 'Draft') return;
	if (!frm._cnr_was_new) return;

	frappe.call({
		method: 'nepal_hrms.api.cnr_applications.can_approve_cnr_application',
		args: { employee: frm.doc.employee },
		freeze: false,
		callback(r) {
			if (r && r.message) return; // leave approver / HR — no need for this tip
			frappe.msgprint({
				title: __('Application Submitted'),
				indicator: 'blue',
				message: __(
					'You have submitted this {0}. Please wait for your Leave Approver to approve it. Until then it will remain in Draft — that means it is awaiting approval, not that it failed to submit.',
					[__(frm.doctype)]
				),
			});
		},
	});
}

function bind_cnr_application(doctype) {
	frappe.ui.form.on(doctype, {
		onload(frm) {
			// Connections / + New from Attendance set route_options.attendance
			if (frm.is_new() && frappe.route_options && frappe.route_options.attendance) {
				frm.set_value('attendance', frappe.route_options.attendance);
			}
		},
		before_save(frm) {
			frm._cnr_was_new = frm.is_new();
		},
		after_save(frm) {
			cnr_notify_draft_filed(frm);
			frm._cnr_was_new = false;
		},
		refresh(frm) {
			if (frm.is_new() && frm.doc.attendance) {
				cnr_fill_from_attendance(frm);
			}
			cnr_apply_approval_ui(frm);
		},
		attendance(frm) {
			cnr_fill_from_attendance(frm);
		},
		employee(frm) {
			cnr_link_attendance(frm);
			cnr_apply_approval_ui(frm);
		},
		attendance_date(frm) {
			cnr_link_attendance(frm);
			cnr_warn_application_deadline(frm);
		},
		estimated_from_time(frm) {
			cnr_warn_ooo_time_limit(frm);
		},
		estimated_to_time(frm) {
			cnr_warn_ooo_time_limit(frm);
		},
		validate(frm) {
			cnr_warn_ooo_time_limit(frm);
			return cnr_warn_application_deadline(frm);
		},
	});
}

async function cnr_warn_ooo_time_limit(frm) {
	if (
		frm.doctype !== 'Out of Office Application' ||
		!frm.doc.estimated_from_time ||
		!frm.doc.estimated_to_time
	) return;

	const toMinutes = (value) => {
		const parts = String(value).split(':').map((part) => Number(part) || 0);
		return parts[0] * 60 + parts[1] + parts[2] / 60;
	};
	const duration = (toMinutes(frm.doc.estimated_to_time) -
		toMinutes(frm.doc.estimated_from_time)) / 60;
	if (duration < 0) return;

	const r = await frappe.call({
		method: 'nepal_hrms.api.cnr_applications.get_late_early_application_deadline_settings',
		freeze: false,
	});
	const maxHours = Number(r?.message?.max_paid_out_of_office_hours || 2);
	if (maxHours > 0 && duration > maxHours) {
		frappe.show_alert({
			message: __(
				'Estimated OOO duration ({0}h) exceeds the configured {1}h limit. Submission will be blocked.',
				[duration.toFixed(2), maxHours]
			),
			indicator: 'red',
		}, 7);
	}
}

['Late Entry Application', 'Early Exit Application', 'Out of Office Application'].forEach(bind_cnr_application);
