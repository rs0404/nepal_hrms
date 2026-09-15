import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, add_days, get_datetime, get_time, today

import nepal_compliance.nepali_date_utils.nepali_date as nepali_date

from nepal_hrms.custom_code.attendance_policy import (
    free_occurrences_remaining,
    get_hr_settings,
    split_occurrence_penalty,
)
from nepal_hrms.custom_code.leave_type_acronym import (
    format_leave_type_acronym,
    leave_type_acronym,
)


LEAVE_GROUP_ANNUAL_HOME = "Annual/Home"
LEAVE_GROUP_SICK = "Sick"
LEAVE_GROUP_OTHER = "Other Paid"
APPLICATION_SPECS = {
    "attendance_request": {
        "doctype": "Attendance Request",
        "label": _("Attendance Request"),
        "fieldname": "attendance_request_apps",
        "width": 125,
    },
    "late_entry": {
        "doctype": "Late Entry Application",
        "label": _("Late Entry"),
        "fieldname": "late_entry_apps",
        "width": 100,
    },
    "early_exit": {
        "doctype": "Early Exit Application",
        "label": _("Early Exit"),
        "fieldname": "early_exit_apps",
        "width": 100,
    },
    "out_of_office": {
        "doctype": "Out of Office Application",
        "label": _("Out of Office"),
        "fieldname": "out_of_office_apps",
        "width": 110,
    },
}


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

    message = ""

    data = get_data(filters, start_ad, end_ad, attendance_data, leave_types)
    return columns, data, message


def get_columns(filters, start_ad, end_ad, leave_types=None):
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
        ad_date = curr.strftime("%d %b %Y")
        label_html = (
            "<div style='text-align:center;'>"
            f"<div><span style='font-size:13px; font-weight:bold; color:#374151;'>{day:02d}</span>"
            f"<span style='font-size:10px; color:#6b7280; margin-left:4px;'>{weekday_abbr}</span></div>"
            f"<div style='font-size:9px; color:#6b7280; margin-top:2px;'>{ad_date}</div>"
            "</div>"
        )
        fieldname = f"day_{curr.strftime('%Y_%m_%d')}"
        columns.append({"label": label_html, "fieldname": fieldname, "fieldtype": "Data", "width": 88})

        columns.append({"label": f"{day} In", "fieldname": f"{fieldname}_in", "fieldtype": "Time", "width": 80, "hidden": not show_details})
        columns.append({"label": f"{day} Out", "fieldname": f"{fieldname}_out", "fieldtype": "Time", "width": 80, "hidden": not show_details})
        columns.append({"label": f"{day} WH", "fieldname": f"{fieldname}_wh", "fieldtype": "Float", "width": 60, "hidden": not show_details})
        columns.append({"label": f"{day} Logs", "fieldname": f"{fieldname}_checks", "fieldtype": "Data", "width": 120, "hidden": not show_details})
        curr = add_days(curr, 1)

    columns.extend(
        [
            {
                "label": _("Total Period Days"),
                "fieldname": "total_days_in_period",
                "fieldtype": "Int",
                "width": 115,
            },
            {
                "label": _("Total Paid Days"),
                "fieldname": "payable_days",
                "fieldtype": "Float",
                "width": 110,
            },
            {
                "label": _("Absent Days"),
                "fieldname": "total_absent",
                "fieldtype": "Float",
                "width": 95,
            },
            {
                "label": _("Leave Without Pay"),
                "fieldname": "lwp_days",
                "fieldtype": "Float",
                "width": 120,
            },
            {
                "label": _("Paid Leaves"),
                "fieldname": "paid_leave_days",
                "fieldtype": "Float",
                "width": 95,
            },
            {
                "label": _("Annual/Home Leaves"),
                "fieldname": "annual_home_leave_days",
                "fieldtype": "Float",
                "width": 125,
            },
            {
                "label": _("Sick Leaves"),
                "fieldname": "sick_leave_days",
                "fieldtype": "Float",
                "width": 90,
            },
            {
                "label": _("Other Paid Leaves"),
                "fieldname": "other_paid_leave_days",
                "fieldtype": "Float",
                "width": 120,
            },
            {
                "label": _("Present on WO/Hol"),
                "fieldname": "holiday_extra_present",
                "fieldtype": "Float",
                "width": 115,
            },
            {
                "label": _("Extra Hrs (WO/Hol)"),
                "fieldname": "holiday_extra_hours",
                "fieldtype": "Float",
                "width": 115,
            },
        ]
    )
    for spec in APPLICATION_SPECS.values():
        columns.append(
            {
                "label": spec["label"],
                "fieldname": spec["fieldname"],
                "fieldtype": "Int",
                "width": spec["width"],
            }
        )
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
        fields=["name", "employee_name", "holiday_list", "default_shift"],
        ignore_permissions=True,
    )
    if not employees: return {"employees": []}, set()

    emp_names = [e.name for e in employees]

    att_fields = [
        "name", "employee", "attendance_date", "status", "working_hours", "leave_type",
        "half_day_status", "late_entry", "early_exit", "in_time", "out_time", "shift",
        "attendance_request", "leave_application",
    ]
    att_meta = frappe.get_meta("Attendance")
    for fname in (
        "custom_late_mins",
        "custom_early_mins",
        "custom_cnr_unexcused_late",
        "custom_cnr_unexcused_early",
        "custom_cnr_late_in_pool",
        "custom_cnr_early_in_pool",
    ):
        if att_meta.has_field(fname):
            att_fields.append(fname)

    attendances = frappe.get_all(
        "Attendance",
        filters={"employee": ["in", emp_names], "attendance_date": ["between", [start_ad, end_ad]], "docstatus": 1},
        fields=att_fields,
        ignore_permissions=True
    )

    checkin_fields = ["name", "employee", "time", "log_type", "custom_attendance_type"]
    checkin_meta = frappe.get_meta("Employee Checkin")
    if checkin_meta.has_field("custom_reason"):
        checkin_fields.append("custom_reason")
    checkins = frappe.get_all(
        "Employee Checkin",
        filters={"employee": ["in", emp_names], "time": ["between", [f"{start_ad} 00:00:00", f"{end_ad} 23:59:59"]], "docstatus": ["<", 2]},
        fields=checkin_fields,
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
    shift_types_used.update(e.default_shift for e in employees if e.default_shift)
    shift_types_used.update(att.shift for att in attendances if att.shift)
    shift_type_details = {}
    for st_name in shift_types_used:
        try:
            st = frappe.get_cached_doc("Shift Type", st_name)
            shift_type_details[st_name] = {"start_time": str(st.start_time), "end_time": str(st.end_time)}
        except Exception:
            pass

    application_audits, approved_day_maps, day_app_maps = _load_application_audits(
        emp_names, start_ad, end_ad
    )
    leave_day_map = _load_leave_day_map(emp_names, start_ad, end_ad)
    leave_type_details = _get_leave_type_details()

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
        "leave_apps": [],
        "leave_type_details": leave_type_details,
        "application_audits": application_audits,
        "lea_map": approved_day_maps.get("late_entry", {}),
        "eea_map": approved_day_maps.get("early_exit", {}),
        "ooo_map": approved_day_maps.get("out_of_office", {}),
        "day_app_maps": day_app_maps,
        "leave_day_map": leave_day_map,
    }, leave_types


