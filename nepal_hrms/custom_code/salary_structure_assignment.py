import frappe
from frappe.utils import flt

def validate_leave_encashment(doc, method=None):
    formula = doc.get("custom_leave_encashment_formula")
    if not formula and doc.salary_structure:
        formula = frappe.db.get_value("Salary Structure", doc.salary_structure, "custom_leave_encashment_formula")

    if formula:
        # Context to evaluate the formula
        context = {
            "base": flt(doc.base),
            "revised_salary": flt(doc.base)  # Add common aliases for base just in case
        }
        
        if doc.salary_structure:
            details = frappe.get_all("Salary Detail", filters={"parent": doc.salary_structure}, fields=["abbr", "formula", "amount"])
            # Multi-pass evaluation to resolve dependent formulas like basic_salary
            for _ in range(3):
                for d in details:
                    if d.abbr not in context:
                        try:
                            if d.formula:
                                context[d.abbr] = frappe.safe_eval(d.formula, None, context)
                            else:
                                context[d.abbr] = flt(d.amount)
                        except Exception:
                            pass
        
        print(f"Context after evaluation: {context}")
        
        try:
            # Safely evaluate the user-entered formula
            encashment_value = frappe.safe_eval(formula, None, context)
            print(f"Evaluated encashment_value: {encashment_value}")
            doc.leave_encashment_amount_per_day = flt(encashment_value)
        except Exception as e:
            print(f"Exception during encashment eval: {e}")
            frappe.throw(f"Invalid Leave Encashment Formula: {str(e)}")
