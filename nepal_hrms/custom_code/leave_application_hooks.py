# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import getdate, add_days

def validate_sandwich_leave_application(doc, method):
    from nepal_hrms.custom_code.attendance_policy import get_hr_settings

    settings = get_hr_settings()
    if not settings.enable_leave_sandwich_rule:
        return

    from nepal_hrms.custom_code.policy_escape import has_policy_escape

    # Escape on leave from_date (or today if missing)
    if doc.employee and has_policy_escape(
        doc.employee, "escape_sandwich", doc.from_date or None
    ):
        return

    if doc.half_day:
        frappe.msgprint(
            _("Notice: Half-day leave before/after holidays prevents immediate sandwiching, but if you are absent for the full day on the adjacent working day, Sandwich Rule will consider intervening holidays as Leave/Absent."),
            alert=True,
            indicator="orange"
        )
        return

    if not settings.block_sandwich_leave_application:
        return

    # Check if from_date or to_date borders a holiday/weekend
    employee = doc.employee
    from_date = getdate(doc.from_date)
    to_date = getdate(doc.to_date)

    # Check preceding day
    prev_day = add_days(from_date, -1)
    is_prev_holiday = is_holiday_or_weekend(employee, prev_day)

    # Check next day
    next_day = add_days(to_date, 1)
    is_next_holiday = is_holiday_or_weekend(employee, next_day)

    if is_prev_holiday or is_next_holiday:
        # Check if adjacent working days have leaves or absent
        preceding_working_day = get_adjacent_working_day(employee, from_date, direction=-1)
        following_working_day = get_adjacent_working_day(employee, to_date, direction=1)

        has_prev_leave = has_leave_or_absent(employee, preceding_working_day, doc.name)
        has_next_leave = has_leave_or_absent(employee, following_working_day, doc.name)

        if has_prev_leave or has_next_leave:
            frappe.throw(
                _("Sandwich Rule Violation: Your leave request borders weekend/holiday dates ({0} to {1}). Please include the intervening weekend/holiday days in your Leave Application.").format(
                    from_date, to_date
                )
            )

def is_holiday_or_weekend(employee, date_obj):
    holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")
    if not holiday_list:
        holiday_list = frappe.db.get_single_value("HR Settings", "default_holiday_list")

    if holiday_list:
        return bool(frappe.db.exists("Holiday", {"parent": holiday_list, "holiday_date": date_obj}))
    return False

def get_adjacent_working_day(employee, date_obj, direction=-1):
    curr = add_days(date_obj, direction)
    while is_holiday_or_weekend(employee, curr):
        curr = add_days(curr, direction)
    return curr

def has_leave_or_absent(employee, date_obj, current_leave_name=None):
    filters = {
        "employee": employee,
        "docstatus": 1,
        "from_date": ["<=", date_obj],
        "to_date": [">=", date_obj]
    }
    if current_leave_name:
        filters["name"] = ["!=", current_leave_name]

    return bool(frappe.db.exists("Leave Application", filters))
