# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate, now_datetime, today
from hrms.hr.utils import get_distance_between_coordinates


@frappe.whitelist()
def start_ooo_work(employee, reason=None, latitude=None, longitude=None, manual_time=None):
    """
    Create an OOO Work check-in (employee is starting OOO Work).
    """
    if not reason:
        frappe.throw(_("A reason is required when starting OOO Work."))

    employee_doc = frappe.get_doc("Employee", employee)
    _validate_employee_permission(employee_doc)

    timestamp = get_datetime(manual_time) if manual_time else now_datetime()

    # Create the OOO IN check-in log
    checkin = frappe.get_doc({
        "doctype": "Employee Checkin",
        "employee": employee,
        "employee_name": employee_doc.employee_name,
        "log_type": "IN",
        "time": timestamp,
        "custom_attendance_type": "OOO Work",
        "custom_reason": reason,
        "latitude": latitude,
        "longitude": longitude,
    })
    checkin.insert(ignore_permissions=True)

    return {
        "checkin": checkin.name,
        "message": _("OOO Work session started. GPS tracking will begin."),
        "timestamp": str(timestamp)
    }


@frappe.whitelist()
def end_ooo_work(employee, reason=None, latitude=None, longitude=None, manual_time=None):
    """
    Create the OOO Work check-out (employee is ending OOO Work).
    """
    if not reason:
        frappe.throw(_("A reason is required when ending OOO Work."))

    employee_doc = frappe.get_doc("Employee", employee)
    _validate_employee_permission(employee_doc)

    timestamp = get_datetime(manual_time) if manual_time else now_datetime()

    # Verify there's an active OOO session
    active_ooo = _get_active_ooo_session(employee)
    if not active_ooo:
        frappe.throw(_("No active OOO Work session found to end."))

    # Create the OOO OUT check-in log
    checkin = frappe.get_doc({
        "doctype": "Employee Checkin",
        "employee": employee,
        "employee_name": employee_doc.employee_name,
        "log_type": "OUT",
        "time": timestamp,
        "custom_attendance_type": "OOO Work",
        "custom_reason": reason,
        "latitude": latitude,
        "longitude": longitude,
    })
    checkin.insert(ignore_permissions=True)

    return {
        "checkin": checkin.name,
        "message": _("OOO Work session ended. Welcome back!"),
        "timestamp": str(timestamp)
    }


@frappe.whitelist()
def log_gps_position(employee, checkin_reference=None, latitude=None, longitude=None, accuracy=None):
    """
    Log a GPS position to Employee Path Log during an active OOO session.
    Called periodically by the PWA.
    """
    if not latitude or not longitude:
        frappe.throw(_("Latitude and longitude are required for GPS logging."))

    path_log = frappe.get_doc({
        "doctype": "Employee Path Log",
        "employee": employee,
        "checkin_reference": checkin_reference,
        "timestamp": now_datetime(),
        "latitude": float(latitude),
        "longitude": float(longitude),
        "accuracy": float(accuracy) if accuracy else 0,
    })
    path_log.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"path_log": path_log.name}


@frappe.whitelist()
def recalculate_attendance_from_checkins(employee, attendance_date):
	"""Rebuild Attendance hours/status from all check-ins for the day."""
	from nepal_hrms.overrides.attendance_override import sync_attendance_hours_from_checkins

	frappe.has_permission("Attendance", "write", throw=True)
	attendance = sync_attendance_hours_from_checkins(employee, getdate(attendance_date))
	if not attendance:
		frappe.throw(_("No attendance found for {0} on {1}.").format(employee, attendance_date))
	return {
		"message": _("Attendance recalculated from check-ins."),
		"attendance": attendance.name,
		"status": attendance.status,
		"working_hours": attendance.working_hours,
		"in_time": str(attendance.in_time) if attendance.in_time else None,
		"out_time": str(attendance.out_time) if attendance.out_time else None,
	}


