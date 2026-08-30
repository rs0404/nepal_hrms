import frappe
from nepal_compliance.nepali_date_utils.nepali_date import ad_to_bs

@frappe.whitelist()
def get_calendar_data():
    """
    Returns the current Nepali (BS) year, month, and day based on today's AD date.
    Used for setting default filters in BS-based reports.
    """
    today = frappe.utils.today()
    bs_date = ad_to_bs(today)
    
    return {
        "current_bs_year": bs_date.get("year"),
        "current_bs_month": bs_date.get("month"),
        "current_bs_day": bs_date.get("day")
    }