def _get_leave_type_details():
    fields = ["name", "is_lwp"]
    meta = frappe.get_meta("Leave Type")
    group_field = "custom_attendance_sheet_leave_group"
    acronym_field = "custom_attendance_sheet_acronym"
    if meta.has_field(group_field):
        fields.append(group_field)
    if meta.has_field(acronym_field):
        fields.append(acronym_field)
    rows = frappe.get_all("Leave Type", fields=fields, ignore_permissions=True)
    details = {}
    for row in rows:
        group = getattr(row, group_field, None) or LEAVE_GROUP_OTHER
        details[row.name] = frappe._dict(
            is_lwp=bool(cint(row.is_lwp)),
            group=group,
            configured=bool(getattr(row, group_field, None)),
            acronym=format_leave_type_acronym(
                row.name, getattr(row, acronym_field, None)
            ),
        )
    return details


def _empty_application_stats(spec):
    return {
        "doctype": spec["doctype"],
        "label": str(spec["label"]),
        "approved": 0,
        "pending": 0,
        "rejected": 0,
        "details": [],
    }


def _application_bucket(row):
    status = (getattr(row, "status", None) or "").strip()
    if status == "Rejected":
        return "rejected"
    if cint(row.docstatus) == 1 and status in ("Approved", ""):
        return "approved"
    if status == "Approved" and cint(row.docstatus) == 1:
        return "approved"
    return "pending"


def _application_detail(row, kind):
    detail = {
        "name": row.name,
        "status": _application_bucket(row),
        "status_label": (getattr(row, "status", None) or "").strip(),
    }
    if kind == "attendance_request":
        detail["from_date"] = str(row.from_date)
        detail["to_date"] = str(row.to_date)
    else:
        detail["attendance_date"] = str(row.attendance_date)
    for fieldname in (
        "reason",
        "explanation",
        "description",
        "type_of_work",
        "custom_rejection_reason",
        "estimated_late_entry_time",
        "late_entry_time",
        "estimated_from_time",
        "estimated_to_time",
        "from_time",
        "to_time",
        "total_hours",
    ):
        value = getattr(row, fieldname, None)
        if value is not None and value != "":
            detail[fieldname] = str(value)
    return detail


def _application_fields(doctype, ranged=False):
    meta = frappe.get_meta(doctype)
    fields = ["name", "employee", "docstatus", "status"]
    fields.extend(["from_date", "to_date"] if ranged else ["attendance_date"])
    for fieldname in (
        "reason",
        "explanation",
        "description",
        "type_of_work",
        "custom_rejection_reason",
        "estimated_late_entry_time",
        "late_entry_time",
        "estimated_from_time",
        "estimated_to_time",
        "from_time",
        "to_time",
        "total_hours",
    ):
        if meta.has_field(fieldname):
            fields.append(fieldname)
    return fields


def _doctype_slug(doctype):
    return str(doctype or "").strip().lower().replace(" ", "-")


def _append_linked_application(day_applications, seen_apps, doctype, name, existing):
    if not name:
        return
    key = (doctype, name)
    if key in seen_apps:
        return
    match = next((app for app in existing or [] if app.get("name") == name), None)
    if match:
        seen_apps.add(key)
        day_applications.append(match)
        return
    meta = frappe.get_meta(doctype)
    fields = ["status", "docstatus"]
    for fieldname in (
        "reason",
        "explanation",
        "description",
        "type_of_work",
        "custom_rejection_reason",
        "leave_type",
        "half_day",
    ):
        if meta.has_field(fieldname):
            fields.append(fieldname)
    values = frappe.db.get_value(doctype, name, fields, as_dict=True)
    if not values:
        return
    detail = {
        "name": name,
        "doctype": doctype,
        "slug": _doctype_slug(doctype),
        "status": _application_bucket(values),
        "status_label": (values.status or "").strip(),
    }
    for fieldname in (
        "reason",
        "explanation",
        "description",
        "type_of_work",
        "custom_rejection_reason",
        "leave_type",
    ):
        value = values.get(fieldname)
        if value not in (None, ""):
            detail[fieldname] = str(value)
    if values.get("half_day") is not None:
        detail["half_day"] = cint(values.half_day)
    day_applications.append(detail)
    seen_apps.add(key)


def _expand_ranged_days(from_date, to_date, start_ad, end_ad):
    cur = max(getdate(from_date), start_ad)
    last = min(getdate(to_date), end_ad)
    days = []
    while cur <= last:
        days.append(cur)
        cur = add_days(cur, 1)
    return days


def _checkin_time_label(when):
    label = when.strftime("%I:%M %p").lower()
    if label.startswith("0"):
        label = label[1:]
    return label