@frappe.whitelist()
def approve_ooo_checkins(employee, attendance_date):
	"""
	Leave Approver approves OOO check-ins for a given date.
	Marks OOO check-ins approved, recalculates working hours (Normal + OOO),
	clears OOO hold, and submits/updates Attendance.
	"""
	_assert_is_leave_approver(employee, attendance_date)

	attendance_date = getdate(attendance_date)
	checkin_meta = frappe.get_meta("Employee Checkin")

	filters = {
		"employee": employee,
		"time": ["between", [f"{attendance_date} 00:00:00", f"{attendance_date} 23:59:59"]],
		"custom_attendance_type": "OOO Work",
	}
	if checkin_meta.has_field("custom_ooo_rejected"):
		filters["custom_ooo_rejected"] = 0

	ooo_checkins = frappe.get_all(
		"Employee Checkin",
		filters=filters,
		pluck="name",
	)

	if not ooo_checkins:
		frappe.throw(_("No OOO Work check-ins found for {0} on {1}.").format(employee, attendance_date))

	for checkin_name in ooo_checkins:
		updates = {"custom_is_approved": 1}
		if checkin_meta.has_field("custom_ooo_rejected"):
			updates["custom_ooo_rejected"] = 0
		if checkin_meta.has_field("custom_ooo_rejection_reason"):
			updates["custom_ooo_rejection_reason"] = ""
		frappe.db.set_value("Employee Checkin", checkin_name, updates)

	# All check-ins for the day (after approval flags set)
	all_checkins = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"time": ["between", [f"{attendance_date} 00:00:00", f"{attendance_date} 23:59:59"]],
		},
		fields=["time", "log_type", "custom_attendance_type", "custom_is_approved", "shift"],
		order_by="time asc",
	)

	total_worked_seconds = 0
	last_in_time = None
	first_in = None
	last_out = None
	shift_name = None

	for c in all_checkins:
		# Count Normal always; OOO only when approved (just set above)
		counts = (c.custom_attendance_type or "Normal") != "OOO Work" or cint(c.custom_is_approved)
		if not counts:
			continue
		if c.shift and not shift_name:
			shift_name = c.shift
		if c.log_type == "IN":
			last_in_time = c.time
			if first_in is None:
				first_in = c.time
		elif c.log_type == "OUT" and last_in_time:
			diff = (c.time - last_in_time).total_seconds()
			total_worked_seconds += diff
			last_out = c.time
			last_in_time = None

	total_hours = round(total_worked_seconds / 3600.0, 2)

	from nepal_hrms.custom_code.attendance_policy import calculate_ooo_hours_from_checkins
	from nepal_hrms.overrides.attendance_override import _status_from_hours

	ooo_hours = calculate_ooo_hours_from_checkins(employee, attendance_date, approved_only=True)
	has_normal = any((c.custom_attendance_type or "Normal") != "OOO Work" for c in all_checkins)
	new_status = _status_from_hours(total_hours, shift_name)
	if not has_normal and total_hours > 0:
		new_status = "Present"

	attendance_name = frappe.db.get_value(
		"Attendance",
		{"employee": employee, "attendance_date": attendance_date, "docstatus": ["<", 2]},
	)

	values = {
		"working_hours": total_hours,
		"status": new_status,
		"custom_ooo_hold": 0,
		"custom_has_ooo_logs": 1,
		"in_time": first_in,
		"out_time": last_out,
	}
	if frappe.get_meta("Attendance").has_field("custom_ooo_hours"):
		values["custom_ooo_hours"] = ooo_hours
	if shift_name:
		values["shift"] = shift_name

	if attendance_name:
		attendance = frappe.get_doc("Attendance", attendance_name)

		if attendance.docstatus == 0:
			for key, val in values.items():
				setattr(attendance, key, val)
			attendance.flags.ignore_validate = True
			attendance.save(ignore_permissions=True)
			# Hold cleared — allow submit
			attendance.flags.ignore_validate = True
			attendance.submit()
		else:
			# Already submitted: update hours/status in DB (cannot re-submit)
			frappe.db.set_value("Attendance", attendance.name, values)

		# Link any OOO checkins still missing attendance link
		for checkin_name in ooo_checkins:
			frappe.db.set_value(
				"Employee Checkin",
				checkin_name,
				"attendance",
				attendance_name,
				update_modified=False,
			)

		frappe.db.commit()
		return {
			"message": _("OOO check-ins approved and attendance updated."),
			"working_hours": total_hours,
			"ooo_hours": ooo_hours,
			"status": new_status,
			"attendance": attendance_name,
		}

	# No attendance yet — create and submit
	attendance = frappe.new_doc("Attendance")
	attendance.update(
		{
			"employee": employee,
			"attendance_date": attendance_date,
			"status": new_status,
			"working_hours": total_hours,
			"custom_ooo_hold": 0,
			"custom_has_ooo_logs": 1,
			"custom_ooo_hours": ooo_hours,
			"in_time": first_in,
			"out_time": last_out,
			"shift": shift_name,
		}
	)
	attendance.insert(ignore_permissions=True)
	attendance.submit()
	for checkin_name in ooo_checkins:
		frappe.db.set_value(
			"Employee Checkin",
			checkin_name,
			"attendance",
			attendance.name,
			update_modified=False,
		)
	frappe.db.commit()
	return {
		"message": _("OOO check-ins approved and attendance record created."),
		"working_hours": total_hours,
		"ooo_hours": ooo_hours,
		"status": new_status,
		"attendance": attendance.name,
	}


