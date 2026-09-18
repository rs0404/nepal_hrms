import frappe, traceback
from frappe import _
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip, get_salary_component_data
from hrms.payroll.doctype.salary_slip.salary_slip import make_loan_repayment_entry
from frappe.utils import cint, flt, getdate, add_days
from typing import Optional
from frappe.model.document import Document


DEFAULT_BASIC_BASE = "Basic Remuneration (SSF/PF Base)"
GROSS_BASE = "Total Fixed Remuneration (Gross)"
# The Salary Structure Assignment's own Base field. Deliberately distinct from
# GROSS_BASE: the slip's Gross Pay carries the Employer's SSF / PF / Gratuity
# earning on top of contractual salary, and nothing that is added to gross only
# to be deducted back should widen an attendance deduction.
ASSIGNMENT_BASE = "Assignment Base (Total Salary)"


def _get_attendance_deduction_base(
    selection,
    basic_salary,
    dearness_allowance,
    grade,
    basic_remuneration,
    total_fixed,
    assignment_base=0.0,
):
    """Resolve a human-readable settings choice to a monthly deduction base."""
    amounts = {
        "Basic Salary Only": basic_salary,
        "Basic Salary + Grade": basic_salary + grade,
        "Basic Salary + Dearness Allowance": basic_salary + dearness_allowance,
        "Basic Salary + Grade + Dearness Allowance": (
            basic_salary + grade + dearness_allowance
        ),
        DEFAULT_BASIC_BASE: basic_remuneration,
        GROSS_BASE: total_fixed,
        ASSIGNMENT_BASE: flt(assignment_base) or total_fixed,
    }
    return flt(amounts.get(selection, basic_remuneration))


def get_pool_penalty_days(employee, start_date, end_date):
    """Pool ½P / 1P days in this period, with the dates that produced them.

    ½P and 1P are written onto Attendance itself (Half Day / Absent), so HRMS
    counts them inside `absent_days`. Payroll needs them separated out to charge
    them on their own base, so read the marks back off Attendance -- it is the
    record of record, and policy escapes were already applied when the mark was
    assigned.

    A ½P is worth whatever Payroll Settings pays for a half day, because that is
    exactly what HRMS added to `absent_days` for the same Attendance row -- using a
    flat 0.5 here would leave a residue on a site configured otherwise.

    Returns (days, dates) where dates is [{date, kind, units}, ...].
    """
    if not frappe.get_meta("Attendance").has_field("custom_cnr_pool_penalty"):
        return 0.0, []

    half_day_units = (
        flt(frappe.db.get_single_value("Payroll Settings", "daily_wages_fraction_for_half_day"))
        or 0.5
    )

    rows = frappe.get_all(
        "Attendance",
        filters={
            "employee": employee,
            "attendance_date": ["between", [start_date, end_date]],
            "docstatus": 1,
            "custom_cnr_pool_penalty": ["in", ["half", "full"]],
        },
        fields=["attendance_date", "custom_cnr_pool_penalty"],
        order_by="attendance_date asc",
    )

    # A holiday never earns a penalty. Date-based, not a status filter on the
    # query: a worked holiday carries status "Present".
    from nepal_hrms.custom_code.attendance_holiday import holiday_dates_between

    holiday_dates = holiday_dates_between(employee, start_date, end_date)

    days = 0.0
    dates = []
    for row in rows:
        if getdate(row.attendance_date) in holiday_dates:
            continue
        kind = (row.custom_cnr_pool_penalty or "").strip()
        units = 1.0 if kind == "full" else half_day_units
        days += units
        dates.append(
            {"date": str(row.attendance_date), "kind": kind, "units": units}
        )
    return flt(days), dates


def _has_half_day_leave(employee, attendance_date):
    """True if an approved half-day leave covers this date (major delay excused by leave)."""
    return bool(
        frappe.db.exists(
            "Leave Application",
            {
                "employee": employee,
                "docstatus": 1,
                "status": "Approved",
                "from_date": ["<=", attendance_date],
                "to_date": [">=", attendance_date],
                "half_day": 1,
            },
        )
    )


def _get_paid_leave_days(employee, start_date, end_date):
    """Approved non-LWP leave days inside this payroll period."""
    from hrms.hr.doctype.leave_application.leave_application import get_number_of_leave_days

    leaves = frappe.get_all(
        "Leave Application",
        filters={
            "employee": employee,
            "docstatus": 1,
            "status": "Approved",
            "from_date": ["<=", end_date],
            "to_date": [">=", start_date],
        },
        fields=["leave_type", "from_date", "to_date", "half_day", "half_day_date"],
    )
    paid_days = 0.0
    for leave in leaves:
        if cint(frappe.db.get_value("Leave Type", leave.leave_type, "is_lwp")):
            continue
        clipped_from = max(getdate(leave.from_date), getdate(start_date))
        clipped_to = min(getdate(leave.to_date), getdate(end_date))
        half_day_date = (
            leave.half_day_date
            if leave.half_day_date
            and clipped_from <= getdate(leave.half_day_date) <= clipped_to
            else None
        )
        paid_days += get_number_of_leave_days(
            employee,
            leave.leave_type,
            clipped_from,
            clipped_to,
            half_day=1 if half_day_date else 0,
            half_day_date=half_day_date,
        )
    return flt(paid_days)


def _classify_late_or_early(mins, app, employee, att_date, grace, max_delay):
    """
    C&R rules:
    - Within grace: ignore
    - Any approved Late/Early application: fully excused (no pool, no half-day)
    - Major (> max delay): half-day unless half-day leave or Office Work
    - Minor with no approved slip: counts toward occurrence pool
    Returns: None | 'minor' | 'major'
    """
    from nepal_hrms.custom_code.attendance_policy import classify_delay

    kind = classify_delay(mins, grace, max_delay)
    if not kind:
        return None

    # Approved application fully excuses grace→max and also Office Work majors
    if app:
        if kind == "minor":
            return None
        if app.type_of_work == "Office Work":
            return None

    if kind == "major":
        if _has_half_day_leave(employee, att_date):
            return None
        return "major"

    # minor, no approved slip → occurrence pool
    return "minor"


def count_sandwich_holiday_absents(
    employee, attendance_rows, holidays, already_counting_holiday_attendance=False
):
    """Holiday Absents created by the sandwich rule.

    Stock HRMS skips Absent on holidays unless Payroll Settings
    "Consider Marked Attendance on Holidays" is on. Sandwich weekends are
    holidays, so those days never reached leave_without_pay / absent_days.
    """
    if already_counting_holiday_attendance or not employee:
        return 0.0

    from nepal_hrms.custom_code.attendance_holiday import (
        is_sandwiched,
        sandwich_rule_enabled,
    )

    if not sandwich_rule_enabled():
        return 0.0

    holiday_set = {getdate(h) for h in (holidays or [])}
    extra = 0.0
    for row in attendance_rows or []:
        day = getdate(row.get("attendance_date") if isinstance(row, dict) else row.attendance_date)
        status = row.get("status") if isinstance(row, dict) else row.status
        if day not in holiday_set or (status or "").strip() != "Absent":
            continue
        if is_sandwiched(employee, day):
            extra += 1
    return extra


def period_leave_days_for_gross_rule(lwp_days, absent_days):
    """LWP + absent days in the payroll period that can trip LWP onto Gross."""
    return flt(lwp_days) + flt(absent_days)