def _checkin_payloads(day_checkins):
    payloads = []
    first_in = None
    last_out = None
    for row in day_checkins or []:
        when = get_datetime(row.time)
        log_type = (row.log_type or "").upper()
        att_type = (getattr(row, "custom_attendance_type", None) or "Normal").strip()
        item = {
            "time": when.strftime("%H:%M"),
            "time_label": _checkin_time_label(when),
            "log_type": log_type or "—",
            "attendance_type": att_type,
            "reason": getattr(row, "custom_reason", None) or "",
        }
        payloads.append(item)
        if log_type == "IN" and first_in is None:
            first_in = item["time_label"]
        if log_type == "OUT":
            last_out = item["time_label"]
    return payloads, first_in, last_out


def _load_leave_day_map(emp_names, start_ad, end_ad):
    leave_map = {}
    if not emp_names or not frappe.db.exists("DocType", "Leave Application"):
        return leave_map
    rows = frappe.get_all(
        "Leave Application",
        filters={
            "employee": ["in", emp_names],
            "docstatus": ["<", 2],
            "status": ["!=", "Cancelled"],
            "from_date": ["<=", end_ad],
            "to_date": [">=", start_ad],
        },
        fields=[
            "name",
            "employee",
            "status",
            "docstatus",
            "from_date",
            "to_date",
            "leave_type",
            "half_day",
            "half_day_date",
            "description",
        ],
        order_by="employee asc, from_date asc",
        ignore_permissions=True,
    )
    for app in rows:
        bucket = _application_bucket(app)
        detail = {
            "name": app.name,
            "doctype": "Leave Application",
            "slug": "leave-application",
            "status": bucket,
            "status_label": (getattr(app, "status", None) or "").strip() or bucket.title(),
            "leave_type": app.leave_type,
            "half_day": cint(app.half_day),
            "from_date": str(app.from_date),
            "to_date": str(app.to_date),
            "description": (getattr(app, "description", None) or "").strip(),
        }
        if getattr(app, "half_day_date", None):
            detail["half_day_date"] = str(app.half_day_date)
        for day in _expand_ranged_days(app.from_date, app.to_date, start_ad, end_ad):
            leave_map.setdefault((app.employee, day), []).append(detail)
    return leave_map


def _load_application_audits(emp_names, start_ad, end_ad):
    audits = {
        employee: {
            kind: _empty_application_stats(spec)
            for kind, spec in APPLICATION_SPECS.items()
        }
        for employee in emp_names
    }
    approved_day_maps = {
        "late_entry": {},
        "early_exit": {},
        "out_of_office": {},
    }
    day_app_maps = {
        "attendance_request": {},
        "late_entry": {},
        "early_exit": {},
        "out_of_office": {},
    }
    if not emp_names:
        return audits, approved_day_maps, day_app_maps

    for kind, spec in APPLICATION_SPECS.items():
        doctype = spec["doctype"]
        if not frappe.db.exists("DocType", doctype):
            continue
        ranged = kind == "attendance_request"
        filters = {
            "employee": ["in", emp_names],
            "docstatus": ["<", 2],
        }
        if ranged:
            filters.update({"from_date": ["<=", end_ad], "to_date": [">=", start_ad]})
        else:
            filters["attendance_date"] = ["between", [start_ad, end_ad]]
        rows = frappe.get_all(
            doctype,
            filters=filters,
            fields=_application_fields(doctype, ranged),
            order_by="employee asc, modified asc",
            ignore_permissions=True,
        )
        for app in rows:
            bucket = _application_bucket(app)
            stats = audits[app.employee][kind]
            stats[bucket] += 1
            detail = _application_detail(app, kind)
            detail["doctype"] = doctype
            detail["slug"] = _doctype_slug(doctype)
            stats["details"].append(detail)
            if ranged:
                days = _expand_ranged_days(app.from_date, app.to_date, start_ad, end_ad)
            else:
                days = [getdate(app.attendance_date)]
            for day in days:
                day_app_maps[kind].setdefault((app.employee, day), []).append(detail)
            if not ranged and bucket == "approved":
                key = (app.employee, getdate(app.attendance_date))
                approved_day_maps[kind].setdefault(key, []).append(app.name)
    return audits, approved_day_maps, day_app_maps


def _leave_acronym(leave_type, leave_type_details):
    details = leave_type_details.get(leave_type) if leave_type else None
    if details and details.get("acronym"):
        return details.acronym
    return leave_type_acronym(leave_type)


def _half_day_other_half(status_abbr, leave_type, leave_type_details):
    """Label for the non-worked half of a half-day attendance cell."""
    if leave_type:
        return _leave_acronym(leave_type, leave_type_details), "leave", leave_type
    if status_abbr == "HD/A":
        return "Ab", "absent", _("Absent (half day)")
    return "Ab", "absent", _("Absent / unpaid half")


def _new_day_classification():
    return {
        "present_full": 0.0,
        "present_half": 0.0,
        "absent_full": 0.0,
        "absent_half": 0.0,
        "lwp_full": 0.0,
        "lwp_half": 0.0,
        "paid_leave_full": 0.0,
        "paid_leave_half": 0.0,
        "annual_home_leave": 0.0,
        "sick_leave": 0.0,
        "other_paid_leave": 0.0,
        "holiday": 0.0,
        "holiday_extra_present": 0.0,
        "holiday_extra_hours": 0.0,
        "paid_flag": 0.0,
        "unmarked": 0,
        "unclassified_leave": 0,
        "sandwich": 0,
        "sandwich_absent": 0.0,
        "leave_breakdown": {},
        "lwp_breakdown": {},
        "other_paid_breakdown": {},
        "unconfigured_paid_leave_breakdown": {},
    }


