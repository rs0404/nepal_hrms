import frappe

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
        has_role = False
        for r in report.roles:
            if r.role == role_name:
                has_role = True
        if not has_role:
            report.append("roles", {"role": role_name})
            report.save(ignore_permissions=True)

    frappe.db.commit()
