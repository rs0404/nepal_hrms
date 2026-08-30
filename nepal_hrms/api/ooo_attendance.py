# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate, now_datetime, today


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
def approve_ooo_checkins(employee, attendance_date):
	"""
	Leave Approver approves OOO check-ins for a given date.
	Marks OOO check-ins approved, recalculates working hours (Normal + OOO),
	clears OOO hold, and submits/updates Attendance.
	"""
	user = frappe.session.user
	employee_doc = frappe.get_doc("Employee", employee)

	leave_approver = employee_doc.leave_approver
	if user != leave_approver and user != "Administrator" and "HR Manager" not in frappe.get_roles(user):
		frappe.throw(_("Only the Leave Approver, HR Manager, or Administrator can approve OOO check-ins."))

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

	user = frappe.session.user
	employee_doc = frappe.get_doc("Employee", employee)
	leave_approver = employee_doc.leave_approver
	if user != leave_approver and user != "Administrator" and "HR Manager" not in frappe.get_roles(user):
		frappe.throw(_("Only the Leave Approver, HR Manager, or Administrator can reject OOO check-ins."))

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
    """
    For Leave Approvers / HR: pending OOO approvals (hold + unapproved check-ins).
    Leave Approvers see their reportees; HR Manager / System Manager see all.
    """
    user = frappe.session.user
    roles = set(frappe.get_roles(user))
    is_hr = bool(roles & {"HR Manager", "System Manager"}) or user == "Administrator"

    if is_hr:
        employees = frappe.get_all(
            "Employee",
            filters={"status": "Active"},
            fields=["name", "employee_name"],
        )
    else:
        employees = frappe.get_all(
            "Employee",
            filters={"leave_approver": user, "status": "Active"},
            fields=["name", "employee_name"],
        )

    if not employees:
        return []

    employee_map = {e.name: e.employee_name for e in employees}
    employee_ids = list(employee_map.keys())

    # Get from Attendance records on hold
    pending_attendance = frappe.get_all("Attendance", filters={
        "employee": ["in", employee_ids],
        "custom_ooo_hold": 1,
        "docstatus": 0,
    }, fields=["name", "employee", "employee_name", "attendance_date", "working_hours"])

    # Find any unapproved OOO check-ins (exclude rejected)
    checkin_filters = {
        "employee": ["in", employee_ids],
        "custom_attendance_type": "OOO Work",
        "custom_is_approved": 0,
        "docstatus": 0
    }
    if frappe.get_meta("Employee Checkin").has_field("custom_ooo_rejected"):
        checkin_filters["custom_ooo_rejected"] = 0

    unapproved_checkins = frappe.get_all("Employee Checkin", filters=checkin_filters, fields=["employee", "time"])

    # Group unapproved check-ins by employee and date
    pending_from_checkins = {}
    for c in unapproved_checkins:
        date = getdate(c.time)
        key = (c.employee, date)
        if key not in pending_from_checkins:
            pending_from_checkins[key] = {
                "employee": c.employee,
                "employee_name": employee_map.get(c.employee),
                "attendance_date": date,
                "working_hours": 0.0,
            }

    # Calculate preliminary working hours for the unapproved check-ins on those dates
    for (emp, date), item in pending_from_checkins.items():
        day_checkins = frappe.get_all("Employee Checkin", filters={
            "employee": emp,
            "time": ["between", [f"{date} 00:00:00", f"{date} 23:59:59"]],
            "docstatus": ["<", 2]
        }, fields=["time", "log_type", "custom_attendance_type"], order_by="time asc")

        total_seconds = 0
        last_in_time = None
        for c in day_checkins:
            if c.log_type == "IN":
                last_in_time = c.time
            elif c.log_type == "OUT" and last_in_time:
                total_seconds += (c.time - last_in_time).total_seconds()
                last_in_time = None
        item["working_hours"] = round(total_seconds / 3600.0, 2)

    # Merge pending lists (avoiding duplicates)
    merged_pending = []
    seen = set()

    for p in pending_attendance:
        key = (p.employee, getdate(p.attendance_date))
        seen.add(key)
        merged_pending.append({
            "name": p.name,
            "employee": p.employee,
            "employee_name": p.employee_name,
            "attendance_date": str(p.attendance_date),
            "working_hours": round(p.working_hours or 0.0, 2)
        })

    for key, item in pending_from_checkins.items():
        if key not in seen:
            merged_pending.append({
                "name": None,
                "employee": item["employee"],
                "employee_name": item["employee_name"],
                "attendance_date": str(item["attendance_date"]),
                "working_hours": item["working_hours"]
            })

    return merged_pending


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