def _include_in_paid_day_audit(
    attendance_date,
    current_date,
    *,
    has_attendance=False,
    is_holiday=False,
    is_sandwich=False,
):
    """Exclude future days and an unmarked current working day from paid totals."""
    attendance_date = getdate(attendance_date)
    current_date = getdate(current_date)
    if attendance_date > current_date:
        return False
    if attendance_date < current_date:
        return True
    return bool(has_attendance or is_holiday or is_sandwich)


def _add_leave_unit(day, leave_type, amount, leave_type_details, full=False):
    details = leave_type_details.get(leave_type) if leave_type else None
    if not details:
        day["unclassified_leave"] += 1
        return
    suffix = "full" if full else "half"
    target_breakdown = (
        day["lwp_breakdown"] if details.is_lwp else day["leave_breakdown"]
    )
    target_breakdown[leave_type] = target_breakdown.get(leave_type, 0) + amount
    if details.is_lwp:
        day[f"lwp_{suffix}"] += amount
        return

    day[f"paid_leave_{suffix}"] += amount
    group = details.group or LEAVE_GROUP_OTHER
    if group == LEAVE_GROUP_ANNUAL_HOME:
        day["annual_home_leave"] += amount
    elif group == LEAVE_GROUP_SICK:
        day["sick_leave"] += amount
    else:
        day["other_paid_leave"] += amount
        day["other_paid_breakdown"][leave_type] = (
            day["other_paid_breakdown"].get(leave_type, 0) + amount
        )
    if not details.configured:
        day["unconfigured_paid_leave_breakdown"][leave_type] = (
            day["unconfigured_paid_leave_breakdown"].get(leave_type, 0) + amount
        )


def classify_attendance_day(
    *,
    status=None,
    half_day_status=None,
    leave_type=None,
    working_hours=0,
    is_holiday=False,
    is_sandwich=False,
    sandwich_leave_type=None,
    leave_type_details=None,
):
    """Return mutually exclusive paid/unpaid units for one employee-date."""
    leave_type_details = leave_type_details or {}
    status = (status or "").strip()
    day = _new_day_classification()

    if is_holiday and is_sandwich:
        day["sandwich"] = 1
        effective_leave = sandwich_leave_type or (
            leave_type if status == "On Leave" else None
        )
        if effective_leave:
            _add_leave_unit(
                day, effective_leave, 1.0, leave_type_details, full=True
            )
        else:
            day["absent_full"] = 1.0
            day["sandwich_absent"] = 1.0
        day["paid_flag"] = (
            day["paid_leave_full"] + day["paid_leave_half"]
        )
        return day

    if is_holiday or status in ("Holiday", "Weekly Off"):
        day["holiday"] = 1.0
        day["paid_flag"] = 1.0
        if status in ("Present", "Work From Home"):
            day["holiday_extra_present"] = 1.0
            day["holiday_extra_hours"] = flt(working_hours)
        elif status == "Half Day" and half_day_status == "Present":
            day["holiday_extra_present"] = 0.5
            day["holiday_extra_hours"] = flt(working_hours)
        return day

    if status in ("Present", "Work From Home"):
        day["present_full"] = 1.0
        day["paid_flag"] = 1.0
        return day
    if status == "Absent":
        day["absent_full"] = 1.0
        return day
    if status == "On Leave":
        _add_leave_unit(day, leave_type, 1.0, leave_type_details, full=True)
        day["paid_flag"] = day["paid_leave_full"]
        return day
    if status == "Half Day":
        if half_day_status == "Present":
            day["present_half"] = 0.5
        else:
            day["absent_half"] = 0.5
        if leave_type:
            _add_leave_unit(day, leave_type, 0.5, leave_type_details, full=False)
        else:
            day["absent_half"] += 0.5
        day["paid_flag"] = (
            day["present_half"] + day["paid_leave_half"]
        )
        return day

    day["unmarked"] = 1
    return day


def _merge_breakdown(target, source):
    for key, value in source.items():
        target[key] = target.get(key, 0) + flt(value)


def _accumulate_day(row, day):
    fields = (
        "present_full",
        "present_half",
        "absent_full",
        "absent_half",
        "lwp_full",
        "lwp_half",
        "paid_leave_full",
        "paid_leave_half",
        "annual_home_leave",
        "sick_leave",
        "other_paid_leave",
        "holiday",
        "holiday_extra_present",
        "holiday_extra_hours",
        "paid_flag",
        "unmarked",
        "unclassified_leave",
        "sandwich",
        "sandwich_absent",
    )
    for fieldname in fields:
        row[fieldname] = row.get(fieldname, 0) + day.get(fieldname, 0)
    _merge_breakdown(row["leave_breakdown"], day["leave_breakdown"])
    _merge_breakdown(row["lwp_breakdown"], day["lwp_breakdown"])
    _merge_breakdown(
        row["other_paid_breakdown"], day["other_paid_breakdown"]
    )
    _merge_breakdown(
        row["unconfigured_paid_leave_breakdown"],
        day["unconfigured_paid_leave_breakdown"],
    )


def _finalize_paid_days(row, tolerance=0.05):
    row["total_present"] = flt(row["present_full"]) + flt(row["present_half"])
    row["total_absent"] = flt(row["absent_full"]) + flt(row["absent_half"])
    row["lwp_days"] = flt(row["lwp_full"]) + flt(row["lwp_half"])
    row["paid_leave_days"] = flt(row["paid_leave_full"]) + flt(
        row["paid_leave_half"]
    )
    row["total_holiday"] = flt(row["holiday"])
    row["annual_home_leave_days"] = flt(row["annual_home_leave"])
    row["sick_leave_days"] = flt(row["sick_leave"])
    row["other_paid_leave_days"] = flt(row["other_paid_leave"])

    method_period = (
        flt(row["total_days_in_period"])
        - flt(row["lwp_days"])
        - flt(row["total_absent"])
    )
    method_components = (
        flt(row["total_present"])
        + flt(row["paid_leave_days"])
        + flt(row["total_holiday"])
    )
    method_daily = flt(row["paid_flag"])
    row["paid_days_period_method"] = method_period
    row["paid_days_component_method"] = method_components
    row["paid_days_daily_method"] = method_daily
    row["payable_days"] = method_daily
    row["payable_days_policy"] = method_daily
    row["payable_days_mismatch"] = int(
        abs(method_period - method_daily) > tolerance
        or abs(method_components - method_daily) > tolerance
    )