@frappe.whitelist()
def reject_ooo_checkins(employee, attendance_date, reason=None):
	"""
	Leave Approver rejects OOO check-ins for a date (with reason).
	OOO hours are excluded; Normal attendance (if any) is recalculated; hold is cleared.
	"""
	if not reason or not str(reason).strip():
		frappe.throw(_("A rejection reason is required."))

	_assert_is_leave_approver(employee, attendance_date)

	attendance_date = getdate(attendance_date)
	reason = str(reason).strip()

	ooo_checkins = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"time": ["between", [f"{attendance_date} 00:00:00", f"{attendance_date} 23:59:59"]],
			"custom_attendance_type": "OOO Work",
			"custom_is_approved": 0,
		},
		pluck="name",
	)
	if not ooo_checkins:
		frappe.throw(_("No pending OOO Work check-ins found for {0} on {1}.").format(employee, attendance_date))

	meta = frappe.get_meta("Employee Checkin")
	for checkin_name in ooo_checkins:
		updates = {"custom_is_approved": 0}
		if meta.has_field("custom_ooo_rejected"):
			updates["custom_ooo_rejected"] = 1
		if meta.has_field("custom_ooo_rejection_reason"):
			updates["custom_ooo_rejection_reason"] = reason
		frappe.db.set_value("Employee Checkin", checkin_name, updates)

	# Recalculate from Normal check-ins only (OOO excluded)
	normal_checkins = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"time": ["between", [f"{attendance_date} 00:00:00", f"{attendance_date} 23:59:59"]],
		},
		fields=["time", "log_type", "custom_attendance_type", "shift"],
		order_by="time asc",
	)

	total_worked_seconds = 0
	last_in_time = None
	first_in = None
	last_out = None
	shift_name = None
	has_normal = False

	for c in normal_checkins:
		if (c.custom_attendance_type or "Normal") == "OOO Work":
			continue
		has_normal = True
		if c.shift and not shift_name:
			shift_name = c.shift
		if c.log_type == "IN":
			last_in_time = c.time
			if first_in is None:
				first_in = c.time
		elif c.log_type == "OUT" and last_in_time:
			total_worked_seconds += (c.time - last_in_time).total_seconds()
			last_out = c.time
			last_in_time = None

	total_hours = round(total_worked_seconds / 3600.0, 2)

	from nepal_hrms.overrides.attendance_override import _status_from_hours

	if has_normal:
		new_status = _status_from_hours(total_hours, shift_name)
	else:
		# Only rejected OOO — mark Absent (no countable work)
		new_status = "Absent"
		total_hours = 0
		first_in = None
		last_out = None

	attendance_name = frappe.db.get_value(
		"Attendance",
		{"employee": employee, "attendance_date": attendance_date, "docstatus": ["<", 2]},
	)

	values = {
		"working_hours": total_hours,
		"status": new_status,
		"custom_ooo_hold": 0,
		"custom_has_ooo_logs": 1,
		"in_time": first_in,
		"out_time": last_out,
	}
	att_meta = frappe.get_meta("Attendance")
	if att_meta.has_field("custom_ooo_hours"):
		values["custom_ooo_hours"] = 0
	if shift_name:
		values["shift"] = shift_name

	if attendance_name:
		attendance = frappe.get_doc("Attendance", attendance_name)
		if attendance.docstatus == 0:
			for key, val in values.items():
				setattr(attendance, key, val)
			attendance.flags.ignore_validate = True
			attendance.save(ignore_permissions=True)
			if has_normal:
				attendance.flags.ignore_validate = True
				attendance.submit()
		else:
			frappe.db.set_value("Attendance", attendance.name, values)
	elif has_normal:
		attendance = frappe.new_doc("Attendance")
		attendance.update(
			{
				"employee": employee,
				"attendance_date": attendance_date,
				**values,
			}
		)
		attendance.insert(ignore_permissions=True)
		attendance.submit()
		attendance_name = attendance.name

	frappe.db.commit()
	return {
		"message": _("OOO check-ins rejected."),
		"status": new_status,
		"working_hours": total_hours,
		"attendance": attendance_name,
		"reason": reason,
	}


@frappe.whitelist()
def get_ooo_status(employee):
    """
    Returns the current OOO state for the employee.
    Used by the PWA to determine UI state (active/inactive OOO session).
    """
    active_session = _get_active_ooo_session(employee)

    # Get GPS tracking interval from HR Settings
    gps_interval = frappe.db.get_single_value("HR Settings", "custom_gps_tracking_interval") or 300

    if active_session:
        return {
            "is_active": True,
            "session_start": str(active_session.time),
            "checkin_reference": active_session.name,
            "reason": active_session.custom_reason or "",
            "gps_interval": gps_interval,
        }

    return {
        "is_active": False,
        "gps_interval": gps_interval,
    }


