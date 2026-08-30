import frappe
import json
from frappe import _
from frappe.utils import cint, getdate, add_days, get_datetime, get_time

import nepal_compliance.nepali_date_utils.nepali_date as nepali_date


def execute(filters=None):
    if not filters:
        filters = {}
    if isinstance(filters, str):
        try:
            filters = frappe.parse_json(filters)
        except Exception:
            filters = {}

    filters = frappe._dict(filters)
    nepali_date._ensure_loaded()

    # Date Handling
    if filters.get("filter_based_on") == "BS Date Range":
        from_bs = filters.get("from_bs_date")
        to_bs = filters.get("to_bs_date")
        if not from_bs or not to_bs:
            frappe.throw(_("Please provide both From and To BS Dates"))
        try:
            f_y, f_m, f_d = map(int, from_bs.split("-"))
            t_y, t_m, t_d = map(int, to_bs.split("-"))
            start_ad = nepali_date.bs_to_ad(f_y, f_m, f_d)
            end_ad = nepali_date.bs_to_ad(t_y, t_m, t_d)
        except Exception:
            frappe.throw(_("Invalid BS Date format. Use YYYY-MM-DD"))
    else:
        bs_year = int(filters.get("bs_year") or 2081)
        bs_month = int(filters.get("bs_month") or 1)
        if bs_year not in nepali_date._bs_months:
            frappe.throw(_("Selected BS Year {0} is out of bounds.").format(bs_year))
        if filters.get("use_custom_period"):
            s_day = int(filters.get("custom_start_day") or 1)
            s_type = filters.get("start_month_type")
            e_day = int(filters.get("custom_end_day") or 30)
            e_type = filters.get("end_month_type")
            s_offset = -1 if s_type == "Previous Month" else 0
            e_offset = 1 if e_type == "Next Month" else 0
            start_ad = get_bs_date_with_offset(bs_year, bs_month, s_day, s_offset)
            end_ad = get_bs_date_with_offset(bs_year, bs_month, e_day, e_offset)
        else:
            days_in_month = nepali_date._bs_months[bs_year][bs_month - 1]
            start_ad = nepali_date.bs_to_ad(bs_year, bs_month, 1)
            end_ad = nepali_date.bs_to_ad(bs_year, bs_month, days_in_month)

    if (end_ad - start_ad).days > 32:
        frappe.throw(_("Date range cannot exceed 32 days for this report layout."))

    company = filters.get("company")
    if not company:
        frappe.throw(_("Company is mandatory"))

    attendance_data, leave_types = get_attendance_and_leaves(filters, start_ad, end_ad)
    columns = get_columns(filters, start_ad, end_ad, leave_types)

    message = """
    <div class="attendance-bar-legend" style="display:flex; flex-direction:column; gap:10px; font-size:12px; padding:12px 14px; background:#f8fafc; border-radius:10px; border:1px solid #e2e8f0; margin-bottom:8px; color:#334155;">
      <div style="display:flex; flex-wrap:wrap; gap:10px 16px; align-items:center;">
        <span style="font-weight:700; color:#0f172a;">Time bar</span>
        <span style="display:flex; align-items:center; gap:5px;"><span style="width:14px; height:10px; border-radius:3px; background:#22c55e;"></span>Office</span>
        <span style="display:flex; align-items:center; gap:5px;"><span style="width:14px; height:10px; border-radius:3px; background:#3b82f6;"></span>OOO Work</span>
        <span style="display:flex; align-items:center; gap:5px;"><span style="width:14px; height:10px; border-radius:3px; background:#0d9488;"></span>WFH</span>
        <span style="display:flex; align-items:center; gap:5px;"><span style="width:14px; height:10px; border-radius:3px; background:#a855f7;"></span>Half Day Leave</span>
        <span style="display:flex; align-items:center; gap:5px;"><span style="width:14px; height:10px; border-radius:3px; background:#f97316;"></span>Extra</span>
        <span style="display:flex; align-items:center; gap:5px;"><span style="width:14px; height:10px; border-radius:3px; background:#ef4444;"></span>Gap</span>
        <span style="display:flex; align-items:center; gap:5px;"><span style="width:14px; height:10px; border-radius:3px; background:#94a3b8;"></span>Holiday / WO</span>
      </div>
      <div style="display:flex; flex-wrap:wrap; gap:10px 16px; align-items:center; border-top:1px solid #e2e8f0; padding-top:8px;">
        <span style="font-weight:700; color:#0f172a;">Late / Early badges</span>
        <span style="display:flex; align-items:center; gap:5px;"><span style="background:#fbbf24;color:#78350f;font-weight:700;font-size:10px;padding:1px 6px;border-radius:999px;">Lg</span> Late within grace</span>
        <span style="display:flex; align-items:center; gap:5px;"><span style="background:#ef4444;color:#fff;font-weight:700;font-size:10px;padding:1px 6px;border-radius:999px;">L!</span> Late — no application</span>
        <span style="display:flex; align-items:center; gap:5px;"><span style="background:#16a34a;color:#fff;font-weight:700;font-size:10px;padding:1px 6px;border-radius:999px;">L✓</span> Late — app approved</span>
        <span style="display:flex; align-items:center; gap:5px;"><span style="background:#fbbf24;color:#78350f;font-weight:700;font-size:10px;padding:1px 6px;border-radius:999px;">Eg</span> Early within grace</span>
        <span style="display:flex; align-items:center; gap:5px;"><span style="background:#ef4444;color:#fff;font-weight:700;font-size:10px;padding:1px 6px;border-radius:999px;">E!</span> Early — no application</span>
        <span style="display:flex; align-items:center; gap:5px;"><span style="background:#16a34a;color:#fff;font-weight:700;font-size:10px;padding:1px 6px;border-radius:999px;">E✓</span> Early — app approved</span>
        <span style="display:flex; align-items:center; gap:5px;"><span style="background:#3b82f6;color:#fff;font-weight:700;font-size:10px;padding:1px 6px;border-radius:999px;">O</span> OOO application</span>
      </div>
      <div style="color:#64748b; font-size:11px;">Click the status pill to open Attendance. Click a badge to open the linked application. Totals at the right include flag-based late/early and application counts.</div>
    </div>
    """

    data = get_data(filters, start_ad, end_ad, attendance_data, leave_types)
    return columns, data, message


