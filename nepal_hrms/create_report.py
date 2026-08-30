import frappe

def create_report():
    report_name = "Monthly Attendance Sheet BS"
    
    if frappe.db.exists("Report", report_name):
        doc = frappe.get_doc("Report", report_name)
    else:
        doc = frappe.new_doc("Report")
        doc.report_name = report_name
    
    doc.ref_doctype = "Attendance"
    doc.report_type = "Script Report"
    doc.module = "Nepal HRMS"
    doc.is_standard = "Yes"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"Created/Updated Report: {report_name}")
