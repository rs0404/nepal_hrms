# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Attendance day classification -- the single definition of what a day counts as.

This used to live inside the Monthly Attendance Sheet BS report, which made the
report the only thing that could answer "how many days was this person present".
Every other surface -- the BSHRMS PWA above all -- re-implemented the question and
got a different answer: half days counted whole, future days counted, penalties
folded back into Absent.

The rules here are deliberately arithmetic only. Nothing in this module reads the
Attendance table or resolves a period; that belongs to attendance_summary.py. Keep
it that way -- it is what lets these rules be tested without a site, and it is why
this module must never import the report.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

import nepal_compliance.nepali_date_utils.nepali_date as nepali_date

from nepal_hrms.custom_code.leave_type_acronym import format_leave_type_acronym


LEAVE_GROUP_ANNUAL_HOME = "Annual/Home"
LEAVE_GROUP_SICK = "Sick"
LEAVE_GROUP_OTHER = "Other Paid"


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


def _new_day_classification():
    return {
        "present_full": 0.0,
        "present_half": 0.0,
        "absent_full": 0.0,
        "absent_half": 0.0,
        "penalty_full": 0.0,
        "penalty_half": 0.0,
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
    pool_penalty=None,
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

    if not is_holiday and not is_sandwich:
        # ½P / 1P are reported on their own, never inside Absent. They still cost
        # the same paid days, so paid_flag is unchanged.
        if pool_penalty == "full":
            day["penalty_full"] = 1.0
            return day
        if pool_penalty == "half":
            day["penalty_half"] = 0.5
            day["present_half"] = 0.5
            day["paid_flag"] = 0.5
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


DAY_COUNT_DATE_FIELDS = (
    "absent_dates",
    "penalty_dates",
    "lwp_dates",
    "paid_leave_dates",
)


def _date_labels(attendance_date):
    """BS and AD labels for one day, for the summary-column hover lists."""
    attendance_date = getdate(attendance_date)
    # The report's execute() loads the calendar for us; a direct caller may not have.
    nepali_date._ensure_loaded()
    bs = nepali_date.ad_to_bs(attendance_date)
    return {
        "bs": f"{bs['year']}-{bs['month']:02d}-{bs['day']:02d}",
        "ad": attendance_date.strftime("%d %b %Y"),
        "weekday": attendance_date.strftime("%a"),
    }


def _collect_day_dates(row, attendance_date, day):
    """Record which dates produced each summary count, so the cells can show them.

    Only days that actually contributed are listed -- an empty list is what makes
    a zero cell read as genuinely zero rather than as a gap in the audit.
    """
    labels = None

    def add(field, units, note):
        nonlocal labels
        if flt(units) <= 0:
            return
        if labels is None:
            labels = _date_labels(attendance_date)
        row[field].append({**labels, "units": flt(units), "note": note})

    add("absent_dates", day.get("absent_full"), _("Absent"))
    add("absent_dates", day.get("absent_half"), _("Half day absent"))
    add("penalty_dates", day.get("penalty_full"), _("1P full-day penalty"))
    add("penalty_dates", day.get("penalty_half"), _("½P half-day penalty"))
    for leave_type, units in (day.get("lwp_breakdown") or {}).items():
        add("lwp_dates", units, leave_type)
    for leave_type, units in (day.get("leave_breakdown") or {}).items():
        add("paid_leave_dates", units, leave_type)


def _merge_breakdown(target, source):
    for key, value in source.items():
        target[key] = target.get(key, 0) + flt(value)


def _accumulate_day(row, day):
    fields = (
        "present_full",
        "present_half",
        "absent_full",
        "absent_half",
        "penalty_full",
        "penalty_half",
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
    row["penalty_days"] = flt(row["penalty_full"]) + flt(row["penalty_half"])
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
        - flt(row["penalty_days"])
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