def lwp_should_use_gross(
    *,
    enable_continuous,
    max_continuous_lwp,
    continuous_threshold,
    enable_period_leave,
    period_leave_days,
    period_threshold,
    escape_lwp_gross,
):
    """Return (use_gross, is_continuous, is_period_leave).

    Continuous LWP: one application length is at least the threshold.
    Period leave: LWP + absent days in this payroll period is more than the threshold.
    """
    if cint(escape_lwp_gross):
        return False, 0, 0
    is_continuous = int(
        cint(enable_continuous)
        and flt(max_continuous_lwp) >= cint(continuous_threshold or 0)
    )
    is_period = int(
        cint(enable_period_leave) and flt(period_leave_days) > cint(period_threshold or 0)
    )
    return bool(is_continuous or is_period), is_continuous, is_period


ATTENDANCE_DEDUCTION_COMPONENTS = (
    "Leave and Late Deduction",
    "Leaves and Late Comings",
)
BASIC_EARNING_COMPONENTS = ("Basic Salary",)
DA_EARNING_COMPONENTS = ("Dearness Allowance",)
GRADE_EARNING_COMPONENTS = ("Grade", "Grade Amount", "Employee Grade Amount")
OTHER_ALLOWANCE_COMPONENTS = (
    "Other Allowance",
    "Miscellaneous Allowance",
    "Blog Allowance",
)
EMPLOYER_CONTRIBUTION_EARNINGS = (
    "Employer's Contribution SSF",
    "Provident Fund Employer",
    "Gratuity",
)
CONTRIBUTION_DEDUCTIONS = (
    "Employee's Contribution SSF",
    "Employer's Contribution SSF Deduction",
    "Provident Fund Employee",
    "Provident Fund Employer Deduction",
    "Gratuity Deduction",
)


def _matches_component(name, roots):
    name = (name or "").strip()
    return any(name == root or name.startswith(f"{root} - ") for root in roots)


def _check_setting(settings, fieldname, default=0):
    value = settings.get(fieldname)
    return cint(default if value is None else value)


def allocate_attendance_deduction(components, deduction_amount, proportional=False):
    """Allocate a deduction without making any earned component negative.

    ``components`` is a list of dictionaries containing a unique ``key``, a
    fixed ``amount`` and whether the component ``contributes`` to the
    SSF/PF/Gratuity base.

    Allowances-first mode consumes non-contribution earnings first, then spills
    into the contribution base. Proportional mode treats every fixed component
    as one pool.
    """
    normalized = [
        {
            "key": component["key"],
            "amount": max(flt(component.get("amount")), 0.0),
            "contributes": bool(component.get("contributes")),
        }
        for component in components
    ]
    earned = {component["key"]: component["amount"] for component in normalized}
    requested = max(flt(deduction_amount, 2), 0.0)
    remaining = requested

    def consume(group):
        nonlocal remaining
        group = [component for component in group if earned[component["key"]] > 0]
        amounts_in_cents = {
            component["key"]: int(round(earned[component["key"]] * 100))
            for component in group
        }
        available_in_cents = sum(amounts_in_cents.values())
        target_in_cents = min(int(round(remaining * 100)), available_in_cents)
        if not group or target_in_cents <= 0:
            return

        shares = {}
        remainders = []
        allocated_in_cents = 0
        for component in group:
            key = component["key"]
            numerator = target_in_cents * amounts_in_cents[key]
            share, remainder = divmod(numerator, available_in_cents)
            shares[key] = share
            allocated_in_cents += share
            remainders.append((remainder, key))

        for _remainder, key in sorted(
            remainders, key=lambda item: item[0], reverse=True
        )[
            : target_in_cents - allocated_in_cents
        ]:
            shares[key] += 1

        for component in group:
            key = component["key"]
            earned[key] = flt((amounts_in_cents[key] - shares[key]) / 100, 2)
        remaining = flt(remaining - target_in_cents / 100, 2)

    if proportional:
        consume(normalized)
    else:
        consume([component for component in normalized if not component["contributes"]])
        consume([component for component in normalized if component["contributes"]])

    fixed_contribution_base = flt(
        sum(component["amount"] for component in normalized if component["contributes"]),
        2,
    )
    earned_contribution_base = flt(
        sum(earned[component["key"]] for component in normalized if component["contributes"]),
        2,
    )
    return {
        "earned_amounts": earned,
        "requested_deduction": requested,
        "applied_deduction": flt(requested - remaining, 2),
        "unapplied_deduction": remaining,
        "fixed_contribution_base": fixed_contribution_base,
        "earned_contribution_base": earned_contribution_base,
    }