def _occurrence_audits(attendance_map, settings, employee_names=None):
    counts = defaultdict(
        lambda: {
            "late_minor": 0,
            "late_major": 0,
            "early_minor": 0,
            "early_major": 0,
        }
    )
    for att in attendance_map.values():
        item = counts[att.employee]
        item["late_minor"] += cint(
            getattr(att, "custom_cnr_late_in_pool", 0) or 0
        )
        item["early_minor"] += cint(
            getattr(att, "custom_cnr_early_in_pool", 0) or 0
        )
        item["late_major"] += cint(
            getattr(att, "custom_cnr_unexcused_late", 0) or 0
        )
        item["early_major"] += cint(
            getattr(att, "custom_cnr_unexcused_early", 0) or 0
        )
    for employee in employee_names or []:
        counts[employee]

    initial = cint(getattr(settings, "initial_grace_occurrences", 2) or 2)
    step = cint(getattr(settings, "subsequent_grace_step_occurrences", 2) or 2)
    combine = cint(getattr(settings, "combine_late_and_early_pool", 0) or 0)
    escalation_enabled = cint(
        getattr(settings, "enable_late_full_day_escalation", 0) or 0
    )
    escalation_after = cint(
        getattr(settings, "late_full_day_after_occurrences", 5) or 5
    )
    penalty_enabled = cint(
        getattr(settings, "enable_late_early_penalty", 0) or 0
    )

    result = {}
    for employee, item in counts.items():
        if combine:
            minor = item["late_minor"] + item["early_minor"]
            major = item["late_major"] + item["early_major"]
            combined_penalty = split_occurrence_penalty(
                minor,
                major,
                initial,
                step,
                escalation_enabled,
                escalation_after,
            )
            late_penalty = combined_penalty
            early_penalty = combined_penalty
            free_remaining = free_occurrences_remaining(minor, initial, step)
        else:
            late_penalty = split_occurrence_penalty(
                item["late_minor"],
                item["late_major"],
                initial,
                step,
                escalation_enabled,
                escalation_after,
            )
            early_penalty = split_occurrence_penalty(
                item["early_minor"],
                item["early_major"],
                initial,
                step,
                escalation_enabled,
                escalation_after,
            )
            free_remaining = {
                "late": free_occurrences_remaining(
                    item["late_minor"], initial, step
                ),
                "early": free_occurrences_remaining(
                    item["early_minor"], initial, step
                ),
            }
        result[employee] = {
            **item,
            "penalty_enabled": penalty_enabled,
            "combine_pools": combine,
            "initial_grace_occurrences": initial,
            "subsequent_grace_step_occurrences": step,
            "full_day_escalation_enabled": escalation_enabled,
            "full_day_escalation_threshold": escalation_after,
            "free_remaining": free_remaining,
            "late_half_days": flt(late_penalty.half_days),
            "late_full_days": flt(late_penalty.full_days),
            "late_escalated": bool(late_penalty.escalated),
            "early_half_days": flt(early_penalty.half_days),
            "early_full_days": flt(early_penalty.full_days),
            "early_escalated": bool(early_penalty.escalated),
        }
    return result


def _covering_leave_from_rows(leave_rows, day):
    day = getdate(day)
    for leave in leave_rows:
        if getdate(leave.from_date) <= day <= getdate(leave.to_date):
            return leave
    return None


def _is_full_day_leave_row(leave, day):
    if not leave:
        return False
    if not cint(leave.half_day):
        return True
    return not (
        leave.half_day_date
        and getdate(leave.half_day_date) == getdate(day)
    )


def _escape_covers_day(escape, day):
    day = getdate(day)
    return (
        (not escape.from_date or getdate(escape.from_date) <= day)
        and (not escape.to_date or getdate(escape.to_date) >= day)
    )