@frappe.whitelist()
def get_pending_ooo_approvals():
	"""OOO board for PWA: pending + approved reportees, plus own OOO.

	Pending/approved lists include the employees whose approvals reach the
	current user: their Leave Approver or anyone above that approver in Reports
	To (see approval_authority). Not all employees for HR.
	"""
	from frappe.utils import add_days

	from nepal_hrms.custom_code.approval_authority import approvable_employees

	user = frappe.session.user
	my_emp = frappe.db.get_value("Employee", {"user_id": user}, ["name", "employee_name"], as_dict=True)

	team = approvable_employees(user)
	reportees = (
		frappe.get_all(
			"Employee",
			filters={"name": ["in", team]},
			fields=["name", "employee_name"],
		)
		if team
		else []
	)

	employee_map = {e["name"]: e["employee_name"] for e in reportees}
	reportee_ids = list(employee_map.keys())

	from_date = add_days(today(), -60)

	pending, approved = [], []
	if reportee_ids:
		days = _collect_ooo_days(reportee_ids, employee_map, from_date=from_date)
		for item in days:
			if item["approval_status"] == "Pending":
				pending.append(item)
			elif item["approval_status"] == "Approved":
				approved.append(item)

	mine = []
	if my_emp:
		mine = _collect_ooo_days(
			[my_emp.name],
			{my_emp.name: my_emp.employee_name},
			from_date=from_date,
			include_rejected=True,
		)

	# Newest first; cap each section
	def _sort_cap(rows, limit=20):
		rows.sort(key=lambda r: r["attendance_date"], reverse=True)
		return rows[:limit]

	return {
		"pending": _sort_cap(pending),
		"approved": _sort_cap(approved),
		"mine": _sort_cap(mine),
	}


def _collect_ooo_days(employee_ids, employee_map, from_date=None, include_rejected=False):
	"""Group OOO check-ins into one row per employee+date with approval_status."""
	from frappe.utils import add_days

	if not employee_ids:
		return []

	from_date = getdate(from_date or add_days(today(), -60))
	checkin_meta = frappe.get_meta("Employee Checkin")
	has_rejected = checkin_meta.has_field("custom_ooo_rejected")

	fields = [
		"name",
		"employee",
		"time",
		"log_type",
		"custom_is_approved",
	]
	if has_rejected:
		fields.append("custom_ooo_rejected")

	filters = {
		"employee": ["in", employee_ids],
		"custom_attendance_type": "OOO Work",
		"time": [">=", f"{from_date} 00:00:00"],
		"docstatus": ["<", 2],
	}

	rows = frappe.get_all(
		"Employee Checkin",
		filters=filters,
		fields=fields,
		order_by="time asc",
		limit_page_length=2000,
	)

	grouped = {}
	for c in rows:
		rejected = cint(getattr(c, "custom_ooo_rejected", 0)) if has_rejected else 0
		if rejected and not include_rejected:
			continue
		day = getdate(c.time)
		key = (c.employee, day)
		bucket = grouped.setdefault(
			key,
			{
				"employee": c.employee,
				"employee_name": employee_map.get(c.employee),
				"attendance_date": day,
				"has_pending": False,
				"has_approved": False,
				"has_rejected": False,
				"ooo_seconds": 0,
				"_last_in": None,
			},
		)
		if rejected:
			bucket["has_rejected"] = True
		elif cint(c.custom_is_approved):
			bucket["has_approved"] = True
		else:
			bucket["has_pending"] = True

		if c.log_type == "IN":
			bucket["_last_in"] = c.time
		elif c.log_type == "OUT" and bucket["_last_in"]:
			bucket["ooo_seconds"] += (c.time - bucket["_last_in"]).total_seconds()
			bucket["_last_in"] = None

	# Attendance names for display
	attendance_map = {}
	if grouped:
		att_rows = frappe.get_all(
			"Attendance",
			filters={
				"employee": ["in", employee_ids],
				"attendance_date": ["in", list({d for _, d in grouped.keys()})],
				"docstatus": ["<", 2],
			},
			fields=["name", "employee", "attendance_date", "working_hours"],
		)
		for a in att_rows:
			attendance_map[(a.employee, getdate(a.attendance_date))] = a

	result = []
	for key, bucket in grouped.items():
		if bucket["has_pending"]:
			status = "Pending"
		elif bucket["has_approved"]:
			status = "Approved"
		elif bucket["has_rejected"]:
			status = "Rejected"
		else:
			continue

		att = attendance_map.get(key)
		ooo_hours = round(bucket["ooo_seconds"] / 3600.0, 2)
		result.append(
			{
				"name": (att.name if att else None) or f"OOO-{bucket['employee']}-{bucket['attendance_date']}",
				"employee": bucket["employee"],
				"employee_name": bucket["employee_name"],
				"attendance_date": str(bucket["attendance_date"]),
				"working_hours": ooo_hours
				if ooo_hours
				else round(float(att.working_hours or 0), 2)
				if att
				else 0.0,
				"approval_status": status,
				"can_approve": status == "Pending",
			}
		)
	return result