def compute_nepal_hr_variables(doc, data):
    if isinstance(doc, dict):
        doc = frappe._dict(doc)

    # C&R settings live on Nepal HRMS Settings. reassign_hr_module._copy_hr_settings()
    # migrated them off Nepal Compliance Settings, which no longer declares the fields
    # at all -- reading it there silently returned the hardcoded defaults for every one.
    try:
        from nepal_hrms.custom_code.attendance_policy import get_hr_settings

        settings = get_hr_settings()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Nepal HRMS settings unavailable for payroll")
        settings = frappe._dict()

    from nepal_hrms.custom_code.attendance_policy import get_approved_application

    late_entry_half_days = 0.0
    early_exit_half_days = 0.0
    out_of_office_half_days = 0.0
    late_entry_full_days = 0.0
    early_exit_full_days = 0.0

    start_date = getdate(doc.start_date)
    end_date = getdate(doc.end_date)
    employee = doc.employee

    from nepal_hrms.custom_code.policy_escape import (
        get_policy_escapes_for_period,
        has_policy_escape,
    )

    period_escapes = get_policy_escapes_for_period(employee, start_date, end_date)

    # 1. Late Entry & Early Exit Penalty Calculation
    # get_singles_dict returns Check/Int fields as strings ("0"/"1"), so truthiness
    # and numeric compares must go through cint().
    if cint(getattr(settings, "enable_late_early_penalty", 0)):
        grace_mins = cint(getattr(settings, "late_early_grace_mins", None) or 15)
        max_delay = cint(getattr(settings, "late_early_max_delay_mins", None) or 60)

        att_meta = frappe.get_meta("Attendance")
        has_late_pool = att_meta.has_field("custom_cnr_late_in_pool")
        has_early_pool = att_meta.has_field("custom_cnr_early_in_pool")

        fields = [
            "name",
            "attendance_date",
            "late_entry",
            "early_exit",
            "custom_late_mins",
            "custom_early_mins",
            "in_time",
            "out_time",
            "shift",
        ]
        if has_late_pool:
            fields.append("custom_cnr_late_in_pool")
        if has_early_pool:
            fields.append("custom_cnr_early_in_pool")

        attendances = frappe.get_all(
            "Attendance",
            filters={
                "employee": employee,
                "attendance_date": ["between", [start_date, end_date]],
                "docstatus": 1,
            },
            fields=fields,
        )

        minor_late_count = 0
        major_late_count = 0
        minor_early_count = 0
        major_early_count = 0

        from nepal_hrms.custom_code.attendance_policy import compute_late_early_minutes
        from nepal_hrms.custom_code.attendance_holiday import holiday_dates_between

        holiday_dates = holiday_dates_between(employee, start_date, end_date)
        excused_request_dates = set()
        if cint(getattr(settings, "excuse_late_early_on_attendance_request", 0) or 0):
            from nepal_hrms.custom_code.attendance_policy import (
                approved_attendance_request_dates,
            )

            excused_request_dates = approved_attendance_request_dates(
                employee, start_date, end_date
            )

        for att in attendances:
            att_date = att.attendance_date
            if has_policy_escape(employee, "escape_late_early", att_date):
                continue
            if getdate(att_date) in holiday_dates:
                continue
            if getdate(att_date) in excused_request_dates:
                continue
            late_mins = cint(att.custom_late_mins or 0)
            early_mins = cint(att.custom_early_mins or 0)
            if (not late_mins and att.in_time) or (not early_mins and att.out_time):
                calc_late, calc_early = compute_late_early_minutes(
                    employee, att_date, in_time=att.in_time, out_time=att.out_time, shift=att.shift
                )
                if not late_mins:
                    late_mins = calc_late
                if not early_mins:
                    early_mins = calc_early

            # Late: prefer pool flag for minors; always classify for majors / legacy rows
            if has_late_pool and cint(att.get("custom_cnr_late_in_pool")):
                minor_late_count += 1
            elif late_mins > grace_mins or att.late_entry:
                if late_mins <= grace_mins and att.late_entry:
                    late_mins = grace_mins + 1
                lea = get_approved_application("Late Entry Application", employee, att_date)
                result = _classify_late_or_early(
                    late_mins, lea, employee, att_date, grace_mins, max_delay
                )
                if result == "minor":
                    minor_late_count += 1
                elif result == "major":
                    major_late_count += 1

            if has_early_pool and cint(att.get("custom_cnr_early_in_pool")):
                minor_early_count += 1
            elif early_mins > grace_mins or att.early_exit:
                if early_mins <= grace_mins and att.early_exit:
                    early_mins = grace_mins + 1
                eea = get_approved_application("Early Exit Application", employee, att_date)
                result = _classify_late_or_early(
                    early_mins, eea, employee, att_date, grace_mins, max_delay
                )
                if result == "minor":
                    minor_early_count += 1
                elif result == "major":
                    major_early_count += 1

        # Pool ½P / 1P now change Attendance (Half Day absent / Absent) and
        # are counted in absent_days at the unapproved-absence (gross) rate.
        # Do not also charge them on Leave and Late Deduction.
        late_entry_half_days = float(major_late_count)
        late_entry_full_days = 0.0
        early_exit_half_days = float(major_early_count)
        early_exit_full_days = 0.0

    # 2. Out of Office Overages
    # Personal Work OOO Application over max paid hours => half-day.
    # PWA OOO Work is Office Work: approved check-in hours do not create personal overage,
    # but Personal Work Application over limit still does. If Personal hours on Attendance
    # custom_ooo_hours exceed limit with a Personal Application, count once.
    max_paid_ooo = flt(getattr(settings, "max_paid_out_of_office_hours", 2.0) or 2.0)
    ooo_apps = frappe.get_all(
        "Out of Office Application",
        filters={
            "employee": employee,
            "attendance_date": ["between", [start_date, end_date]],
            "status": "Approved",
            "docstatus": 1,
        },
        fields=["attendance_date", "total_hours", "type_of_work"],
    )
    for ooo in ooo_apps:
        if has_policy_escape(employee, "escape_applications", ooo.attendance_date):
            continue
        if ooo.type_of_work == "Personal Work" and flt(ooo.total_hours) > max_paid_ooo:
            if not _has_half_day_leave(employee, ooo.attendance_date):
                out_of_office_half_days += 1.0

    # PWA OOO Work is Office Work: manager-approved check-ins do not add personal overage.
    # Personal Work must use Out of Office Application (handled above).

    # 3. Distinct LWP vs Unapproved Absent
    lwp_days = flt(doc.leave_without_pay or 0)
    # absent_days and leave_without_pay are disjoint in HRMS: `absent` is counted
    # from Attendance status=Absent, `lwp` from LWP leave types, and payment_days
    # subtracts both (see hrms salary_slip.py get_working_days_details). Deducting
    # lwp_days here under-counted unapproved absence by exactly the LWP days, so
    # 3 absent + 2 LWP was charged as 1 + 2 = 3 days instead of 5.
    total_absent_days = flt(doc.absent_days or 0)
    if total_absent_days < 0:
        total_absent_days = 0.0

    # ½P / 1P are Attendance rows too, so they are already inside absent_days.
    # Split them out so each is charged on its own configured base; never let the
    # split drive the genuine-absence count negative if the two disagree.
    penalty_days, penalty_dates = get_pool_penalty_days(employee, start_date, end_date)
    penalty_days = min(flt(penalty_days), total_absent_days)
    unapproved_absent_days = flt(total_absent_days - penalty_days)
    if unapproved_absent_days < 0:
        unapproved_absent_days = 0.0

    # 4. LWP streak / period-leave count & Gross Salary Deduction Rate
    # Policy: normal LWP on the configured base; unapproved absence or either
    # Gross-LWP rule (continuous application, or too many LWP + absent days in the
    # payroll period) uses gross.
    is_continuous_lwp_gross = 0
    max_continuous_lwp = 0

    lwp_leaves = frappe.get_all(
        "Leave Application",
        filters={
            "employee": employee,
            "docstatus": 1,
            "status": "Approved",
            "from_date": ["<=", end_date],
            "to_date": [">=", start_date],
        },
        fields=["from_date", "to_date", "leave_type"],
    )
    for l in lwp_leaves:
        is_lwp = frappe.db.get_value("Leave Type", l.leave_type, "is_lwp")
        if is_lwp:
            streak = (getdate(l.to_date) - getdate(l.from_date)).days + 1
            if streak > max_continuous_lwp:
                max_continuous_lwp = streak

    # Per-day rates come from the Salary Structure Assignment via `data`, which
    # carries every SSA field (SalarySlip selects "*"). They must NOT be read off
    # `doc`: Salary Slip has no `base` field and BaseDocument has no __getattr__,
    # so `doc.base` raises AttributeError. `doc.gross_pay` is also still 0 here --
    # this runs while the earnings table is being built.
    from nepal_hrms.custom_code.payroll.period import resolve_daily_divisor

    ssa_base = flt(data.get("base"))
    basic_remuneration = flt(data.get("custom_basic_remuneration"))
    total_fixed = flt(data.get("custom_total_fixed_remuneration")) or ssa_base

    if not basic_remuneration:
        # Assignment predating the Nepal breakdown: derive rather than divide by 0.
        percent = flt(settings.get("default_basic_percent") or 60)
        basic_remuneration = flt(ssa_base * percent / 100.0, 2)

    basic_salary = flt(data.get("custom_basic_salary")) or basic_remuneration
    dearness_allowance = flt(data.get("custom_dearness_allowance"))
    grade = flt(data.get("custom_grade_amount"))
    half_day_base_name = settings.get("half_day_deduction_base") or DEFAULT_BASIC_BASE
    lwp_base_name = settings.get("lwp_deduction_base") or DEFAULT_BASIC_BASE
    absent_base_name = settings.get("unapproved_absence_deduction_base") or GROSS_BASE
    # Unset falls back to the half-day base, which is what ½P / 1P were charged
    # on before they had a base of their own.
    penalty_base_name = settings.get("penalty_deduction_base") or half_day_base_name

    def resolve_base(selection):
        return _get_attendance_deduction_base(
            selection,
            basic_salary,
            dearness_allowance,
            grade,
            basic_remuneration,
            total_fixed,
            assignment_base=ssa_base,
        )

    half_day_monthly_base = resolve_base(half_day_base_name)
    lwp_monthly_base = resolve_base(lwp_base_name)
    absent_monthly_base = resolve_base(absent_base_name)
    penalty_monthly_base = resolve_base(penalty_base_name)

    # Snapshot the divisor onto the slip the first time it is calculated. A later
    # Nepal Payroll Period Override must not restate pay that already exists, so
    # a slip that carries a snapshot keeps using it.
    snapshot = flt(getattr(doc, "custom_daily_divisor_used", 0))
    if snapshot > 0:
        working_days, divisor_basis = snapshot, "snapshot on slip"
    else:
        working_days, divisor_basis = resolve_daily_divisor(
            doc.start_date,
            doc.end_date,
            working_days=doc.total_working_days,
            company=doc.company,
            created_on=getattr(doc, "creation", None) or frappe.utils.today(),
        )
        if hasattr(doc, "custom_daily_divisor_used"):
            doc.custom_daily_divisor_used = flt(working_days)
    if hasattr(doc, "custom_daily_divisor_basis"):
        doc.custom_daily_divisor_basis = divisor_basis

    basic_daily = flt(basic_remuneration) / working_days if working_days else 0.0
    gross_daily = flt(total_fixed) / working_days if working_days else 0.0
    half_day_base_daily = flt(half_day_monthly_base) / working_days if working_days else 0.0
    configured_lwp_daily = flt(lwp_monthly_base) / working_days if working_days else 0.0
    configured_absent_daily = flt(absent_monthly_base) / working_days if working_days else 0.0
    configured_penalty_daily = flt(penalty_monthly_base) / working_days if working_days else 0.0

    paid_leave_days = _get_paid_leave_days(employee, start_date, end_date)
    # The threshold rule asks how much of the period was unpaid, so it keeps
    # counting ½P / 1P days even though they are deducted on their own base.
    period_leave_days = period_leave_days_for_gross_rule(lwp_days, total_absent_days)
    threshold_lwp = cint(getattr(settings, "continuous_lwp_threshold_days", 5) or 5)
    period_threshold = cint(getattr(settings, "period_leave_gross_lwp_threshold", 5) or 5)
    use_gross, is_continuous_lwp_gross, is_period_leave_gross = lwp_should_use_gross(
        enable_continuous=getattr(settings, "enable_continuous_lwp_gross_deduction", 0),
        max_continuous_lwp=max_continuous_lwp,
        continuous_threshold=threshold_lwp,
        enable_period_leave=getattr(settings, "enable_period_leave_gross_lwp", 0),
        period_leave_days=period_leave_days,
        period_threshold=period_threshold,
        escape_lwp_gross=period_escapes.escape_continuous_lwp_gross,
    )
    lwp_deduction_rate = gross_daily if use_gross else configured_lwp_daily

    # The escape only relaxes a configured gross absence rate.
    if cint(period_escapes.escape_absent_gross) and absent_base_name == GROSS_BASE:
        unapproved_absent_rate = basic_daily
    else:
        unapproved_absent_rate = configured_absent_daily
    # The absence escape relaxes a gross ½P / 1P rate the same way.
    if cint(period_escapes.escape_absent_gross) and penalty_base_name == GROSS_BASE:
        penalty_deduction_rate = basic_daily
    else:
        penalty_deduction_rate = configured_penalty_daily
    # Each late/early/OOO penalty count represents half a day.
    late_deduction_rate = half_day_base_daily * 0.5

    half_day_penalties = flt(
        late_entry_half_days + early_exit_half_days + out_of_office_half_days
    )
    half_day_deduction = flt(half_day_penalties * late_deduction_rate, 2)
    lwp_deduction_amount = flt(lwp_days * lwp_deduction_rate, 2)
    absent_deduction_amount = flt(unapproved_absent_days * unapproved_absent_rate, 2)
    penalty_deduction_amount = flt(penalty_days * penalty_deduction_rate, 2)
    leave_late_deduction_total = flt(
        half_day_deduction
        + lwp_deduction_amount
        + absent_deduction_amount
        + penalty_deduction_amount,
        2,
    )

    data["late_entry_half_days"] = late_entry_half_days
    data["early_exit_half_days"] = early_exit_half_days
    data["out_of_office_half_days"] = out_of_office_half_days
    data["late_entry_full_days"] = late_entry_full_days
    data["early_exit_full_days"] = early_exit_full_days
    data["lwp_days"] = lwp_days
    data["unapproved_absent_days"] = unapproved_absent_days
    data["penalty_days"] = penalty_days
    data["total_absent_days"] = total_absent_days
    data["lwp_deduction_rate"] = lwp_deduction_rate
    data["unapproved_absent_rate"] = unapproved_absent_rate
    data["penalty_deduction_rate"] = penalty_deduction_rate
    data["late_deduction_rate"] = late_deduction_rate
    data["is_continuous_lwp_gross"] = is_continuous_lwp_gross
    data["is_period_leave_gross"] = is_period_leave_gross
    data["period_leave_days"] = period_leave_days
    data["half_day_deduction_base"] = half_day_base_name
    data["lwp_deduction_base"] = lwp_base_name
    data["unapproved_absence_deduction_base"] = absent_base_name
    data["penalty_deduction_base"] = penalty_base_name
    earned_salary_mode = _check_setting(
        settings,
        "calculate_attendance_deductions_through_earned_salary",
        default=1,
    )
    proportional_earning_reduction = _check_setting(
        settings,
        "proportionally_reduce_earnings_for_attendance_deductions",
        default=0,
    )
    data["calculate_attendance_deductions_through_earned_salary"] = earned_salary_mode
    data["proportionally_reduce_earnings_for_attendance_deductions"] = (
        proportional_earning_reduction
    )
    data["leave_late_deduction_total"] = leave_late_deduction_total
    visible_values = {
        "custom_paid_leave_days": paid_leave_days,
        "custom_late_entry_half_days": late_entry_half_days,
        "custom_early_exit_half_days": early_exit_half_days,
        "custom_out_of_office_half_days": out_of_office_half_days,
        "custom_unapproved_absent_days": unapproved_absent_days,
        "custom_penalty_days": penalty_days,
        "custom_late_entry_full_days": late_entry_full_days,
        "custom_early_exit_full_days": early_exit_full_days,
        "custom_late_deduction_rate": flt(late_deduction_rate, 2),
        "custom_lwp_deduction_rate": flt(lwp_deduction_rate, 2),
        "custom_unapproved_absent_rate": flt(unapproved_absent_rate, 2),
        "custom_penalty_deduction_rate": flt(penalty_deduction_rate, 2),
        "custom_late_deduction_amount": half_day_deduction,
        "custom_lwp_deduction_amount": lwp_deduction_amount,
        "custom_unapproved_absent_deduction_amount": absent_deduction_amount,
        "custom_penalty_deduction_amount": penalty_deduction_amount,
        "custom_leave_late_deduction_total": leave_late_deduction_total,
        "custom_is_continuous_lwp_gross": is_continuous_lwp_gross,
        "custom_is_period_leave_gross": is_period_leave_gross,
    }
    for fieldname, value in visible_values.items():
        if doc.meta.has_field(fieldname):
            doc.set(fieldname, value)
    if doc.meta.has_field("custom_attendance_breakdown_data"):
        doc.custom_attendance_breakdown_data = frappe.as_json(
            {
                **visible_values,
                "half_day_deduction_amount": half_day_deduction,
                "unapproved_absent_deduction_amount": absent_deduction_amount,
                "daily_divisor": flt(working_days),
                "daily_divisor_basis": divisor_basis,
                "half_day_deduction_base": half_day_base_name,
                "lwp_deduction_base": lwp_base_name,
                "unapproved_absence_deduction_base": absent_base_name,
                "penalty_deduction_base": penalty_base_name,
                "penalty_dates": penalty_dates,
                "total_absent_days": total_absent_days,
                "period_leave_days": period_leave_days,
                "is_period_leave_gross": is_period_leave_gross,
            }
        )
    doc._nepal_hr_vars = {
        "late_entry_half_days": late_entry_half_days,
        "early_exit_half_days": early_exit_half_days,
        "out_of_office_half_days": out_of_office_half_days,
        "late_entry_full_days": late_entry_full_days,
        "early_exit_full_days": early_exit_full_days,
        "lwp_days": lwp_days,
        "unapproved_absent_days": unapproved_absent_days,
        "penalty_days": penalty_days,
        "total_absent_days": total_absent_days,
        "lwp_deduction_rate": lwp_deduction_rate,
        "unapproved_absent_rate": unapproved_absent_rate,
        "penalty_deduction_rate": penalty_deduction_rate,
        "late_deduction_rate": late_deduction_rate,
        "is_continuous_lwp_gross": is_continuous_lwp_gross,
        "is_period_leave_gross": is_period_leave_gross,
        "leave_late_deduction_total": leave_late_deduction_total,
        "calculate_attendance_deductions_through_earned_salary": earned_salary_mode,
        "proportionally_reduce_earnings_for_attendance_deductions": (
            proportional_earning_reduction
        ),
    }


