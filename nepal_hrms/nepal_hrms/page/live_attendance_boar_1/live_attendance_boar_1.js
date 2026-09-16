frappe.pages['live_attendance_boar-1'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Live Attendance Board',
		single_column: true
	});

	$(frappe.render_template("live_attendance_boar_1", {})).appendTo(page.body);

	let selected_date = frappe.datetime.get_today();
	let selected_employee = "";
	let viewing_today = true;
	let date_bs_base = "----";

	const date_control = frappe.ui.form.make_control({
		parent: $("#lab-date-control"),
		df: {
			fieldtype: "Date",
			fieldname: "attendance_date",
			label: __("Date"),
			reqd: 1,
			change: function () {
				const val = date_control.get_value();
				if (!val || val === selected_date) {
					return;
				}
				selected_date = val;
				load_board();
			},
		},
		render_input: true,
	});
	date_control.refresh();
	date_control.set_value(selected_date);

	const employee_control = frappe.ui.form.make_control({
		parent: $("#lab-employee-control"),
		df: {
			fieldtype: "Link",
			fieldname: "employee",
			options: "Employee",
			label: __("Employee"),
			placeholder: __("Search employee"),
			get_query: () => ({
				filters: { status: "Active" },
			}),
			change: function () {
				const val = employee_control.get_value() || "";
				if (val === selected_employee) {
					return;
				}
				selected_employee = val;
				load_board();
			},
		},
		render_input: true,
	});
	employee_control.refresh();

	function update_time() {
		if (!viewing_today) {
			return;
		}
		let now = new Date();
		let time_str =
			now.getHours().toString().padStart(2, "0") +
			":" +
			now.getMinutes().toString().padStart(2, "0") +
			":" +
			now.getSeconds().toString().padStart(2, "0");
		$("#lab-date-bs").text(date_bs_base + " " + time_str);
	}

	setInterval(update_time, 1000);

	function load_board() {
		$("#col-pending").html('<div class="lab-empty">Refreshing...</div>');
		$("#col-active").html('<div class="lab-empty">Refreshing...</div>');
		$("#col-completed").html('<div class="lab-empty">Refreshing...</div>');
		$("#col-leave").html('<div class="lab-empty">Refreshing...</div>');
		$("#col-upcoming").html('<div class="lab-empty">Refreshing...</div>');
		$("#col-pending_leave").html('<div class="lab-empty">Refreshing...</div>');

		frappe.call({
			method: "nepal_hrms.nepal_hrms.page.live_attendance_boar_1.live_attendance_boar_1.get_live_data",
			args: {
				attendance_date: selected_date,
				employee: selected_employee || undefined,
			},
			callback: function (r) {
				if (r.message) {
					render_board(r.message);
					if (r.message.is_today) {
						update_time();
					}
				}
			},
		});
	}

	function generate_card(emp) {
		let punches_html = "";
		if (emp.punches && emp.punches.length > 0) {
			punches_html = `<div class="lab-punches">`;
			emp.punches.forEach((p) => {
				let p_str = p.toString();
				let typeClass = "";
				if (p_str.includes("(IN)") || p_str.includes("(OOO IN)")) typeClass = "in";
				else if (p_str.includes("(OUT)") || p_str.includes("(OOO OUT)")) typeClass = "out";
				punches_html += `<div class="lab-punch ${typeClass}">${p}</div>`;
			});
			punches_html += `</div>`;
		} else {
			punches_html = `<div class="lab-punches"><div class="lab-punch" style="background:transparent; border-color:transparent; color:#94a3b8;">No logs</div></div>`;
		}

		let ooo_tag = "";
		if (emp.punches && emp.punches.some((p) => p.includes("OOO"))) {
			ooo_tag = `<span class="lab-tag ooo">Out of Office</span>`;
		}

		return `
            <div class="lab-card">
                <div class="lab-emp-name">${emp.employee_name} ${ooo_tag}</div>
                <div class="lab-emp-dept">
                    <span>${emp.name}</span>
                </div>
                ${punches_html}
            </div>
        `;
	}

	function render_board(data) {
		date_bs_base = data.today_bs || "----";
		viewing_today = !!data.is_today;
		selected_date = data.attendance_date || selected_date;

		$("#lab-date-bs").text(date_bs_base);
		$("#lab-date-ad").text(
			data.attendance_date
				? `AD: ${frappe.datetime.str_to_user(data.attendance_date)}`
				: ""
		);
		$("#lab-leave-label").text(viewing_today ? __("On Leave (Today)") : __("On Leave"));
		$("#lab-today-btn").toggleClass("btn-primary-light", !viewing_today);

		const column_keys = ["pending", "active", "completed", "leave", "upcoming", "pending_leave"];

		column_keys.forEach((key) => {
			let container = $(`#col-${key}`);
			let counter = $(`#count-${key}`);
			let dept_groups = data[key] || {};

			container.empty();
			let total_count = 0;

			let depts = Object.keys(dept_groups).sort();

			if (depts.length === 0) {
				container.append('<div class="lab-empty">0 Employees</div>');
			} else {
				depts.forEach((dept) => {
					let emps = dept_groups[dept];
					total_count += emps.length;

					container.append(`
                        <div class="lab-dept-header" data-dept="${dept}" data-col="${key}">
                            <span><i class="fa fa-chevron-down fold-icon"></i> ${dept}</span>
                            <span style="opacity:0.7;">${emps.length}</span>
                        </div>
                        <div class="lab-dept-body">
                            ${emps.map((emp) => generate_card(emp)).join("")}
                        </div>
                    `);
				});
			}
			counter.text(total_count);
		});
	}

	page.body.on("click", ".lab-dept-header", function () {
		$(this).toggleClass("collapsed");
	});

	page.body.on("click", "#lab-refresh-btn", function () {
		let btn = $(this);
		btn.prop("disabled", true).find("i").addClass("fa-spin");
		load_board();
		setTimeout(() => {
			btn.prop("disabled", false).find("i").removeClass("fa-spin");
		}, 1000);
	});

	page.body.on("click", "#lab-today-btn", function () {
		const today = frappe.datetime.get_today();
		if (selected_date === today) {
			load_board();
			return;
		}
		selected_date = today;
		date_control.set_value(today);
		load_board();
	});

	load_board();
};