@frappe.whitelist()
def update_pending_ooo_checkin_times(employee, attendance_date, checkins):
	"""Correct pending OOO IN/OUT timestamps before approval.

	Only the employee's configured Leave Approver (or Administrator) can edit,
	and records cannot be moved to another calendar day.
	"""
	if not employee or not attendance_date:
		frappe.throw(_("Employee and attendance date are required."))

	_assert_is_leave_approver(employee, attendance_date)
	attendance_date = getdate(attendance_date)
	if isinstance(checkins, str):
		checkins = frappe.parse_json(checkins)
	if not isinstance(checkins, list) or not checkins:
		frappe.throw(_("At least one check-in time is required."))

	names = [row.get("name") for row in checkins if isinstance(row, dict) and row.get("name")]
	if len(names) != len(checkins) or len(set(names)) != len(names):
		frappe.throw(_("Invalid or duplicate check-in records."))

	meta = frappe.get_meta("Employee Checkin")
	filters = {
		"name": ["in", names],
		"employee": employee,
		"custom_attendance_type": "OOO Work",
		"custom_is_approved": 0,
		"docstatus": ["<", 2],
	}
	if meta.has_field("custom_ooo_rejected"):
		filters["custom_ooo_rejected"] = 0

	existing = frappe.get_all(
		"Employee Checkin",
		filters=filters,
		fields=["name", "time", "log_type"],
	)
	existing_by_name = {row.name: row for row in existing}
	if set(existing_by_name) != set(names):
		frappe.throw(
			_("One or more check-ins are no longer pending or do not belong to this employee."),
			frappe.PermissionError,
		)

	updates = []
	for row in checkins:
		name = row["name"]
		new_time = get_datetime(row.get("time"))
		if getdate(new_time) != attendance_date:
			frappe.throw(_("OOO check-in times must remain on {0}.").format(attendance_date))
		old_time = get_datetime(existing_by_name[name].time)
		if new_time != old_time:
			updates.append((name, old_time, new_time))

	# Validate each complete OOO session after applying the proposed times.
	proposed = {name: new_time for name, _old_time, new_time in updates}
	day_rows = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"custom_attendance_type": "OOO Work",
			"time": [
				"between",
				[f"{attendance_date} 00:00:00", f"{attendance_date} 23:59:59"],
			],
			"docstatus": ["<", 2],
		},
		fields=["name", "time", "log_type"],
	)
	for row in day_rows:
		row.time = proposed.get(row.name, get_datetime(row.time))
	day_rows.sort(key=lambda row: row.time)
	open_in = None
	for row in day_rows:
		if row.log_type == "IN":
			open_in = row
		elif row.log_type == "OUT" and open_in:
			if row.time <= open_in.time:
				frappe.throw(_("OOO check-out must be later than its check-in."))
			open_in = None

	for name, old_time, new_time in updates:
		frappe.db.set_value(
			"Employee Checkin",
			name,
			"time",
			new_time,
			update_modified=True,
		)
		try:
			frappe.get_doc("Employee Checkin", name).add_comment(
				"Edit",
				_("OOO time corrected by {0}: {1} → {2}").format(
					frappe.session.user, old_time, new_time
				),
			)
		except Exception:
			frappe.logger("nepal_hrms.ooo").info(
				"OOO time corrected by %s: %s %s -> %s",
				frappe.session.user,
				name,
				old_time,
				new_time,
			)

	frappe.db.commit()
	return {
		"updated": len(updates),
		"employee": employee,
		"attendance_date": str(attendance_date),
	}


