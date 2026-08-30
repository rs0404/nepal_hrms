import frappe
def execute():
    if not frappe.db.exists("Page", "live_attendance_board"):
        page = frappe.new_doc("Page")
        page.page_name = "live_attendance_board"
        page.module = "Nepal HRMS"
        page.standard = "Yes"
        page.title = "Live Attendance Board"
        page.insert(ignore_permissions=True)
        frappe.db.commit()
        print("Page target created natively!")
    else:
        print("Page already exists.")