def get_columns(filters, start_ad, end_ad, leave_types):
    show_details = filters.get("show_details")
    columns = [
        {"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 140, "sticky": 1},
        {"label": _("Summary"), "fieldname": "summary", "fieldtype": "Data", "width": 140, "sticky": 1},
    ]

    curr = start_ad
    while curr <= end_ad:
        bs = nepali_date.ad_to_bs(curr)
        day = bs["day"]
        weekday_abbr = curr.strftime("%a").upper()
        label_html = f"<div style='text-align:center;'><span style='font-size:13px; font-weight:bold; color:#374151;'>{day:02d}</span><span style='font-size:10px; color:#6b7280; margin-left:4px;'>{weekday_abbr}</span></div>"
        fieldname = f"day_{curr.strftime('%Y_%m_%d')}"
        columns.append({"label": label_html, "fieldname": fieldname, "fieldtype": "Data", "width": 80})

        columns.append({"label": f"{day} In", "fieldname": f"{fieldname}_in", "fieldtype": "Time", "width": 80, "hidden": not show_details})
        columns.append({"label": f"{day} Out", "fieldname": f"{fieldname}_out", "fieldtype": "Time", "width": 80, "hidden": not show_details})
        columns.append({"label": f"{day} WH", "fieldname": f"{fieldname}_wh", "fieldtype": "Float", "width": 60, "hidden": not show_details})
        columns.append({"label": f"{day} Logs", "fieldname": f"{fieldname}_checks", "fieldtype": "Data", "width": 120, "hidden": not show_details})
        curr = add_days(curr, 1)

    columns.extend([
        {"label": _("Total Days in Period"), "fieldname": "total_days_in_period", "fieldtype": "Int", "width": 140},
        {"label": _("Late (flag)"), "fieldname": "total_late_entry", "fieldtype": "Int", "width": 90},
        {"label": _("Late in grace"), "fieldname": "total_grace_late", "fieldtype": "Int", "width": 100},
        {"label": _("Late no app"), "fieldname": "total_unexcused_late", "fieldtype": "Int", "width": 100},
        {"label": _("Late Entry Apps"), "fieldname": "total_late_entry_apps", "fieldtype": "Int", "width": 110},
        {"label": _("Early (flag)"), "fieldname": "total_early_exit", "fieldtype": "Int", "width": 90},
        {"label": _("Early Exit Apps"), "fieldname": "total_early_exit_apps", "fieldtype": "Int", "width": 110},
        {"label": _("OOO Apps"), "fieldname": "total_ooo_apps", "fieldtype": "Int", "width": 90},
        {"label": _("Total Days Present"), "fieldname": "total_no_of_days", "fieldtype": "Float", "width": 120},
        {"label": _("Present"), "fieldname": "total_present", "fieldtype": "Float", "width": 70},
        {"label": _("Absent"), "fieldname": "total_absent", "fieldtype": "Float", "width": 70},
        {"label": _("Holiday"), "fieldname": "total_holiday", "fieldtype": "Float", "width": 70},
        {"label": _("Leave"), "fieldname": "total_leave", "fieldtype": "Float", "width": 70},
    ])

    for lt in sorted(leave_types):
        columns.append({"label": lt, "fieldname": frappe.scrub(lt), "fieldtype": "Float", "width": 90})

    columns.append({"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120})
    return columns


def get_attendance_and_leaves(filters, start_ad, end_ad):
    emp_conditions = {"company": filters.get("company"), "status": "Active"}
    # Same rule as Live Attendance Board: Active but already relieved before the period are hidden
    relieving_or_filters = [
        ["relieving_date", "is", "not set"],
        ["relieving_date", ">=", start_ad],
    ]
    user = frappe.session.user
    user_roles = frappe.get_roles(user)
    has_full_access = "HR Manager" in user_roles or "HR User" in user_roles or "Attendance Report Viewer" in user_roles or user == "Administrator"

    if not has_full_access:
        linked_emps = frappe.get_all(
            "Employee",
            filters={"user_id": user, "status": "Active"},
            or_filters=relieving_or_filters,
            pluck="name",
            limit=1,
            ignore_permissions=True,
        )
        linked_emp = linked_emps[0] if linked_emps else None
        if linked_emp:
            allowed_emps = [linked_emp]
            def fetch_subs(mgr):
                subs = frappe.get_all(
                    "Employee",
                    filters={"reports_to": mgr, "status": "Active"},
                    or_filters=relieving_or_filters,
                    pluck="name",
                    ignore_permissions=True,
                )
                for sub in subs:
                    allowed_emps.append(sub)
                    fetch_subs(sub)
            fetch_subs(linked_emp)
            emp_conditions["name"] = ["in", allowed_emps]
        else:
            emp_conditions["name"] = "None"

    if filters.get("employee"): emp_conditions["name"] = filters.get("employee")
    if filters.get("department"): emp_conditions["department"] = filters.get("department")
    if filters.get("shift"): emp_conditions["default_shift"] = filters.get("shift")

    employees = frappe.get_all(
        "Employee",
        filters=emp_conditions,
        or_filters=relieving_or_filters,
        fields=["name", "employee_name", "holiday_list"],
        ignore_permissions=True,
    )
    if not employees: return {"employees": []}, set()

    emp_names = [e.name for e in employees]

    att_fields = [
        "name", "employee", "attendance_date", "status", "working_hours", "leave_type",
        "half_day_status", "late_entry", "early_exit", "in_time", "out_time", "shift",
    ]
    att_meta = frappe.get_meta("Attendance")
    for fname in ("custom_late_mins", "custom_early_mins", "custom_cnr_unexcused_late", "custom_cnr_unexcused_early"):
        if att_meta.has_field(fname):
            att_fields.append(fname)

    attendances = frappe.get_all(
        "Attendance",
        filters={"employee": ["in", emp_names], "attendance_date": ["between", [start_ad, end_ad]], "docstatus": 1},
        fields=att_fields,
        ignore_permissions=True
    )

    checkins = frappe.get_all(
        "Employee Checkin",
        filters={"employee": ["in", emp_names], "time": ["between", [f"{start_ad} 00:00:00", f"{end_ad} 23:59:59"]], "docstatus": ["<", 2]},
        fields=["employee", "time", "log_type", "custom_attendance_type"],
        order_by="time asc",
        ignore_permissions=True
    )

    # Fetch shift assignments for the period
    shift_assignments = frappe.get_all(
        "Shift Assignment",
        filters={
            "employee": ["in", emp_names],
            "docstatus": 1,
            "status": "Active",
            "start_date": ["<=", end_ad],
        },
        or_filters=[["end_date", ">=", start_ad], ["end_date", "is", "not set"]],
        fields=["employee", "shift_type", "start_date", "end_date"],
        ignore_permissions=True
    )

    # Build shift assignment map: employee -> list of assignments
    shift_map = {}
    for sa in shift_assignments:
        shift_map.setdefault(sa.employee, []).append(sa)

    # Fetch shift type details
    shift_types_used = set(sa.shift_type for sa in shift_assignments)
    shift_type_details = {}
    for st_name in shift_types_used:
        try:
            st = frappe.get_cached_doc("Shift Type", st_name)
            shift_type_details[st_name] = {"start_time": str(st.start_time), "end_time": str(st.end_time)}
        except Exception:
            pass

    # Fetch leave applications for half-day detection
    leave_apps = frappe.get_all(
        "Leave Application",
        filters={"employee": ["in", emp_names], "from_date": ["<=", end_ad], "to_date": [">=", start_ad], "docstatus": 1, "half_day": 1},
        fields=["employee", "from_date", "to_date", "half_day", "half_day_date"],
        ignore_permissions=True
    )

    lea_map = _cnr_application_map("Late Entry Application", emp_names, start_ad, end_ad)
    eea_map = _cnr_application_map("Early Exit Application", emp_names, start_ad, end_ad)
    ooo_map = _cnr_application_map("Out of Office Application", emp_names, start_ad, end_ad)

    attendance_map = {}
    for att in attendances:
        key = (att.employee, getdate(att.attendance_date))
        attendance_map[key] = att

    checkin_map = {}
    for c in checkins:
        key = (c.employee, getdate(c.time))
        if key not in checkin_map: checkin_map[key] = []
        checkin_map[key].append(c)

    leave_types = set(att.leave_type for att in attendances if att.leave_type)

    return {
        "employees": employees,
        "attendance_map": attendance_map,
        "checkin_map": checkin_map,
        "shift_map": shift_map,
        "shift_type_details": shift_type_details,
        "leave_apps": leave_apps,
        "lea_map": lea_map,
        "eea_map": eea_map,
        "ooo_map": ooo_map,
    }, leave_types


def _cnr_application_map(doctype, emp_names, start_ad, end_ad):
    """Map (employee, attendance_date) -> list of approved application names."""
    if not emp_names or not frappe.db.exists("DocType", doctype):
        return {}
    rows = frappe.get_all(
        doctype,
        filters={
            "employee": ["in", emp_names],
            "attendance_date": ["between", [start_ad, end_ad]],
            "docstatus": 1,
            "status": "Approved",
        },
        fields=["name", "employee", "attendance_date"],
        ignore_permissions=True,
    )
    app_map = {}
    for r in rows:
        key = (r.employee, getdate(r.attendance_date))
        app_map.setdefault(key, []).append(r.name)
    return app_map


def _delay_badge_kind(mins, grace, has_app, unexcused_flag=0):
    """
    Return badge kind for late/early minutes:
    None | 'grace' | 'unexcused' | 'excused'
    """
    mins = cint(mins)
    grace = cint(grace) or 15
    if mins <= 0:
        return None
    if mins <= grace:
        return "grace"
    if has_app:
        return "excused"
    if unexcused_flag or mins > grace:
        return "unexcused"
    return None


def calculate_attendance_hours(employee, date, status, checkins, shift_map, shift_type_details):
    """
    Dynamically calculate working hours, late entry, and early exit based on shift and check-ins
    when working hours are 0 or from an approved attendance request.
    """
    emp_shifts = shift_map.get(employee, [])
    active_shift = None
    for sa in emp_shifts:
        sa_start = getdate(sa.start_date)
        sa_end = getdate(sa.end_date) if sa.end_date else getdate("2099-12-31")
        if sa_start <= date <= sa_end:
            active_shift = sa
            break

    shift_start_mins = None
    shift_end_mins = None
    shift_duration = 480.0
    
    if active_shift:
        st_detail = shift_type_details.get(active_shift.shift_type)
        if st_detail:
            shift_start_mins = _time_to_minutes(st_detail["start_time"])
            shift_end_mins = _time_to_minutes(st_detail["end_time"])
            if shift_end_mins <= shift_start_mins:
                shift_end_mins += 1440
            shift_duration = shift_end_mins - shift_start_mins

    in_time_mins = None
    out_time_mins = None
    
    if checkins:
        sorted_c = sorted(checkins, key=lambda x: get_datetime(x.time))
        first_c = sorted_c[0]
        last_c = sorted_c[-1]
        
        first_dt = get_datetime(first_c.time)
        in_time_mins = first_dt.hour * 60 + first_dt.minute
        
        if len(sorted_c) > 1:
            last_dt = get_datetime(last_c.time)
            out_time_mins = last_dt.hour * 60 + last_dt.minute
            if out_time_mins < in_time_mins:
                out_time_mins += 1440
        else:
            if first_c.log_type == "IN":
                in_time_mins = first_dt.hour * 60 + first_dt.minute
            else:
                out_time_mins = first_dt.hour * 60 + first_dt.minute

    working_hours = 0.0
    late_entry = False
    early_exit = False
    
    if not checkins:
        if status in ("Present", "Work From Home"):
            working_hours = shift_duration / 60.0
        elif status == "Half Day":
            working_hours = (shift_duration / 2.0) / 60.0
    else:
        if in_time_mins is not None and out_time_mins is not None:
            working_hours = (out_time_mins - in_time_mins) / 60.0
            if shift_start_mins is not None:
                if in_time_mins > shift_start_mins:
                    late_entry = True
                if out_time_mins < shift_end_mins:
                    early_exit = True
        elif in_time_mins is not None:
            if shift_end_mins is not None:
                working_hours = (shift_end_mins - in_time_mins) / 60.0
                if shift_start_mins is not None and in_time_mins > shift_start_mins:
                    late_entry = True
            else:
                working_hours = 8.0 if status != "Half Day" else 4.0
        elif out_time_mins is not None:
            if shift_start_mins is not None:
                working_hours = (out_time_mins - shift_start_mins) / 60.0
                if shift_end_mins is not None and out_time_mins < shift_end_mins:
                    early_exit = True
            else:
                working_hours = 8.0 if status != "Half Day" else 4.0

    working_hours = max(0.0, working_hours)
    working_hours = min(24.0, working_hours)
    
    if status == "Half Day":
        working_hours = min(working_hours, (shift_duration / 2.0) / 60.0)

    return round(working_hours, 2), late_entry, early_exit


def get_data(filters, start_ad, end_ad, att_data, leave_types):
    employees = att_data["employees"]
    attendance_map = att_data["attendance_map"]
    checkin_map = att_data["checkin_map"]
    shift_map = att_data.get("shift_map", {})
    shift_type_details = att_data.get("shift_type_details", {})
    leave_apps = att_data.get("leave_apps", [])
    lea_map = att_data.get("lea_map", {})
    eea_map = att_data.get("eea_map", {})
    ooo_map = att_data.get("ooo_map", {})

    try:
        settings = frappe.get_cached_doc("Nepal Compliance Settings", "Nepal Compliance Settings")
        grace_mins = cint(getattr(settings, "late_early_grace_mins", None) or 15)
    except Exception:
        grace_mins = 15

    company_holiday_list = frappe.db.get_value('Company', filters.get('company'), 'default_holiday_list')
    holiday_lists = set(e.holiday_list for e in employees if e.holiday_list)
    if company_holiday_list: holiday_lists.add(company_holiday_list)

    holidays_by_list = {}
    for hl in holiday_lists:
        h_records = frappe.get_all("Holiday", filters={"parent": hl, "holiday_date": ["between", [start_ad, end_ad]]}, fields=["holiday_date", "weekly_off"], ignore_permissions=True)
        holidays_by_list[hl] = {getdate(h.holiday_date): bool(h.weekly_off) for h in h_records}

    days_in_period = (end_ad - start_ad).days + 1
    data = []
    period_start = str(start_ad)
    period_end = str(end_ad)

    for emp in employees:
        row = {
            "employee": emp.name, "employee_name": emp.employee_name,
            "period_start": period_start, "period_end": period_end,
            "total_days_in_period": days_in_period, "total_late_entry": 0, "total_early_exit": 0,
            "total_grace_late": 0, "total_unexcused_late": 0,
            "total_late_entry_apps": 0, "total_early_exit_apps": 0, "total_ooo_apps": 0,
            "total_no_of_days": 0, "total_present": 0, "total_absent": 0,
            "total_holiday": 0, "total_leave": 0,
        }
        for lt in leave_types:
            row[frappe.scrub(lt)] = 0

        total_worked = 0.0
        total_target = 0.0
        hl = emp.holiday_list or company_holiday_list
        emp_holidays = holidays_by_list.get(hl, {})

        curr = start_ad
        while curr <= end_ad:
            key = (emp.name, curr)
            att = attendance_map.get(key)
            day_checkins = checkin_map.get(key, [])
            fieldname = f"day_{curr.strftime('%Y_%m_%d')}"

            # Extract in/out times
            if day_checkins:
                times = [get_datetime(c.time) for c in day_checkins]
                row[f"{fieldname}_in"] = times[0].strftime("%H:%M:%S")
                row[f"{fieldname}_out"] = times[-1].strftime("%H:%M:%S")

            status_abbr = "NONE"
            wh = 0.0
            wh_str = ""
            checks_str = ",".join([get_datetime(c.time).strftime("%H:%M") for c in day_checkins])
            target_hours = 8.0
            leave_type = ""
            is_half_day = 0

            is_holiday = curr in emp_holidays
            if is_holiday:
                status_abbr = "WO" if emp_holidays[curr] else "Hol"
                row["total_holiday"] += 1
                row["total_no_of_days"] += 1
                target_hours = 0.0

            late_entry = False
            early_exit = False
            late_mins = 0
            early_mins = 0
            day_lea = lea_map.get(key) or []
            day_eea = eea_map.get(key) or []
            day_ooo = ooo_map.get(key) or []
            if day_lea:
                row["total_late_entry_apps"] += len(day_lea)
            if day_eea:
                row["total_early_exit_apps"] += len(day_eea)
            if day_ooo:
                row["total_ooo_apps"] += len(day_ooo)

            if att:
                wh = att.working_hours or 0.0
                status = att.status
                late_entry = bool(att.late_entry)
                early_exit = bool(att.early_exit)
                late_mins = cint(getattr(att, "custom_late_mins", 0) or 0)
                early_mins = cint(getattr(att, "custom_early_mins", 0) or 0)

                # Dynamic calculation for missing/zero working hours when present/half day/wfh
                if wh == 0.0 and status in ("Present", "Half Day", "Work From Home"):
                    calc_wh, calc_late, calc_early = calculate_attendance_hours(
                        emp.name, curr, status, day_checkins, shift_map, shift_type_details
                    )
                    wh = calc_wh
                    if not late_entry and calc_late:
                        late_entry = True
                    if not early_exit and calc_early:
                        early_exit = True

                if (not late_mins and att.in_time) or (not early_mins and att.out_time):
                    try:
                        from nepal_hrms.custom_code.attendance_policy import compute_late_early_minutes
                        calc_late_m, calc_early_m = compute_late_early_minutes(
                            emp.name, curr, in_time=att.in_time, out_time=att.out_time, shift=getattr(att, "shift", None)
                        )
                        if not late_mins:
                            late_mins = calc_late_m
                        if not early_mins:
                            early_mins = calc_early_m
                    except Exception:
                        pass

                row[f"{fieldname}_wh"] = wh
                total_worked += wh
                leave_type = att.leave_type or ""
                is_half_day = 1 if status == "Half Day" else 0

                if late_entry: row["total_late_entry"] += 1
                if early_exit: row["total_early_exit"] += 1

                if status == "Present":
                    status_abbr = "P"
                    row["total_present"] += 1
                    row["total_no_of_days"] += 1
                elif status == "Absent":
                    status_abbr = "Ab"
                    row["total_absent"] += 1
                    target_hours = 0.0
                elif status == "Half Day":
                    status_abbr = "HD/P" if att.half_day_status == "Present" else "HD/A"
                    row["total_present"] += 0.5
                    row["total_no_of_days"] += 1
                    target_hours = 4.0
                elif status == "On Leave":
                    status_abbr = "Lv"
                    row["total_leave"] += 1.0
                    row["total_no_of_days"] += 1
                    if leave_type:
                        row[frappe.scrub(leave_type)] += 1.0
                    target_hours = 0.0
                elif status == "Work From Home":
                    status_abbr = "WFH"
                    row["total_present"] += 1
                    row["total_no_of_days"] += 1
                elif status in ["Weekly Off", "Holiday"]:
                    status_abbr = "WO" if status == "Weekly Off" else "Hol"
                    if not is_holiday:
                        row["total_holiday"] += 1
                        target_hours = 0.0
                    row["total_no_of_days"] += 1

                if wh > 0:
                    wh_str = f"{int(wh)}h" if wh == int(wh) else f"{round(wh, 1)}h"

            if not att and not is_holiday:
                target_hours = 0.0

            total_target += target_hours
            # Build bar data for this day
            bar_data = build_bar_data(
                emp.name, curr, day_checkins, att, is_holiday,
                emp_holidays.get(curr), shift_map, shift_type_details, leave_apps, status_abbr
            )

            unexcused_late = cint(getattr(att, "custom_cnr_unexcused_late", 0) or 0) if att else 0
            unexcused_early = cint(getattr(att, "custom_cnr_unexcused_early", 0) or 0) if att else 0
            late_kind = _delay_badge_kind(late_mins, grace_mins, bool(day_lea), unexcused_late)
            early_kind = _delay_badge_kind(early_mins, grace_mins, bool(day_eea), unexcused_early)
            # Flag-only late with 0 stored mins still show as unexcused/excused via app
            if not late_kind and late_entry:
                late_kind = "excused" if day_lea else "unexcused"
            if not early_kind and early_exit:
                early_kind = "excused" if day_eea else "unexcused"

            if late_kind == "grace":
                row["total_grace_late"] += 1
            elif late_kind == "unexcused":
                row["total_unexcused_late"] += 1

            # Store EVERYTHING in the main field as JSON for the formatter
            row[fieldname] = json.dumps({
                "status": status_abbr,
                "wh": wh_str,
                "checks": checks_str,
                "target": target_hours,
                "leave_type": leave_type,
                "half_day": is_half_day,
                "late_entry": 1 if late_entry else 0,
                "early_exit": 1 if early_exit else 0,
                "late_mins": late_mins,
                "early_mins": early_mins,
                "grace_mins": grace_mins,
                "late_kind": late_kind,
                "early_kind": early_kind,
                "bar_data": bar_data,
                "attendance_doc": att.name if att else None,
                "late_entry_app": day_lea[0] if day_lea else None,
                "early_exit_app": day_eea[0] if day_eea else None,
                "ooo_app": day_ooo[0] if day_ooo else None,
                "has_lea": 1 if day_lea else 0,
                "has_eea": 1 if day_eea else 0,
                "has_ooo": 1 if day_ooo else 0,
            })

            curr = add_days(curr, 1)

        w_h, w_m = divmod(int(total_worked * 60), 60)
        t_h, t_m = divmod(int(total_target * 60), 60)
        row["summary"] = f"{w_h}:{w_m:02d} / {t_h}:{t_m:02d}"
        data.append(row)

    return data


def build_bar_data(employee, date, checkins, att, is_holiday, is_weekly_off, shift_map, shift_type_details, leave_apps, status_abbr):
    """Build time bar segment data for a single employee-day."""
    result = {
        "has_shift": False,
        "shift_start": None,
        "shift_end": None,
        "is_weekly_off": bool(is_weekly_off) if is_holiday else False,
        "is_holiday": is_holiday and not is_weekly_off if is_holiday else False,
        "is_leave": status_abbr == "Lv",
        "is_half_day": status_abbr in ("HD/P", "HD/A"),
        "status": status_abbr,
        "segments": [],
    }

    # Find active shift for this employee on this date
    emp_shifts = shift_map.get(employee, [])
    active_shift = None
    for sa in emp_shifts:
        sa_start = getdate(sa.start_date)
        sa_end = getdate(sa.end_date) if sa.end_date else getdate("2099-12-31")
        if sa_start <= date <= sa_end:
            active_shift = sa
            break

    shift_type_name = None
    if active_shift:
        shift_type_name = active_shift.shift_type
    else:
        # Fall back when Shift Assignment ended/inactive but Attendance/Employee still has a shift
        # (e.g. Sabina Thapa: assignment ended 2026-03-27, Attendance.shift still "Full Time")
        shift_type_name = (getattr(att, "shift", None) if att else None) or frappe.db.get_value(
            "Employee", employee, "default_shift"
        )

    if not shift_type_name:
        result["no_shift"] = True
        return result

    st_detail = shift_type_details.get(shift_type_name)
    if not st_detail:
        try:
            st = frappe.get_cached_doc("Shift Type", shift_type_name)
            st_detail = {"start_time": str(st.start_time), "end_time": str(st.end_time)}
            shift_type_details[shift_type_name] = st_detail
        except Exception:
            result["no_shift"] = True
            return result

    result["has_shift"] = True
    result["shift_start"] = st_detail["start_time"]
    result["shift_end"] = st_detail["end_time"]
    result["shift_name"] = shift_type_name
    result["no_shift"] = False

    # Don't build segments for weekly off or full leave
    if result["is_weekly_off"] or result["is_leave"]:
        # But if there are checkins on a holiday, mark them as yellow (extra)
        if checkins and is_holiday:
            for c in checkins:
                ct = get_datetime(c.time)
                result["segments"].append({
                    "start": ct.strftime("%H:%M"),
                    "end": ct.strftime("%H:%M"),
                    "type": "extra",
                })
        return result

    if not checkins:
        # No checkins - if attendance says absent, entire shift is gap
        if status_abbr == "Ab":
            result["segments"].append({
                "start": st_detail["start_time"][:5],
                "end": st_detail["end_time"][:5],
                "type": "gap",
            })
        elif status_abbr in ("P", "WFH", "HD/P", "HD/A"):
            shift_start_mins = _time_to_minutes(st_detail["start_time"])
            shift_end_mins = _time_to_minutes(st_detail["end_time"])
            if shift_end_mins <= shift_start_mins:
                shift_end_mins += 1440
            
            if status_abbr == "P":
                result["segments"].append({
                    "start": _minutes_to_time(shift_start_mins),
                    "end": _minutes_to_time(shift_end_mins),
                    "type": "normal",
                })
            elif status_abbr == "WFH":
                result["segments"].append({
                    "start": _minutes_to_time(shift_start_mins),
                    "end": _minutes_to_time(shift_end_mins),
                    "type": "wfh",
                })
            elif status_abbr in ("HD/P", "HD/A"):
                half_point = shift_start_mins + (shift_end_mins - shift_start_mins) // 2
                if status_abbr == "HD/P":
                    # First half leave, second half worked
                    result["segments"].append({
                        "start": _minutes_to_time(shift_start_mins),
                        "end": _minutes_to_time(half_point),
                        "type": "halfday",
                    })
                    result["segments"].append({
                        "start": _minutes_to_time(half_point),
                        "end": _minutes_to_time(shift_end_mins),
                        "type": "normal",
                    })
                else: # HD/A
                    # First half worked, second half leave
                    result["segments"].append({
                        "start": _minutes_to_time(shift_start_mins),
                        "end": _minutes_to_time(half_point),
                        "type": "normal",
                    })
                    result["segments"].append({
                        "start": _minutes_to_time(half_point),
                        "end": _minutes_to_time(shift_end_mins),
                        "type": "halfday",
                    })
        return result

    # Build segments from checkin logs
    shift_start_mins = _time_to_minutes(st_detail["start_time"])
    shift_end_mins = _time_to_minutes(st_detail["end_time"])
    if shift_end_mins <= shift_start_mins:
        shift_end_mins += 1440  # overnight shift

    # Parse checkins into time entries with type
    entries = []
    for c in checkins:
        ct = get_datetime(c.time)
        mins = ct.hour * 60 + ct.minute
        att_type = getattr(c, "custom_attendance_type", "Normal") or "Normal"
        entries.append({"time": mins, "log_type": c.log_type, "att_type": att_type, "time_str": ct.strftime("%H:%M")})

    # If a single check-in log is present and the attendance status is approved,
    # append/prepend a virtual check-in/out entry at the shift boundary before pairing starts.
    if len(entries) == 1 and status_abbr in ("P", "WFH", "HD/P", "HD/A"):
        single_entry = entries[0]
        if single_entry["log_type"] == "IN":
            # Missing OUT. Append virtual OUT at shift end.
            att_type = single_entry["att_type"]
            virtual_time = max(shift_end_mins, single_entry["time"])
            entries.append({
                "time": virtual_time,
                "log_type": "OUT",
                "att_type": att_type,
                "time_str": _minutes_to_time(virtual_time),
                "is_virtual": True
            })
        else:
            # Missing IN. Prepend virtual IN at shift start.
            att_type = single_entry["att_type"]
            virtual_time = min(shift_start_mins, single_entry["time"])
            entries.insert(0, {
                "time": virtual_time,
                "log_type": "IN",
                "att_type": att_type,
                "time_str": _minutes_to_time(virtual_time),
                "is_virtual": True
            })
        # Sort entries by time to keep them chronological
        entries.sort(key=lambda x: x["time"])

    # Build presence segments from paired IN/OUT logs
    segments = []
    ooo_time = 0
    extra_time = 0
    
    # Split segments that cross shift boundaries
    def add_seg(s_min, e_min, base_type):
        nonlocal ooo_time, extra_time
        dur = e_min - s_min
        if dur <= 0: return

        # If segment crosses shift_start or shift_end, split it
        points = sorted(list(set([s_min, e_min, shift_start_mins, shift_end_mins])))
        points = [p for p in points if s_min <= p <= e_min]
        
        for k in range(len(points) - 1):
            p1, p2 = points[k], points[k+1]
            if p2 <= p1: continue
            
            final_type = base_type
            is_outside = p1 < shift_start_mins or p2 > shift_end_mins
            
            if is_outside:
                final_type = "extra"
                extra_time += (p2 - p1)
            elif is_holiday:
                final_type = "holiday"
            elif base_type == "ooo":
                ooo_time += (p2 - p1)

            segments.append({
                "start": _minutes_to_time(p1),
                "end": _minutes_to_time(p2),
                "type": final_type,
                "start_mins": p1,
                "end_mins": p2,
            })

    i = 0
    while i < len(entries):
        entry = entries[i]
        if i + 1 < len(entries) and entry["time"] < entries[i + 1]["time"]:
            next_entry = entries[i + 1]
            base_type = "normal" if entry["att_type"] == "Normal" else "ooo"
            add_seg(entry["time"], next_entry["time"], base_type)
            i += 2
        else:
            # Unpaired entry (check-in without check-out)
            base_type = "normal" if entry["att_type"] == "Normal" else "ooo"
            segments.append({
                "start": entry["time_str"],
                "end": entry["time_str"],
                "type": base_type,
                "start_mins": entry["time"],
                "end_mins": entry["time"],
            })
            i += 1
            
    result["ooo_mins"] = ooo_time
    result["extra_mins"] = extra_time
    
    # Calculate late entry mins
    late_mins = 0
    if entries and entries[0]["time"] > shift_start_mins:
        late_mins = entries[0]["time"] - shift_start_mins
    result["late_mins"] = late_mins

    # Detect gaps during shift period
    if segments:
        gap_segments = []

        # Gap before first segment (if first segment starts after shift start)
        first_start = segments[0]["start_mins"]
        if first_start > shift_start_mins:
            gap_segments.append({
                "start": _minutes_to_time(shift_start_mins),
                "end": segments[0]["start"],
                "type": "gap",
            })

        # Gaps between segments
        for j in range(len(segments) - 1):
            gap_start = segments[j]["end_mins"]
            gap_end = segments[j + 1]["start_mins"]
            if gap_end > gap_start and gap_start < shift_end_mins and gap_end > shift_start_mins:
                gap_segments.append({
                    "start": segments[j]["end"],
                    "end": segments[j + 1]["start"],
                    "type": "gap",
                })

        # Gap after last segment (if last segment ends before shift end)
        last_end = segments[-1]["end_mins"]
        if last_end < shift_end_mins:
            gap_segments.append({
                "start": segments[-1]["end"],
                "end": _minutes_to_time(shift_end_mins),
                "type": "gap",
            })

        segments.extend(gap_segments)

    # Handle half-day leave
    if result["is_half_day"]:
        # Add purple segment for the leave half
        half_point = shift_start_mins + (shift_end_mins - shift_start_mins) // 2
        # Assume second half is leave if HD/A, first half if HD/P
        if status_abbr == "HD/A":
            segments.append({
                "start": _minutes_to_time(half_point),
                "end": _minutes_to_time(shift_end_mins),
                "type": "halfday",
            })
        else:
            segments.append({
                "start": _minutes_to_time(shift_start_mins),
                "end": _minutes_to_time(half_point),
                "type": "halfday",
            })

    # Sort segments by start time and clean up internal fields
    segments.sort(key=lambda s: s["start"])
    for seg in segments:
        seg.pop("start_mins", None)
        seg.pop("end_mins", None)

    result["segments"] = segments
    return result


def _time_to_minutes(time_str):
    """Convert HH:MM or HH:MM:SS to minutes since midnight."""
    parts = str(time_str).split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _minutes_to_time(mins):
    """Convert minutes since midnight to HH:MM string."""
    mins = mins % 1440
    return f"{mins // 60:02d}:{mins % 60:02d}"


def get_bs_date_with_offset(year, month, day, month_offset):
    m = month + month_offset
    y = year
    while m < 1:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    nepali_date._ensure_loaded()
    if y not in nepali_date._bs_months:
        frappe.throw(_("Year {0} outside supported BS range").format(y))
    max_days = nepali_date._bs_months[y][m - 1]
    actual_day = min(day, max_days)
    return nepali_date.bs_to_ad(y, m, actual_day)