@frappe.whitelist()
def get_ooo_approval_details(employee, attendance_date):
	"""Attendance + all day check-ins for an OOO approval detail sheet."""
	if not employee or not attendance_date:
		frappe.throw(_("Employee and attendance date are required."))

	_assert_can_view_ooo_day(employee)

	attendance_date = getdate(attendance_date)
	employee_name = frappe.db.get_value("Employee", employee, "employee_name") or employee
	day_start = f"{attendance_date} 00:00:00"
	day_end = f"{attendance_date} 23:59:59"

	att_fields = [
		"name",
		"status",
		"docstatus",
		"in_time",
		"out_time",
		"working_hours",
		"shift",
		"late_entry",
		"early_exit",
	]
	att_meta = frappe.get_meta("Attendance")
	for f in ("custom_ooo_hold", "custom_ooo_hours", "custom_has_ooo_logs"):
		if att_meta.has_field(f):
			att_fields.append(f)

	attendance_row = frappe.db.get_value(
		"Attendance",
		{
			"employee": employee,
			"attendance_date": attendance_date,
			"docstatus": ["<", 2],
		},
		att_fields,
		as_dict=True,
	)

	checkin_fields = [
		"name",
		"time",
		"log_type",
		"custom_attendance_type",
		"custom_reason",
		"custom_is_approved",
		"device_id",
		"latitude",
		"longitude",
	]
	checkin_meta = frappe.get_meta("Employee Checkin")
	if checkin_meta.has_field("custom_ooo_rejected"):
		checkin_fields.append("custom_ooo_rejected")

	raw_checkins = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"time": ["between", [day_start, day_end]],
			"docstatus": ["<", 2],
		},
		fields=checkin_fields,
		order_by="time asc",
	)

	assignment_filters = {
		"employee": employee,
		"start_date": ["<=", attendance_date],
		"shift_location": ["is", "set"],
		"docstatus": 1,
		"status": "Active",
	}
	if attendance_row and attendance_row.shift:
		assignment_filters["shift_type"] = attendance_row.shift
	shift_assignment = frappe.get_all(
		"Shift Assignment",
		filters=assignment_filters,
		or_filters=[
			["end_date", ">=", attendance_date],
			["end_date", "is", "not set"],
		],
		fields=["shift_location"],
		order_by="start_date desc",
		limit_page_length=1,
	)
	shift_location = None
	if shift_assignment:
		location = frappe.db.get_value(
			"Shift Location",
			shift_assignment[0].shift_location,
			["name", "location_name", "latitude", "longitude", "checkin_radius"],
			as_dict=True,
		)
		if location and location.latitude is not None and location.longitude is not None:
			shift_location = {
				"name": location.name,
				"location_name": location.location_name,
				"latitude": float(location.latitude),
				"longitude": float(location.longitude),
				"checkin_radius": cint(location.checkin_radius),
			}

	checkins = []
	ooo_checkins = []
	ooo_seconds = 0
	last_ooo_in = None

	for c in raw_checkins:
		att_type = (c.custom_attendance_type or "Normal").strip() or "Normal"
		is_ooo = att_type == "OOO Work"
		rejected = cint(getattr(c, "custom_ooo_rejected", 0))
		entry = {
			"name": c.name,
			"time": str(c.time),
			"log_type": c.log_type,
			"attendance_type": att_type,
			"reason": c.custom_reason or "",
			"is_approved": cint(c.custom_is_approved),
			"is_rejected": rejected,
			"is_ooo": is_ooo,
			"device_id": c.device_id or "",
			"has_location": bool(c.latitude and c.longitude),
			"latitude": float(c.latitude) if c.latitude is not None else None,
			"longitude": float(c.longitude) if c.longitude is not None else None,
		}
		if (
			shift_location
			and entry["latitude"] is not None
			and entry["longitude"] is not None
		):
			entry["distance_from_shift_location_m"] = round(
				get_distance_between_coordinates(
					shift_location["latitude"],
					shift_location["longitude"],
					entry["latitude"],
					entry["longitude"],
				)
			)
		else:
			entry["distance_from_shift_location_m"] = None
		checkins.append(entry)

		if is_ooo and not rejected:
			ooo_checkins.append(entry)
			if c.log_type == "IN":
				last_ooo_in = get_datetime(c.time)
			elif c.log_type == "OUT" and last_ooo_in:
				ooo_seconds += (get_datetime(c.time) - last_ooo_in).total_seconds()
				last_ooo_in = None

	attendance = None
	if attendance_row:
		attendance = {
			"name": attendance_row.name,
			"status": attendance_row.status,
			"docstatus": cint(attendance_row.docstatus),
			"in_time": str(attendance_row.in_time) if attendance_row.in_time else None,
			"out_time": str(attendance_row.out_time) if attendance_row.out_time else None,
			"working_hours": round(float(attendance_row.working_hours or 0), 2),
			"shift": attendance_row.shift or "",
			"late_entry": cint(attendance_row.late_entry),
			"early_exit": cint(attendance_row.early_exit),
			"ooo_hold": cint(getattr(attendance_row, "custom_ooo_hold", 0)),
			"ooo_hours": round(float(getattr(attendance_row, "custom_ooo_hours", 0) or 0), 2),
		}

	first_in = next((c for c in checkins if c["log_type"] == "IN"), None)
	last_out = next((c for c in reversed(checkins) if c["log_type"] == "OUT"), None)

	pending_count = len([c for c in ooo_checkins if not c["is_approved"]])
	can_approve = _is_leave_approver_for(employee, attendance_date) and pending_count > 0
	emp_user = frappe.db.get_value("Employee", employee, "user_id")
	is_own = bool(emp_user and emp_user == frappe.session.user)

	if pending_count:
		approval_status = "Pending"
	elif any(c["is_approved"] for c in ooo_checkins):
		approval_status = "Approved"
	elif any(c["is_rejected"] for c in checkins if c["is_ooo"]):
		approval_status = "Rejected"
	else:
		approval_status = "Pending"

	path_logs = frappe.get_all(
		"Employee Path Log",
		filters={
			"employee": employee,
			"timestamp": ["between", [day_start, day_end]],
		},
		fields=["name", "checkin_reference", "timestamp", "latitude", "longitude", "accuracy"],
		order_by="timestamp asc",
		limit_page_length=2000,
	)
	path_points = [
		{
			"name": row.name,
			"checkin_reference": row.checkin_reference,
			"timestamp": str(row.timestamp),
			"latitude": float(row.latitude),
			"longitude": float(row.longitude),
			"accuracy": float(row.accuracy or 0),
		}
		for row in path_logs
	]
	employee_user = frappe.db.get_value("Employee", employee, "user_id")

	return {
		"employee": employee,
		"employee_name": employee_name,
		"attendance_date": str(attendance_date),
		"attendance": attendance,
		"working_hours": (attendance or {}).get("working_hours")
		or round(ooo_seconds / 3600.0, 2),
		"ooo_hours": round(ooo_seconds / 3600.0, 2),
		"first_in": first_in["time"] if first_in else None,
		"last_out": last_out["time"] if last_out else None,
		"checkins": checkins,
		"ooo_checkins": ooo_checkins,
		"shift_location": shift_location,
		"pending_count": pending_count,
		"can_approve": can_approve,
		"is_own": is_own,
		"approval_status": approval_status,
		"path_points": path_points,
		"employee_user": employee_user,
	}


