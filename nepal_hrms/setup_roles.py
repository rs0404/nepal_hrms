import frappe

REPORT_ROLES = ("HR User", "HR Manager", "Attendance Report Viewer", "Employee")


def setup_roles():
    role_name = "Attendance Report Viewer"
    if not frappe.db.exists("Role", role_name):
        frappe.get_doc({
            "doctype": "Role",
            "role_name": role_name
        }).insert(ignore_permissions=True)

    report_name = "Monthly Attendance Sheet BS"
    if frappe.db.exists("Report", report_name):
        report = frappe.get_doc("Report", report_name)
        existing = {r.role for r in report.roles}
        added = False
        for role in REPORT_ROLES:
            if role not in existing:
                report.append("roles", {"role": role})
                added = True
        if added:
            report.flags.ignore_validate = True
            report.save(ignore_permissions=True)

    from nepal_hrms.custom_code.payroll.journal_access import ensure_role

    ensure_role()

    frappe.db.commit()