def _build_sandwich_map(
    employees,
    start_ad,
    end_ad,
    holidays_by_list,
    company_holiday_list,
    settings,
):
    """Batch-resolve sandwich holidays without per-employee/day SQL queries."""
    if not cint(getattr(settings, "enable_leave_sandwich_rule", 0) or 0):
        return {}

    employee_names = [employee.name for employee in employees]
    if not employee_names:
        return {}
    buffer_start = add_days(start_ad, -40)
    buffer_end = add_days(end_ad, 40)
    anchor_rows = frappe.get_all(
        "Attendance",
        filters={
            "employee": ["in", employee_names],
            "attendance_date": ["between", [buffer_start, buffer_end]],
            "docstatus": 1,
        },
        fields=[
            "employee",
            "attendance_date",
            "status",
            "half_day_status",
            "leave_type",
        ],
        ignore_permissions=True,
    )
    anchor_map = {
        (row.employee, getdate(row.attendance_date)): row for row in anchor_rows
    }

    leave_rows = frappe.get_all(
        "Leave Application",
        filters={
            "employee": ["in", employee_names],
            "from_date": ["<=", buffer_end],
            "to_date": [">=", buffer_start],
            "docstatus": 1,
            "status": "Approved",
        },
        fields=[
            "employee",
            "from_date",
            "to_date",
            "leave_type",
            "half_day",
            "half_day_date",
            "modified",
        ],
        order_by="modified desc",
        ignore_permissions=True,
    )
    leaves_by_employee = defaultdict(list)
    for leave in leave_rows:
        leaves_by_employee[leave.employee].append(leave)

    escapes_by_employee = defaultdict(list)
    if frappe.db.exists("DocType", "Attendance Policy Escape"):
        escape_rows = frappe.get_all(
            "Attendance Policy Escape",
            filters={
                "employee": ["in", employee_names],
                "is_active": 1,
                "escape_sandwich": 1,
            },
            fields=["employee", "from_date", "to_date"],
            ignore_permissions=True,
        )
        for escape in escape_rows:
            escapes_by_employee[escape.employee].append(escape)

    result = {}
    for employee in employees:
        holiday_list = employee.holiday_list or company_holiday_list
        holidays = holidays_by_list.get(holiday_list, {})
        if not holidays:
            continue
        employee_leaves = leaves_by_employee.get(employee.name, [])

        def adjacent_working_day(day, direction):
            candidate = add_days(day, direction)
            for _ in range(40):
                if candidate not in holidays:
                    return candidate
                candidate = add_days(candidate, direction)
            return None

        def full_leave_or_absent(day):
            attendance = anchor_map.get((employee.name, day))
            if attendance:
                status = (attendance.status or "").strip()
                if status in ("Present", "Work From Home", "Half Day"):
                    return False
                return status in ("Absent", "On Leave")
            leave = _covering_leave_from_rows(employee_leaves, day)
            return _is_full_day_leave_row(leave, day)

        day = getdate(start_ad)
        while day <= getdate(end_ad):
            if day not in holidays:
                day = add_days(day, 1)
                continue
            if any(
                _escape_covers_day(escape, day)
                for escape in escapes_by_employee.get(employee.name, [])
            ):
                day = add_days(day, 1)
                continue
            previous_day = adjacent_working_day(day, -1)
            next_day = adjacent_working_day(day, 1)
            if not previous_day or not next_day:
                is_sandwich, leave_type = _sandwich_day(
                    employee.name, day, True, settings
                )
                if is_sandwich:
                    result[(employee.name, day)] = leave_type
                day = add_days(day, 1)
                continue
            if (
                previous_day
                and next_day
                and full_leave_or_absent(previous_day)
                and full_leave_or_absent(next_day)
            ):
                covering_leave = _covering_leave_from_rows(employee_leaves, day)
                result[(employee.name, day)] = (
                    covering_leave.leave_type if covering_leave else None
                )
            day = add_days(day, 1)
    return result