def _get_ooo_attendance_for_comment(employee, attendance_date):
	_assert_can_view_ooo_day(employee)
	name = frappe.db.get_value(
		"Attendance",
		{
			"employee": employee,
			"attendance_date": getdate(attendance_date),
			"docstatus": ["<", 2],
		},
	)
	if not name:
		frappe.throw(_("No Attendance record exists for this employee and date."))
	return name


@frappe.whitelist()
def get_ooo_attendance_comments(employee, attendance_date):
	"""Return Attendance comments visible from the OOO review sheet."""
	attendance = _get_ooo_attendance_for_comment(employee, attendance_date)
	comments = frappe.get_all(
		"Comment",
		filters={
			"reference_doctype": "Attendance",
			"reference_name": attendance,
			"comment_type": "Comment",
		},
		fields=["name", "comment_by", "comment_email", "content", "creation"],
		order_by="creation asc",
	)
	for comment in comments:
		comment["full_name"] = (
			frappe.db.get_value("User", comment.comment_email, "full_name")
			or comment.comment_by
			or comment.comment_email
		)
	return {"attendance": attendance, "comments": comments}


@frappe.whitelist()
def add_ooo_attendance_comment(employee, attendance_date, content, mention_employee=1):
	"""Add a plain-text Attendance comment and optionally mention the employee."""
	from frappe.utils import escape_html

	attendance = _get_ooo_attendance_for_comment(employee, attendance_date)
	content = (content or "").strip()
	if not content:
		frappe.throw(_("Comment cannot be empty."))

	safe_content = escape_html(content).replace("\n", "<br>")
	if cint(mention_employee):
		employee_user = frappe.db.get_value("Employee", employee, "user_id")
		if employee_user:
			full_name = frappe.db.get_value("User", employee_user, "full_name") or employee_user
			safe_user = escape_html(employee_user)
			safe_name = escape_html(full_name)
			mention = (
				f'<span class="mention" data-id="{safe_user}" data-value="{safe_name}" '
				f'data-denotation-char="@">@{safe_name}</span>'
			)
			safe_content = f"{mention} {safe_content}"

	comment = frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Comment",
			"reference_doctype": "Attendance",
			"reference_name": attendance,
			"comment_email": frappe.session.user,
			"comment_by": frappe.utils.get_fullname(frappe.session.user),
			"content": safe_content,
		}
	)
	comment.insert(ignore_permissions=True)
	return {"name": comment.name, "attendance": attendance, "creation": comment.creation}


def _prevent_self_ooo_checkin_approval() -> bool:
	"""Nepal HRMS Settings: block employees from approving their own OOO check-ins.

	Default True when the field is missing so existing sites stay protected.
	"""
	if not frappe.db.exists("DocType", "Nepal HRMS Settings"):
		return True
	meta = frappe.get_meta("Nepal HRMS Settings")
	if not meta.has_field("prevent_self_ooo_checkin_approval"):
		return True
	value = frappe.db.get_single_value(
		"Nepal HRMS Settings", "prevent_self_ooo_checkin_approval"
	)
	return True if value is None else bool(cint(value))


def _is_own_employee(employee: str) -> bool:
	emp_user = frappe.db.get_value("Employee", employee, "user_id")
	return bool(emp_user and emp_user == frappe.session.user)


