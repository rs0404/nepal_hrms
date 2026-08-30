import frappe
from frappe.utils import nowdate, getdate
import nepal_compliance.nepali_date_utils.nepali_date as nepali_date


@frappe.whitelist()
def get_live_data(attendance_date=None):
	day = getdate(attendance_date) if attendance_date else getdate(nowdate())
	day_str = str(day)
	today_str = nowdate()
	day_bs = nepali_date.format_bs(day)

	# 1. Active employees not yet relieved as of selected day
	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		or_filters=[
			["relieving_date", "is", "not set"],
			["relieving_date", ">=", day_str],
		],
		fields=["name", "employee_name", "department", "date_of_joining"],
		order_by="department asc, employee_name asc",
		ignore_permissions=True,
	)
	employees = [
		e for e in employees
		if not e.date_of_joining or str(e.date_of_joining) <= day_str
	]

	# 2. Checkins for selected day
	checkins = frappe.get_all(
		"Employee Checkin",
		filters={"time": ["between", [f"{day_str} 00:00:00", f"{day_str} 23:59:59"]]},
		fields=["employee", "time", "log_type", "custom_attendance_type"],
		order_by="time asc",
		ignore_permissions=True,
	)

	# 3. Approved leaves overlapping / after selected day
	leaves = frappe.get_all(
		"Leave Application",
		filters={"status": "Approved", "docstatus": 1, "to_date": [">=", day_str]},
		fields=["employee", "from_date", "to_date", "leave_type", "half_day", "half_day_date"],
		ignore_permissions=True,
	)

	# 4. Unapproved leaves (Pending Approval) still relevant on/after selected day
	unapproved_leaves = frappe.get_all(
		"Leave Application",
		filters={
			"docstatus": 0,
			"status": ["not in", ["Rejected", "Cancelled"]],
			"to_date": [">=", day_str],
		},
		fields=["employee", "from_date", "to_date", "leave_type", "half_day", "half_day_date"],
		ignore_permissions=True,
	)

	checkin_map = {}
	for c in checkins:
		if c.employee not in checkin_map:
			checkin_map[c.employee] = []

		type_prefix = "OOO " if c.custom_attendance_type == "OOO Work" else ""
		type_str = f" ({type_prefix}{c.log_type})" if c.log_type in ("IN", "OUT") else ""
		checkin_map[c.employee].append(f"{c.time.hour:02d}:{c.time.minute:02d}{type_str}")

	leave_map_today = {}
	leave_map_future = {}
	leave_map_pending = {}

	for l in leaves:
		from_bs = nepali_date.format_bs(l.from_date)
		to_bs = nepali_date.format_bs(l.to_date)
		half_lbl = " - Half Day" if l.half_day else ""
		lbl = f"{from_bs} ~ {to_bs} ({l.leave_type}){half_lbl}"

		if str(l.from_date) <= day_str <= str(l.to_date):
			leave_map_today[l.employee] = lbl

		if str(l.to_date) > day_str:
			if l.employee not in leave_map_future:
				leave_map_future[l.employee] = []
			if lbl not in leave_map_future[l.employee]:
				leave_map_future[l.employee].append(lbl)

	for l in unapproved_leaves:
		from_bs = nepali_date.format_bs(l.from_date)
		to_bs = nepali_date.format_bs(l.to_date)
		half_lbl = " - Half Day" if l.half_day else ""
		lbl = f"{from_bs} ~ {to_bs} ({l.leave_type}){half_lbl}"

		if l.employee not in leave_map_pending:
			leave_map_pending[l.employee] = []
		if lbl not in leave_map_pending[l.employee]:
			leave_map_pending[l.employee].append(lbl)

	data = {
		"today_bs": day_bs,
		"attendance_date": day_str,
		"is_today": day_str == today_str,
		"pending": {},
		"active": {},
		"completed": {},
		"leave": {},
		"upcoming": {},
		"pending_leave": {},
	}

	def add_to_group(category, dept, emp_data):
		if not dept:
			dept = "No Department"
		if dept not in data[category]:
			data[category][dept] = []
		data[category][dept].append(emp_data)

	for emp in employees:
		punches = checkin_map.get(emp.name, [])
		emp.punches = punches
		dept = emp.department

		if emp.name in leave_map_today:
			emp.punches = [leave_map_today[emp.name]]
			add_to_group("leave", dept, emp)
		elif not punches:
			add_to_group("pending", dept, emp)
		else:
			last_punch = punches[-1]
			if "(OUT)" in last_punch:
				add_to_group("completed", dept, emp)
			else:
				add_to_group("active", dept, emp)

		if emp.name in leave_map_future:
			future_emp = emp.copy()
			future_emp.punches = leave_map_future[emp.name]
			add_to_group("upcoming", dept, future_emp)

		if emp.name in leave_map_pending:
			pending_emp = emp.copy()
			pending_emp.punches = leave_map_pending[emp.name]
			add_to_group("pending_leave", dept, pending_emp)

	return data