def apply_manual_absent_days(doc, manual_absent, calculated_absent):
    """Keep user-edited absent days and adjust payment days by the delta."""
    manual_absent = max(flt(manual_absent), 0.0)
    calculated_absent = flt(calculated_absent)
    delta = manual_absent - calculated_absent
    if abs(delta) > 1e-9:
        doc.payment_days = max(flt(doc.payment_days) - delta, 0.0)
        frappe.msgprint(
            _("Absent Days set manually. Attendance had {0} absent day(s).").format(
                calculated_absent
            ),
            indicator="orange",
            alert=True,
        )
    doc.absent_days = manual_absent
    return manual_absent


def _manual_absent_override_enabled(doc):
    if cint(getattr(doc.flags, "use_manual_absent_days", 0)):
        return True
    if doc.meta.has_field("custom_absent_days_manual"):
        return cint(doc.get("custom_absent_days_manual"))
    return False


class CustomSalarySlip(SalarySlip):
    def validate(self):
        if _manual_absent_override_enabled(self):
            self.flags.use_manual_absent_days = 1
        super().validate()

    def get_working_days_details(self, lwp=None, for_preview=0):
        use_manual_absent = _manual_absent_override_enabled(self)
        manual_absent = flt(self.absent_days) if use_manual_absent else None

        super().get_working_days_details(lwp=lwp, for_preview=for_preview)

        if manual_absent is not None and not for_preview:
            calculated_absent = flt(self.absent_days)
            apply_manual_absent_days(self, manual_absent, calculated_absent)

        # Formulas may have already run against stale absent_days; force a rebuild.
        for attr in ("_nepal_hr_variables_loaded", "_nepal_hr_vars"):
            if hasattr(self, attr):
                delattr(self, attr)

    @frappe.whitelist()
    def process_salary_based_on_working_days(self, use_manual_absent=0):
        if cint(use_manual_absent):
            self.flags.use_manual_absent_days = 1
            if self.meta.has_field("custom_absent_days_manual"):
                self.custom_absent_days_manual = 1
        self.get_working_days_details(lwp=self.leave_without_pay)
        self.calculate_net_pay()

    def calculate_lwp_ppl_and_absent_days_based_on_attendance(
        self, holidays, daily_wages_fraction_for_half_day, consider_marked_attendance_on_holidays
    ):
        lwp, absent = super().calculate_lwp_ppl_and_absent_days_based_on_attendance(
            holidays, daily_wages_fraction_for_half_day, consider_marked_attendance_on_holidays
        )
        extra = count_sandwich_holiday_absents(
            self.employee,
            self.get_employee_attendance(self.start_date, self.actual_end_date),
            holidays,
            already_counting_holiday_attendance=bool(
                cint(consider_marked_attendance_on_holidays)
            ),
        )
        return lwp, flt(absent) + extra

    def add_structure_components(self, component_type):
        super().add_structure_components(component_type)
        if component_type == "earnings" and (self.salary_structure or "").startswith("Nepal Payroll - "):
            self._add_assignment_allowance_earnings()

    def _add_assignment_allowance_earnings(self):
        """Replace aggregate structure rows with one earning per SSA allowance row."""
        from nepal_hrms.custom_code.payroll.salary_breakdown import get_allowance_rows

        # Submitted structures created before this change can remain cached during
        # a worker's lifetime. Never pay their aggregate rows as well as the new
        # component-wise rows.
        self.set(
            "earnings",
            [
                row
                for row in self.earnings
                if not (
                    (row.salary_component or "").startswith("Other Allowance - ")
                    or (row.salary_component or "").startswith("Miscellaneous Allowance - ")
                )
            ],
        )

        assignment = getattr(self, "_salary_structure_assignment", None) or {}
        amounts_by_component = {}
        for row in get_allowance_rows(assignment.get("name")):
            if row.salary_component:
                amounts_by_component[row.salary_component] = flt(
                    amounts_by_component.get(row.salary_component)
                ) + flt(row.amount)

        for component, amount in amounts_by_component.items():
            component_data = get_salary_component_data(component)
            if not component_data:
                frappe.throw(
                    _("Salary Component {0} used in Other Allowances does not exist.").format(
                        frappe.bold(component)
                    )
                )
            self.update_component_row(
                component_data,
                amount,
                "earnings",
                data=self.data,
                default_amount=amount,
                remove_if_zero_valued=True,
            )

    def calculate_component_amounts(self, component_type):
        for row in self.get(component_type) or []:
            row.flags.nepal_earned_salary_adjusted = False

        super().calculate_component_amounts(component_type)
        if component_type != "earnings":
            return

        self._populate_fixed_earning_amounts()
        if self._earned_salary_mode_enabled():
            self._apply_attendance_deduction_to_earnings()
        self._set_fixed_gross_pay()

    def get_amount_based_on_payment_days(self, row):
        if getattr(
            getattr(row, "flags", None),
            "nepal_earned_salary_adjusted",
            False,
        ):
            return flt(row.amount), flt(row.additional_amount)
        return super().get_amount_based_on_payment_days(row)

    def set_totals(self):
        super().set_totals()
        if self.salary_slip_based_on_timesheet:
            return

        # Stock set_totals() blindly sums every row and is also called by the
        # editable grids. Keep informational attendance rows out on manual
        # amount/exchange-rate edits just as calculate_net_pay() does.
        self.gross_pay = self.get_component_totals("earnings")
        self.total_deduction = self.get_component_totals("deductions")
        self.net_pay = (
            flt(self.gross_pay)
            - flt(self.total_deduction)
            - flt(self.get("total_loan_repayment"))
        )
        self.set_base_totals()

    def add_tax_components(self):
        # Stock calls this only after every regular deduction has been added.
        # Scale contributions and neutralise the informational attendance row
        # before TDS reads the current earnings and deductions.
        self._restore_attendance_deduction_flags()
        self._populate_fixed_deduction_amounts()
        if self._earned_salary_mode_enabled():
            self._scale_contribution_deductions()
            self._make_attendance_deduction_informational()
        return super().add_tax_components()

    def _earned_salary_mode_enabled(self):
        from nepal_hrms.custom_code.attendance_policy import get_hr_settings

        return bool(
            _check_setting(
                get_hr_settings(),
                "calculate_attendance_deductions_through_earned_salary",
                default=1,
            )
        )

    @staticmethod
    def _regular_component_amount(row):
        if row.additional_salary:
            # An overwrite row carries default_amount plus a positive or
            # negative delta. Its effective amount is the allocatable salary;
            # an additional-only row (default_amount == 0) is not contractual
            # fixed salary and must remain untouched.
            if flt(row.default_amount):
                return flt(max(flt(row.amount), 0), 2)
            return 0.0
        if flt(row.default_amount):
            return flt(max(flt(row.default_amount), 0), 2)
        return flt(max(flt(row.amount) - flt(row.additional_amount), 0), 2)

    @staticmethod
    def _preserved_additional_amount(row):
        if row.additional_salary:
            return flt(row.amount) if not flt(row.default_amount) else 0.0
        return flt(row.additional_amount)

    @staticmethod
    def _set_fixed_amount(row, amount):
        if row.meta.has_field("custom_fixed_amount"):
            row.custom_fixed_amount = flt(amount, row.precision("amount"))

    def _populate_fixed_earning_amounts(self):
        for row in self.get("earnings") or []:
            self._set_fixed_amount(row, self._regular_component_amount(row))

    def _populate_fixed_deduction_amounts(self):
        for row in self.get("deductions") or []:
            self._set_fixed_amount(row, self._regular_component_amount(row))

    def _set_fixed_gross_pay(self):
        if not self.meta.has_field("custom_fixed_gross_pay"):
            return
        self.custom_fixed_gross_pay = flt(
            sum(
                flt(row.custom_fixed_amount)
                for row in (self.get("earnings") or [])
                if not cint(row.do_not_include_in_total)
            ),
            self.precision("custom_fixed_gross_pay"),
        )

    def _allowance_component_names(self):
        if hasattr(self, "_nepal_allowance_component_names"):
            return self._nepal_allowance_component_names

        from nepal_hrms.custom_code.payroll.salary_breakdown import get_allowance_rows

        assignment = getattr(self, "_salary_structure_assignment", None) or {}
        self._nepal_allowance_component_names = {
            row.salary_component
            for row in get_allowance_rows(assignment.get("name"))
            if row.salary_component
        }
        return self._nepal_allowance_component_names

    def _has_attendance_deduction_component(self):
        structure = getattr(self, "_salary_structure_doc", None)
        if not structure:
            return False
        return any(
            _matches_component(
                row.salary_component, ATTENDANCE_DEDUCTION_COMPONENTS
            )
            for row in (structure.get("deductions") or [])
        )

    def _fixed_salary_components(self, settings):
        allowance_components = self._allowance_component_names()
        include_grade = bool(
            _check_setting(settings, "include_grade_in_ssf_base", default=1)
        )
        include_da = bool(_check_setting(settings, "include_da_in_ssf_base", default=0))
        components = []
        rows = {}

        for index, row in enumerate(self.get("earnings") or []):
            name = row.salary_component
            contributes = False
            is_fixed_salary = False

            if _matches_component(name, BASIC_EARNING_COMPONENTS):
                is_fixed_salary = contributes = True
            elif _matches_component(name, DA_EARNING_COMPONENTS):
                is_fixed_salary = True
                contributes = include_da
            elif _matches_component(name, GRADE_EARNING_COMPONENTS):
                is_fixed_salary = True
                contributes = include_grade
            elif (
                name in allowance_components
                or _matches_component(name, OTHER_ALLOWANCE_COMPONENTS)
            ):
                is_fixed_salary = True

            amount = self._regular_component_amount(row)
            if not is_fixed_salary or amount <= 0:
                continue

            key = index
            rows[key] = row
            components.append(
                {"key": key, "amount": amount, "contributes": contributes}
            )

        return components, rows

    def _apply_attendance_deduction_to_earnings(self):
        from nepal_hrms.custom_code.attendance_policy import get_hr_settings

        self._earned_salary_result = None
        if not self._has_attendance_deduction_component():
            return

        settings = get_hr_settings()
        variables = getattr(self, "_nepal_hr_vars", {})
        attendance_deduction = flt(variables.get("leave_late_deduction_total"), 2)
        components, rows = self._fixed_salary_components(settings)
        if not components:
            return

        result = allocate_attendance_deduction(
            components,
            attendance_deduction,
            proportional=bool(
                _check_setting(
                    settings,
                    "proportionally_reduce_earnings_for_attendance_deductions",
                    default=0,
                )
            ),
        )
        self._earned_salary_result = frappe._dict(result)

        for key, earned_amount in result["earned_amounts"].items():
            row = rows[key]
            row.amount = flt(
                earned_amount
                + CustomSalarySlip._preserved_additional_amount(row),
                row.precision("amount"),
            )
            row.flags.nepal_earned_salary_adjusted = True

        fixed_base = flt(result["fixed_contribution_base"])
        earned_base = flt(result["earned_contribution_base"])
        ratio = earned_base / fixed_base if fixed_base else 1.0
        for row in self.get("earnings") or []:
            if not _matches_component(
                row.salary_component, EMPLOYER_CONTRIBUTION_EARNINGS
            ):
                continue
            fixed_amount = self._regular_component_amount(row)
            if fixed_amount <= 0:
                continue
            row.amount = flt(
                fixed_amount * ratio
                + CustomSalarySlip._preserved_additional_amount(row),
                row.precision("amount"),
            )
            row.flags.nepal_earned_salary_adjusted = True

        variables.update(
            {
                "attendance_deduction_applied_to_earnings": result[
                    "applied_deduction"
                ],
                "attendance_deduction_unapplied": result["unapplied_deduction"],
                "fixed_basic_remuneration": fixed_base,
                "earned_basic_remuneration": earned_base,
            }
        )

    def _scale_contribution_deductions(self):
        result = getattr(self, "_earned_salary_result", None)
        if not result:
            return

        fixed_base = flt(result.get("fixed_contribution_base"))
        earned_base = flt(result.get("earned_contribution_base"))
        ratio = earned_base / fixed_base if fixed_base else 1.0
        for row in self.get("deductions") or []:
            if not _matches_component(row.salary_component, CONTRIBUTION_DEDUCTIONS):
                continue
            fixed_amount = self._regular_component_amount(row)
            if fixed_amount <= 0:
                continue
            row.amount = flt(
                fixed_amount * ratio
                + CustomSalarySlip._preserved_additional_amount(row),
                row.precision("amount"),
            )
            row.flags.nepal_earned_salary_adjusted = True

    def _restore_attendance_deduction_flags(self):
        """Reset row flags before applying the current setting.

        Salary Detail rows are reused when a draft slip recalculates. Stock HRMS
        does not refresh these metadata flags on an existing row, so a slip that
        was once informational would otherwise stay excluded after the setting
        is disabled or an oversized deduction leaves a real residual.
        """
        for row in self.get("deductions") or []:
            if not _matches_component(
                row.salary_component, ATTENDANCE_DEDUCTION_COMPONENTS
            ):
                continue
            values = frappe.get_cached_value(
                "Salary Component",
                row.salary_component,
                [
                    "do_not_include_in_total",
                    "do_not_include_in_accounts",
                    "exempted_from_income_tax",
                ],
            ) or (0, 0, 0)
            (
                row.do_not_include_in_total,
                row.do_not_include_in_accounts,
                row.exempted_from_income_tax,
            ) = (cint(value) for value in values)

    def _make_attendance_deduction_informational(self):
        result = getattr(self, "_earned_salary_result", None)
        if not result:
            return

        rows = [
            row
            for row in self.get("deductions") or []
            if _matches_component(
                row.salary_component, ATTENDANCE_DEDUCTION_COMPONENTS
            )
        ]
        if not rows:
            return

        unapplied = flt(result.get("unapplied_deduction"), 2)
        if unapplied:
            # A deduction larger than every fixed earning cannot be represented
            # by non-negative earned rows. Keep only that residual as a real
            # deduction so the complete penalty is still collected.
            original_total = flt(sum(flt(row.amount) for row in rows), 2)
            remaining = unapplied
            for index, row in enumerate(rows):
                if index == len(rows) - 1:
                    amount = remaining
                else:
                    amount = (
                        flt(unapplied * flt(row.amount) / original_total, 2)
                        if original_total
                        else 0
                    )
                    remaining = flt(max(remaining - amount, 0), 2)
                row.amount = flt(amount, row.precision("amount"))
            return

        for row in rows:
            row.do_not_include_in_total = 1
            row.do_not_include_in_accounts = 1
            row.exempted_from_income_tax = 0

    def _inject_cit_contribution(self, data):
        """Expose the effective CIT election to formulas and snapshot this period."""
        from nepal_hrms.custom_code.payroll.retirement_tax import get_cit_contribution

        period_start = getdate(data.get("start_date") or self.start_date)
        election = get_cit_contribution(self.employee, period_start)
        data["cit_contribution"] = flt(election.monthly_amount)

        if period_start == getdate(self.start_date):
            self.custom_cit_contribution_reference = election.name
            self.custom_cit_contribution_amount = flt(election.monthly_amount)

    def _inject_salary_allowances(self, data):
        """Expose Nepal Salary Allowance rows to formulas as nsa_<abbr>.

        SSA scalar fields arrive automatically (SalarySlip selects "*"); child
        tables do not. This must run on *every* pass: calculate_net_pay() can be
        invoked more than once per save and builds a fresh `data` dict each time.
        """
        if not hasattr(self, "_nepal_allowance_map"):
            try:
                from nepal_hrms.custom_code.payroll.salary_breakdown import get_allowance_map

                ssa = getattr(self, "_salary_structure_assignment", None) or {}
                self._nepal_allowance_map = get_allowance_map(ssa.get("name"))
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(), "Nepal salary allowance injection failed"
                )
                self._nepal_allowance_map = {}
        data.update(self._nepal_allowance_map)
        data.setdefault("nsa_other_allowance", 0)

    def eval_condition_and_formula(self, struct_row, data):
        self._inject_salary_allowances(data)
        self._inject_cit_contribution(data)
        if not hasattr(self, "_nepal_hr_variables_loaded"):
            compute_nepal_hr_variables(self, data)
            self._nepal_hr_variables_loaded = True
        else:
            for k, v in getattr(self, "_nepal_hr_vars", {}).items():
                data.setdefault(k, v)

        # Existing submitted Nepal structures may still have a blank formula on
        # their CIT row. Resolve it here as well as configuring new structures.
        if struct_row.salary_component == "CIT":
            return flt(data.get("cit_contribution"))

        return super().eval_condition_and_formula(struct_row, data)

    def compute_taxable_earnings_for_year(self):
        super().compute_taxable_earnings_for_year()

        from nepal_hrms.custom_code.payroll.retirement_tax import (
            apply_retirement_cap_to_taxable_earnings,
        )

        apply_retirement_cap_to_taxable_earnings(self)

    def compute_annual_deductions_before_tax_calculation(self):
        stock_deductions = super().compute_annual_deductions_before_tax_calculation()

        if not getattr(self, "tax_slab", None) or not self.tax_slab.allow_tax_exemption:
            return stock_deductions

        from nepal_hrms.custom_code.payroll.retirement_tax import capped_annual_deductions

        return capped_annual_deductions(self, stock_deductions)

    def on_submit(self):
        if self.net_pay < 0:
            frappe.msgprint(_("Warning: Submitted salary slip with negative Net Pay."))

        self.set_status()
        self.update_status(self.name)

        make_loan_repayment_entry(self)

        if not frappe.flags.via_payroll_entry and not frappe.flags.in_patch:
            email_salary_slip = cint(frappe.db.get_single_value("Payroll Settings", "email_salary_slip_to_employee"))
            if email_salary_slip:
                self.email_salary_slip()

        self.update_payment_status_for_gratuity_and_leave_encashment()

    def compute_income_tax_breakup(self):
        super().compute_income_tax_breakup()

        if not hasattr(self, "remaining_sub_periods"):
            return

        retirement = getattr(self, "_nepal_retirement_tax", frappe._dict())
        assessable = flt(retirement.get("assessable_employment_income"))
        contributions = flt(retirement.get("actual_contributions"))
        one_third_limit = flt(retirement.get("one_third_limit"))
        annual_limit = flt(retirement.get("annual_limit"))
        allowed_retirement = flt(retirement.get("allowed_deduction"))
        annual_taxable = flt(self.get("annual_taxable_amount", 0))
        total_tax = flt(self.get("total_structured_tax_amount", 0))
        tax_deducted = flt(
            self.get("previous_total_paid_taxes", self.get("income_tax_deducted_till_date", 0))
        )
        remaining_tax = flt(max(total_tax - tax_deducted, 0), 2)
        remaining_months = self.remaining_sub_periods
        current_tax = flt(self.get("current_month_income_tax", 0))
        annual_deductions = flt(self.get("deductions_before_tax_calculation", 0))

        self.custom_assessable_employment_income = assessable
        self.custom_one_third_assessable_income = one_third_limit
        self.custom_total_retirement_contribution = contributions
        self.custom_annual_retirement_limit = annual_limit
        self.custom_allowed_retirement_deduction = allowed_retirement
        self.custom_annual_taxable_deductions = annual_deductions
        self.custom_projected_annual_tds = total_tax
        self.custom_tds_paid_till_date = tax_deducted
        self.custom_remaining_payroll_periods = remaining_months
        self.custom_current_period_tds = current_tax

        rows = [
            ("Annual Assessable Employment Income", assessable, None),
            ("Projected SSF / PF / Gratuity / CIT", contributions, None),
            ("One-third of Assessable Income", one_third_limit, None),
            ("Annual Retirement Ceiling", annual_limit, None),
            ("Allowed Retirement Deduction", allowed_retirement, "min(actual, one-third, NPR 500,000)"),
            ("Annual Taxable Amount", annual_taxable, None),
            ("Total Annual Tax (Projected)", total_tax, None),
            ("Tax Deducted Till Date", tax_deducted, None),
            ("Remaining Tax to Deduct", remaining_tax, "annual tax minus tax already deducted"),
        ]
        detail_rows = "".join(
            (
                "<tr>"
                f"<td><b>{label}</b>{f'<br><small>{note}</small>' if note else ''}</td>"
                f"<td style=\"text-align: right;\">{frappe.utils.fmt_money(amount)}</td>"
                "</tr>"
            )
            for label, amount, note in rows
        )

        html = f"""
        <table class="table table-bordered">
            <thead>
                <tr>
                    <th colspan="2" style="background-color: var(--bg-light-gray); text-align: center;"><b>TDS Calculation Breakdown</b></th>
                </tr>
            </thead>
            <tbody>
                {detail_rows}
                <tr>
                    <td><b>Remaining Sub Periods</b><br><small>Months remaining in fiscal year</small></td>
                    <td style="text-align: right;">{remaining_months}</td>
                </tr>
                <tr style="background-color: var(--bg-light-gray);">
                    <td><b>Current Month Income Tax</b><br><small>Remaining tax divided over remaining periods</small></td>
                    <td style="text-align: right; color: var(--text-color);"><b>{frappe.utils.fmt_money(current_tax)}</b></td>
                </tr>
            </tbody>
        </table>
        """
        self.custom_tax_breakup_html = html
        self.custom_tax_calculation_data = frappe.as_json(
            {
                "cit_election": self.get("custom_cit_contribution_reference"),
                "monthly_cit": flt(self.get("custom_cit_contribution_amount")),
                "assessable_employment_income": assessable,
                "projected_retirement_contributions": contributions,
                "one_third_limit": one_third_limit,
                "annual_retirement_limit": annual_limit,
                "allowed_retirement_deduction": allowed_retirement,
                "annual_taxable_deductions": annual_deductions,
                "annual_taxable_amount": annual_taxable,
                "projected_annual_tax": total_tax,
                "tax_deducted_till_date": tax_deducted,
                "current_month_tax": current_tax,
            }
        )