def _is_leave_approver_for(employee: str, on_date=None) -> bool:
	"""True if current user may approve OOO check-ins for this employee.

	The Leave Approver or anyone above them in Reports To. Self-approval needs
	an Allow Self-Approval policy escape, or the site's prevent-self setting off.
	"""
	from nepal_hrms.custom_code.approval_authority import can_approve

	return can_approve(
		employee,
		on_date=on_date,
		site_allows_self=not _prevent_self_ooo_checkin_approval(),
	)


def _assert_is_leave_approver(employee: str, on_date=None):
	from nepal_hrms.custom_code.approval_authority import assert_can_approve

	assert_can_approve(
		employee,
		_("OOO check-ins"),
		on_date=on_date,
		site_allows_self=not _prevent_self_ooo_checkin_approval(),
	)


def _assert_can_view_ooo_day(employee: str):
	"""Leave approver, the employee themself, or Administrator may view."""
	user = frappe.session.user
	if user == "Administrator":
		return
	if _is_own_employee(employee):
		return
	if _is_leave_approver_for(employee):
		return
	frappe.throw(_("Not permitted to view OOO details for this employee."), frappe.PermissionError)


def validate_ooo_checkin(doc, method):
    """
    doc_events validate hook for Employee Checkin.
    Enforces strict transition rules and reason validation.
    """
    # Bypass validation if log is synced from biometric device
    if doc.device_id:
        return

    # Enforce OOO reason is always required for OOO logs
    if doc.custom_attendance_type == "OOO Work" and not doc.custom_reason:
        frappe.throw(_("OOO Reason is required for all OOO Work logs."))

    # Validate Transitions strictly (IN -> OUT -> IN -> OUT)
    last_log = frappe.get_all("Employee Checkin", filters={
        "employee": doc.employee,
        "time": ["<", doc.time],
        "name": ["!=", doc.name]
    }, fields=["log_type", "custom_attendance_type"], order_by="time desc", limit=1)

    if last_log:
        last = last_log[0]
        if last.log_type == "IN":
            if doc.log_type != "OUT":
                frappe.throw(_("Consecutive check-ins are not allowed. You must check out first."))
            if doc.custom_attendance_type != last.custom_attendance_type:
                frappe.throw(_("Your last check-in was {0}. You must check out as {0} first.").format(last.custom_attendance_type))
        else:
            if doc.log_type != "IN":
                frappe.throw(_("Consecutive check-outs are not allowed. You must check in first."))


def check_ooo_hold(doc, method):
    """
    doc_events before_submit hook for Attendance.
    Prevent submission if the attendance is on OOO hold.
    """
    if doc.custom_ooo_hold:
        frappe.throw(
            _("This attendance is on hold pending OOO Work approval. "
              "The Leave Approver must approve the OOO check-ins first.")
        )


def cleanup_old_path_logs():
    """
    Scheduled task to clean up old Employee Path Logs based on retention setting.
    """
    retention_days = frappe.db.get_single_value("HR Settings", "custom_path_log_retention_days") or 0

    if retention_days <= 0:
        # 0 means always retain
        return

    from frappe.utils import add_days
    cutoff_date = add_days(today(), -retention_days)

    old_logs = frappe.get_all("Employee Path Log", filters={
        "timestamp": ["<", f"{cutoff_date} 00:00:00"]
    }, pluck="name", limit_page_length=500)

    for log_name in old_logs:
        frappe.delete_doc("Employee Path Log", log_name, ignore_permissions=True)

    if old_logs:
        frappe.db.commit()
        frappe.logger().info(f"Cleaned up {len(old_logs)} old Employee Path Logs (retention: {retention_days} days)")


# --- Internal helpers ---

def _validate_employee_permission(employee_doc):
    """Ensure the current user has permission to act for this employee."""
    user = frappe.session.user
    if user == "Administrator":
        return

    if employee_doc.user_id != user:
        # Check if user is HR Manager
        if "HR Manager" not in frappe.get_roles(user):
            frappe.throw(_("You can only perform attendance actions for yourself."))


def _get_active_ooo_session(employee):
    """
    Check if the employee has an active OOO session (IN without matching OUT).
    Returns the IN checkin record if active, None otherwise.
    """
    today_date = today()

    # Get all OOO check-ins for today, ordered by time
    ooo_logs = frappe.get_all("Employee Checkin", filters={
        "employee": employee,
        "time": ["between", [f"{today_date} 00:00:00", f"{today_date} 23:59:59"]],
        "custom_attendance_type": "OOO Work",
    }, fields=["name", "log_type", "time", "custom_reason"], order_by="time asc")

    if not ooo_logs:
        return None

    # Count IN and OUT logs — if more INs than OUTs, session is active
    in_count = sum(1 for log in ooo_logs if log.log_type == "IN")
    out_count = sum(1 for log in ooo_logs if log.log_type == "OUT")

    if in_count > out_count:
        # Return the last IN log as the active session
        last_in = [log for log in ooo_logs if log.log_type == "IN"][-1]
        return last_in

    return None