def _sandwich_day(employee, day, is_holiday, settings):
    if not is_holiday or not cint(
        getattr(settings, "enable_leave_sandwich_rule", 0) or 0
    ):
        return False, None
    try:
        from nepal_hrms.custom_code.attendance_holiday import (
            covering_leave_application,
            is_sandwiched,
        )

        if not is_sandwiched(employee, day):
            return False, None
        leave = covering_leave_application(employee, day)
        return True, leave.leave_type if leave else None
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"Monthly Attendance Sheet sandwich audit: {employee} {day}",
        )
        return False, None


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
    show_details = bool(cint(filters.get("show_details")))
    employees = att_data["employees"]
    attendance_map = att_data["attendance_map"]
    checkin_map = att_data["checkin_map"]
    shift_map = att_data.get("shift_map", {})
    shift_type_details = att_data.get("shift_type_details", {})
    leave_apps = att_data.get("leave_apps", [])
    leave_type_details = att_data.get("leave_type_details", {})
    application_audits = att_data.get("application_audits", {})
    lea_map = att_data.get("lea_map", {})
    eea_map = att_data.get("eea_map", {})
    ooo_map = att_data.get("ooo_map", {})
    day_app_maps = att_data.get("day_app_maps") or {}
    leave_day_map = att_data.get("leave_day_map") or {}

    try:
        settings = get_hr_settings()
        grace_mins = cint(getattr(settings, "late_early_grace_mins", None) or 15)
    except Exception:
        settings = frappe._dict()
        grace_mins = 15
    occurrence_audits = _occurrence_audits(
        attendance_map, settings, [employee.name for employee in employees]
    )

    company_holiday_list = frappe.db.get_value('Company', filters.get('company'), 'default_holiday_list')
    holiday_lists = set(e.holiday_list for e in employees if e.holiday_list)
    if company_holiday_list: holiday_lists.add(company_holiday_list)

    holidays_by_list = {}
    holiday_buffer_start = add_days(start_ad, -40)
    holiday_buffer_end = add_days(end_ad, 40)
    for hl in holiday_lists:
        h_records = frappe.get_all(
            "Holiday",
            filters={
                "parent": hl,
                "holiday_date": [
                    "between",
                    [holiday_buffer_start, holiday_buffer_end],
                ],
            },
            fields=["holiday_date", "weekly_off"],
            ignore_permissions=True,
        )
        holidays_by_list[hl] = {getdate(h.holiday_date): bool(h.weekly_off) for h in h_records}
    sandwich_map = _build_sandwich_map(
        employees,
        start_ad,
        end_ad,
        holidays_by_list,
        company_holiday_list,
        settings,
    )

    selected_days_in_period = (end_ad - start_ad).days + 1
    current_date = getdate(today())
    data = []
    period_start = str(start_ad)
    period_end = str(end_ad)

    for emp in employees:
        row = {
            "employee": emp.name, "employee_name": emp.employee_name,
            "period_start": period_start, "period_end": period_end,
            "selected_period_days": selected_days_in_period,
            "total_days_in_period": 0,
            "audit_through_date": None,
            "future_days_excluded": 0,
            "unmarked_today_excluded": 0,
            "total_late_entry": 0, "total_early_exit": 0,
            "total_grace_late": 0, "total_unexcused_late": 0,
            "total_no_of_days": 0, "total_present": 0, "total_absent": 0,
            "total_holiday": 0, "payable_days": 0, "payable_days_policy": 0,
            "payable_days_mismatch": 0, "lwp_days": 0, "paid_leave_days": 0,
            "present_full": 0, "present_half": 0,
            "absent_full": 0, "absent_half": 0,
            "lwp_full": 0, "lwp_half": 0,
            "paid_leave_full": 0, "paid_leave_half": 0,
            "annual_home_leave": 0, "sick_leave": 0, "other_paid_leave": 0,
            "annual_home_leave_days": 0, "sick_leave_days": 0,
            "other_paid_leave_days": 0,
            "holiday": 0, "paid_flag": 0, "unmarked": 0,
            "unclassified_leave": 0, "sandwich": 0, "sandwich_absent": 0,
            "holiday_extra_present": 0, "holiday_extra_hours": 0,
            "leave_breakdown": {}, "lwp_breakdown": {},
            "other_paid_breakdown": {},
            "unconfigured_paid_leave_breakdown": {},
            "application_audits": application_audits.get(emp.name, {}),
            "occurrence_audit": occurrence_audits.get(emp.name, {}),
        }
        for kind, spec in APPLICATION_SPECS.items():
            stats = row["application_audits"].get(kind) or _empty_application_stats(
                spec
            )
            row[spec["fieldname"]] = cint(stats.get("approved"))

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
            if show_details and day_checkins:
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
            status = ""

            is_holiday = curr in emp_holidays
            if is_holiday:
                status_abbr = "WO" if emp_holidays[curr] else "Hol"
                target_hours = 0.0

            late_entry = False
            early_exit = False
            late_mins = 0
            early_mins = 0
            day_lea = lea_map.get(key) or []
            day_eea = eea_map.get(key) or []
            day_ooo = ooo_map.get(key) or []
            day_leave_apps = leave_day_map.get(key) or []
            day_applications = []
            seen_apps = set()
            for kind in ("attendance_request", "late_entry", "early_exit", "out_of_office"):
                for app in day_app_maps.get(kind, {}).get(key, []):
                    app_key = (app.get("doctype"), app.get("name"))
                    if app_key in seen_apps:
                        continue
                    seen_apps.add(app_key)
                    day_applications.append(app)
            for app in day_leave_apps:
                app_key = (app.get("doctype"), app.get("name"))
                if app_key in seen_apps:
                    continue
                seen_apps.add(app_key)
                day_applications.append(app)
            if not leave_type:
                for app in day_leave_apps:
                    if app.get("leave_type"):
                        leave_type = app["leave_type"]
                        break
            if att:
                _append_linked_application(
                    day_applications,
                    seen_apps,
                    "Attendance Request",
                    getattr(att, "attendance_request", None),
                    day_app_maps.get("attendance_request", {}).get(key) or [],
                )
                _append_linked_application(
                    day_applications,
                    seen_apps,
                    "Leave Application",
                    getattr(att, "leave_application", None),
                    day_leave_apps,
                )
            for name in day_lea:
                _append_linked_application(
                    day_applications,
                    seen_apps,
                    "Late Entry Application",
                    name,
                    day_app_maps.get("late_entry", {}).get(key) or [],
                )
            for name in day_eea:
                _append_linked_application(
                    day_applications,
                    seen_apps,
                    "Early Exit Application",
                    name,
                    day_app_maps.get("early_exit", {}).get(key) or [],
                )
            for name in day_ooo:
                _append_linked_application(
                    day_applications,
                    seen_apps,
                    "Out of Office Application",
                    name,
                    day_app_maps.get("out_of_office", {}).get(key) or [],
                )

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

                if show_details:
                    row[f"{fieldname}_wh"] = wh
                leave_type = att.leave_type or leave_type
                is_half_day = 1 if status == "Half Day" else 0

                if status == "Present":
                    status_abbr = "P"
                elif status == "Absent":
                    status_abbr = "Ab"
                    target_hours = 0.0
                elif status == "Half Day":
                    status_abbr = "HD/P" if att.half_day_status == "Present" else "HD/A"
                    target_hours = 4.0
                elif status == "On Leave":
                    status_abbr = "Lv"
                    target_hours = 0.0
                elif status == "Work From Home":
                    status_abbr = "WFH"
                elif status in ["Weekly Off", "Holiday"]:
                    status_abbr = "WO" if status == "Weekly Off" else "Hol"
                    target_hours = 0.0

                if wh > 0:
                    wh_str = f"{int(wh)}h" if wh == int(wh) else f"{round(wh, 1)}h"

            is_sandwich = key in sandwich_map
            sandwich_leave_type = sandwich_map.get(key)
            if is_sandwich:
                if sandwich_leave_type:
                    leave_type = sandwich_leave_type
                    status_abbr = "Lv"
                else:
                    leave_type = ""
                    status_abbr = "Ab"
                target_hours = 0.0
                is_half_day = 0

            day_classification = classify_attendance_day(
                status=status,
                half_day_status=getattr(att, "half_day_status", None) if att else None,
                leave_type=leave_type,
                working_hours=wh,
                is_holiday=is_holiday,
                is_sandwich=is_sandwich,
                sandwich_leave_type=sandwich_leave_type,
                leave_type_details=leave_type_details,
            )
            include_in_paid_audit = _include_in_paid_day_audit(
                curr,
                current_date,
                has_attendance=bool(att),
                is_holiday=is_holiday,
                is_sandwich=is_sandwich,
            )
            if include_in_paid_audit:
                row["total_days_in_period"] += 1
                row["audit_through_date"] = str(curr)
                _accumulate_day(row, day_classification)
                total_worked += wh
                if late_entry:
                    row["total_late_entry"] += 1
                if early_exit:
                    row["total_early_exit"] += 1
            elif curr > current_date:
                row["future_days_excluded"] += 1
            else:
                row["unmarked_today_excluded"] = 1
            worked_on_holiday = bool(
                day_classification["holiday_extra_present"]
            )

            if not att and not is_holiday:
                target_hours = 0.0

            if include_in_paid_audit:
                total_target += target_hours
            # Build bar data for this day
            if not att and not day_checkins:
                bar_data = {
                    "is_weekly_off": bool(emp_holidays.get(curr))
                    if is_holiday
                    else False,
                    "is_leave": False,
                    "segments": [],
                }
            else:
                bar_data = build_bar_data(
                    emp.name, curr, day_checkins, att, is_holiday,
                    emp_holidays.get(curr), shift_map, shift_type_details, leave_apps,
                    status_abbr, emp.default_shift
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

            if include_in_paid_audit and late_kind == "grace":
                row["total_grace_late"] += 1
            elif include_in_paid_audit and late_kind == "unexcused":
                row["total_unexcused_late"] += 1

            other_half_label, other_half_kind, other_half_title = "", "", ""
            if is_half_day and status_abbr in ("HD/P", "HD/A"):
                other_half_label, other_half_kind, other_half_title = _half_day_other_half(
                    status_abbr, leave_type, leave_type_details
                )

            checkin_logs, first_in, last_out = _checkin_payloads(day_checkins)
            if att:
                if not first_in and att.in_time:
                    first_in = _checkin_time_label(get_datetime(att.in_time))
                if not last_out and att.out_time:
                    last_out = _checkin_time_label(get_datetime(att.out_time))

            leave_app_status = None
            if day_leave_apps:
                leave_app_status = day_leave_apps[0].get("status_label") or day_leave_apps[0].get("status")

            # Store EVERYTHING in the main field as JSON for the formatter
            row[fieldname] = json.dumps({
                "status": status_abbr,
                "wh": wh_str,
                "checks": checks_str,
                "checkins": checkin_logs,
                "in_time": first_in,
                "out_time": last_out,
                "target": target_hours,
                "leave_type": leave_type,
                "leave_acronym": (
                    _leave_acronym(leave_type, leave_type_details)
                    if leave_type
                    else ""
                ),
                "leave_app_status": leave_app_status,
                "other_half_label": other_half_label,
                "other_half_kind": other_half_kind,
                "other_half_title": other_half_title,
                "half_day": is_half_day,
                "late_mins": late_mins,
                "early_mins": early_mins,
                "late_kind": late_kind,
                "early_kind": early_kind,
                "bar_data": bar_data,
                "attendance_doc": att.name if att else None,
                "attendance_status": status or None,
                "late_entry_app": day_lea[0] if day_lea else None,
                "early_exit_app": day_eea[0] if day_eea else None,
                "ooo_app": day_ooo[0] if day_ooo else None,
                "attendance_request": getattr(att, "attendance_request", None) if att else None,
                "leave_application": getattr(att, "leave_application", None) if att else None,
                "applications": day_applications,
                "worked_on_holiday": worked_on_holiday,
                "sandwich": is_sandwich,
                "paid_day_audit_included": include_in_paid_audit,
            })

            curr = add_days(curr, 1)

        _finalize_paid_days(row)
        row["total_no_of_days"] = (
            row["total_present"] + row["holiday_extra_present"]
        )

        w_h, w_m = divmod(int(total_worked * 60), 60)
        t_h, t_m = divmod(int(total_target * 60), 60)
        row["summary"] = f"{w_h}:{w_m:02d} / {t_h}:{t_m:02d}"
        data.append(row)

    return data


def build_bar_data(
    employee,
    date,
    checkins,
    att,
    is_holiday,
    is_weekly_off,
    shift_map,
    shift_type_details,
    leave_apps,
    status_abbr,
    default_shift=None,
):
    """Build time bar segment data for a single employee-day."""
    result = {
        "shift_start": None,
        "shift_end": None,
        "is_weekly_off": bool(is_weekly_off) if is_holiday else False,
        "is_leave": status_abbr == "Lv",
        "is_half_day": status_abbr in ("HD/P", "HD/A"),
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
        shift_type_name = (
            (getattr(att, "shift", None) if att else None) or default_shift
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

    result["shift_start"] = st_detail["start_time"]
    result["shift_end"] = st_detail["end_time"]
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

    if result["is_half_day"]:
        segments = _convert_segments_for_half_day(
            segments, status_abbr, shift_start_mins, shift_end_mins
        )

    # Sort segments by start time and clean up internal fields
    segments.sort(key=lambda s: s["start"])
    for seg in segments:
        seg.pop("start_mins", None)
        seg.pop("end_mins", None)

    result["segments"] = segments
    return result


def _convert_segments_for_half_day(segments, status_abbr, shift_start_mins, shift_end_mins):
    """Mark the leave half of the shift as halfday instead of stacking purple on green."""
    if not segments:
        half_point = shift_start_mins + (shift_end_mins - shift_start_mins) // 2
        if status_abbr == "HD/A":
            leave_lo, leave_hi = half_point, shift_end_mins
        else:
            leave_lo, leave_hi = shift_start_mins, half_point
        return [{
            "start": _minutes_to_time(leave_lo),
            "end": _minutes_to_time(leave_hi),
            "type": "halfday",
            "start_mins": leave_lo,
            "end_mins": leave_hi,
        }]

    half_point = shift_start_mins + (shift_end_mins - shift_start_mins) // 2
    if status_abbr == "HD/A":
        leave_lo, leave_hi = half_point, shift_end_mins
    else:
        leave_lo, leave_hi = shift_start_mins, half_point

    converted = []
    for seg in segments:
        s = seg.get("start_mins")
        e = seg.get("end_mins")
        if s is None:
            s = _time_to_minutes(seg["start"])
            e = _time_to_minutes(seg["end"])

        ov_lo = max(s, leave_lo)
        ov_hi = min(e, leave_hi)
        if ov_lo >= ov_hi:
            converted.append(dict(seg, start_mins=s, end_mins=e))
            continue

        if s < ov_lo:
            converted.append({
                "start": _minutes_to_time(s),
                "end": _minutes_to_time(ov_lo),
                "type": seg["type"],
                "start_mins": s,
                "end_mins": ov_lo,
            })
        leave_type = "halfday" if seg["type"] != "extra" else seg["type"]
        converted.append({
            "start": _minutes_to_time(ov_lo),
            "end": _minutes_to_time(ov_hi),
            "type": leave_type,
            "start_mins": ov_lo,
            "end_mins": ov_hi,
        })
        if e > ov_hi:
            converted.append({
                "start": _minutes_to_time(ov_hi),
                "end": _minutes_to_time(e),
                "type": seg["type"],
                "start_mins": ov_hi,
                "end_mins": e,
            })

    return converted


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