from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry
from hrms.payroll.doctype.payroll_entry.payroll_entry import (
    show_payroll_submission_status
)
from hrms.payroll.doctype.salary_withholding.salary_withholding import link_bank_entry_in_salary_withholdings

def submit_salary_slips_for_employees(payroll_entry, salary_slips, publish_progress=True):
    if isinstance(payroll_entry, str):
        payroll_entry = frappe.get_doc("Payroll Entry", payroll_entry)

    submitted = []
    unsubmitted = []
    frappe.flags.via_payroll_entry = True
    count = 0

    if not salary_slips:
        submitted_slips_list = payroll_entry.get_sal_slip_list(ss_status=1)
        if submitted_slips_list:
            submitted = [frappe.get_doc("Salary Slip", d[0]) for d in submitted_slips_list]

    for entry in salary_slips:
        try:
            salary_slip = frappe.get_doc("Salary Slip", entry[0])
            salary_slip.submit()
            submitted.append(salary_slip)
        except Exception as e:
            frappe.log_error(
                title=f"Failed to submit {entry[0]}",
                message=traceback.format_exc()
            )
            unsubmitted.append(entry[0])

        count += 1
        if publish_progress and len(salary_slips) > 0:
            frappe.publish_progress(
                count * 100 / len(salary_slips),
                title=_("Submitting Salary Slips...")
            )

    if submitted:
        try:
            payroll_entry.make_accrual_jv_entry(submitted)
            payroll_entry.email_salary_slip(submitted)
            payroll_entry.db_set({
                "salary_slips_submitted": 1,
                "status": "Submitted",
                "error_message": ""
            })
        except Exception as e:
            err_trace = traceback.format_exc()
            frappe.log_error(
                title="Error in accrual/email step",
                message=err_trace
            )
            frappe.throw(_("Error creating Journal Entry for Payroll Entry {0}: {1}").format(payroll_entry.name, str(e)))

    show_payroll_submission_status(submitted, unsubmitted, payroll_entry)
    frappe.flags.via_payroll_entry = False


