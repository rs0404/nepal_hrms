import frappe
from frappe import _
from frappe.utils import getdate, flt
from datetime import date
from typing import Union, Optional

@frappe.whitelist()
def get_max_amount_eligible(employee: str, claim_date: Optional[Union[str, date]]) -> float:
    if not employee:
        return 0.0

    try:
        emp = frappe.get_doc("Employee", employee)
    except frappe.DoesNotExistError:
        return 0.0

    if not emp.date_of_joining:
        return 0.0

    # Festival expense is one month's *basic remuneration* (Labour Act s.34(4) /
    # Labour Rules), pro-rated for under a year of service. Read it from the
    # Salary Structure Assignment effective on the claim date so a later raise
    # cannot retroactively re-price an earlier claim. Employee.revised_salary is
    # the legacy, un-dated fallback.
    claim_dt = getdate(claim_date) if claim_date else date.today()
    base_salary = _basic_remuneration_on(employee, claim_dt)
    if not base_salary:
        legacy = flt(emp.revised_salary) if getattr(emp, "revised_salary", None) else flt(emp.ctc)
        base_salary = flt(legacy) * 0.6

    if not base_salary:
        return 0.0

    doj = getdate(emp.date_of_joining)
    from dateutil.relativedelta import relativedelta

    rd = relativedelta(claim_dt, doj)
    months_worked = rd.years * 12 + rd.months

    if months_worked < 0:
        months_worked = 0

    if months_worked >= 12:
        return flt(base_salary)
    return flt(flt(base_salary / 12.0) * months_worked)


def _basic_remuneration_on(employee, on_date):
    """Basic remuneration from the Salary Structure Assignment effective on a date."""
    if not frappe.db.has_column("Salary Structure Assignment", "custom_basic_remuneration"):
        return 0.0
    row = frappe.db.get_value(
        "Salary Structure Assignment",
        {"employee": employee, "from_date": ["<=", on_date], "docstatus": 1},
        ["custom_basic_remuneration", "custom_basic_salary"],
        order_by="from_date desc",
        as_dict=True,
    )
    if not row:
        return 0.0
    return flt(row.get("custom_basic_remuneration")) or flt(row.get("custom_basic_salary"))