class CustomPayrollEntry(PayrollEntry):
    @frappe.whitelist()
    def fill_employee_details(self):
        """Restrict the run to one salary structure when custom_salary_structure is set.

        Stock Payroll Entry has no structure filter, so it pulls every employee in
        the company. Wages and Salary structures post to different expense
        accounts, so runs are normally kept separate.
        """
        result = super().fill_employee_details()

        structure = getattr(self, "custom_salary_structure", None)
        if not structure:
            return result

        keep = set(
            frappe.get_all(
                "Salary Structure Assignment",
                filters={
                    "salary_structure": structure,
                    "docstatus": 1,
                    "from_date": ["<=", self.end_date],
                },
                pluck="employee",
            )
        )
        filtered = [e for e in self.get("employees") if e.employee in keep]
        if not filtered:
            frappe.throw(
                _("No employees are assigned to Salary Structure {0} for this period.").format(
                    frappe.bold(structure)
                ),
                title=_("No employees found"),
            )

        self.set("employees", filtered)
        self.number_of_employees = len(filtered)
        return result

    def should_add_component_to_accrual_jv(self, component_type: str, item: dict) -> bool:
        add_component = super().should_add_component_to_accrual_jv(component_type, item)
        if not add_component:
            return False

        do_not_include_in_accounts, statistical_component = frappe.get_cached_value(
            "Salary Component",
            item["salary_component"],
            ["do_not_include_in_accounts", "statistical_component"],
        ) or (0, 0)

        if cint(do_not_include_in_accounts) or cint(statistical_component):
            return False

        return True

    @frappe.whitelist()
    def submit_salary_slips(self):
        self.check_permission("write")
        salary_slips = self.get_sal_slip_list(ss_status=0)
        
        if not salary_slips:
            submitted_slips = self.get_sal_slip_list(ss_status=1)
            if submitted_slips:
                submit_salary_slips_for_employees(self, [], publish_progress=False)
                return

        if len(salary_slips) > 30 or frappe.flags.enqueue_payroll_entry:
            self.db_set("status", "Queued")
            frappe.enqueue(
                submit_salary_slips_for_employees,
                timeout=3000,
                payroll_entry=self,
                salary_slips=salary_slips,
                publish_progress=False,
            )
            frappe.msgprint(
                _("Salary Slip submission is queued. It may take a few minutes"),
                alert=True,
                indicator="blue",
            )
        else:
            submit_salary_slips_for_employees(self, salary_slips, publish_progress=False)

    @frappe.whitelist()
    def make_bank_entry(self, for_withheld_salaries: bool = False) -> Optional[Document]:
        self.check_permission("write")
        self.employee_based_payroll_payable_entries = {}
        employee_wise_accounting_enabled = frappe.db.get_single_value(
        "Payroll Settings", "process_payroll_accounting_entry_based_on_employee"
    )

        salary_slip_total = 0
        salary_details = self.get_salary_slip_details(for_withheld_salaries)

        for sd in salary_details:
            if not sd.salary_component:
                continue

            if sd.parentfield == "earnings":
                result = frappe.db.get_value(
                "Salary Component",
                sd.salary_component,
                (
                    "is_flexible_benefit",
                    "only_tax_impact",
                    "create_separate_payment_entry_against_benefit_claim",
                    "statistical_component",
                ),
                cache=True,
            )

                if result:
                    is_flexible_benefit, only_tax_impact, create_separate_je, statistical_component = result
                else:
                    is_flexible_benefit = only_tax_impact = create_separate_je = statistical_component = 0

                if only_tax_impact != 1 and statistical_component != 1:
                    if is_flexible_benefit == 1 and create_separate_je == 1:
                        self.set_accounting_entries_for_bank_entry(
                        sd.amount, sd.salary_component
                    )
                    else:
                        if employee_wise_accounting_enabled:
                            self.set_employee_based_payroll_payable_entries(
                            "earnings",
                            sd.employee,
                            sd.amount,
                            sd.salary_structure,
                        )
                    salary_slip_total += sd.amount

            elif sd.parentfield == "deductions":
                statistical_component = frappe.db.get_value(
                "Salary Component",
                sd.salary_component,
                "statistical_component",
                cache=True,
            ) or 0

                if not statistical_component:
                    if employee_wise_accounting_enabled:
                        self.set_employee_based_payroll_payable_entries(
                        "deductions",
                        sd.employee,
                        sd.amount,
                        sd.salary_structure,
                    )
                    salary_slip_total -= sd.amount

        total_loan_repayment = self.process_loan_repayments_for_bank_entry(salary_details) or 0
        salary_slip_total -= total_loan_repayment

        bank_entry = None
        if salary_slip_total != 0:
            remark = "withheld salaries" if for_withheld_salaries else "salaries"
            bank_entry = self.set_accounting_entries_for_bank_entry(
                salary_slip_total, remark, employee_wise_accounting_enabled
            )
            if for_withheld_salaries:
                link_bank_entry_in_salary_withholdings(salary_details, bank_entry.name)

        else:
            frappe.msgprint(_("Total Net Pay is zero; Bank Entry will not be created."))

        return bank_entry
