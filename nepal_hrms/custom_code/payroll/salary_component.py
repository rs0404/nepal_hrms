import frappe
from frappe import _
from frappe.exceptions import DoesNotExistError

def create_salary_component(component_data: dict) -> bool:
    if not isinstance(component_data, dict) or not component_data.get("name"):
        frappe.logger().error("Invalid component_data: must be a dict with 'name' field")
        return False

    try:
        default_values = {
            "amount": 0.0,
            "amount_based_on_formula": 0,
            "condition": None,
            "depends_on_payment_days": 0,
            "description": None,
            "disabled": 0,
            "do_not_include_in_total": 0,
            "formula": None,
            "is_flexible_benefit": 0,
            "pay_against_benefit_claim": 0,
            "create_separate_payment_entry_against_benefit_claim": 0,
            "only_tax_impact": 0,
            "is_tax_applicable": 1,
            "exempted_from_income_tax": 1,
            "is_income_tax_component": 1,
            "remove_if_zero_valued": 1,
            "round_to_the_nearest_integer": 0,
            "salary_component": None,
            "salary_component_abbr": None,
            "statistical_component": 0,
            "type": "Earning",
            "variable_based_on_taxable_salary": 0,
        }
        for key, value in default_values.items():
            component_data.setdefault(key, value)

        if "revised_salary" in component_data and component_data["revised_salary"] is None:
            component_data["revised_salary"] = component_data.get("ctc", 0)

        existing_component = frappe.get_all(
            "Salary Component",
            filters={"name": component_data["name"]},
            limit_page_length=1
        )

        if existing_component:
            existing_doc = frappe.get_doc("Salary Component", component_data["name"])
            has_changes = False

            for key, value in component_data.items():
                if hasattr(existing_doc, key) and getattr(existing_doc, key) != value:
                    setattr(existing_doc, key, value)
                    has_changes = True

            if has_changes:
                existing_doc.save(ignore_permissions=True)
                frappe.logger().info(f"Updated Salary Component: {component_data['name']}")
            else:
                frappe.logger().info(f"No changes detected for Salary Component: {component_data['name']}. Skipping update.")
        else:
            new_salary_component = frappe.get_doc({
                "doctype": "Salary Component",
                **component_data
            })
            new_salary_component.insert(ignore_permissions=True)
            frappe.logger().info(f"Created Salary Component: {component_data['name']}")

        return True

    except Exception as e:
        frappe.logger().error(f"Error while creating/updating Salary Component '{component_data.get('name', 'Unknown')}': {str(e)}")
        return False

def create_multiple_salary_components():
    try:
        frappe.logger().info("Started creating multiple salary components...")
        salary_components = [
            {
                "amount_based_on_formula": 1,
                "formula": "((((taxable_salary) * 12) * 0.01)/12) if ((taxable_salary) * 12) <= 1000000 else (((1000000 * 0.01) + (((taxable_salary) * 12) - 1000000) * 0.1)/12) if ((taxable_salary) * 12) <= 1500000 else (((1000000*0.01) + (500000*0.1) + (((taxable_salary)*12) - 1500000) * 0.2)/12) if ((taxable_salary)*12) <= 2500000 else (((1000000*0.01) + (500000*0.1) + (1000000*0.2) + ((taxable_salary)*12 - 2500000) *0.27)/12) if ((taxable_salary)*12)<=4000000 else (((1000000*0.01) + (500000*0.1) + (1000000*0.2) + (1500000*0.27) + ((taxable_salary)*12 - 4000000)*0.29)/12) if ((taxable_salary)*12)>4000000 else 0",
                "exempted_from_income_tax": 0,
                "name": "Income Tax Married",
                "salary_component": "Income Tax Married",
                "salary_component_abbr": "income_tax_married",
                "type": "Deduction"
            },
            {
                "amount_based_on_formula": 1,
                "formula": "((((taxable_salary) * 12) * 0.01)/12) if ((taxable_salary) * 12) <= 1000000 else (((1000000 * 0.01) + (((taxable_salary) * 12) - 1000000) * 0.1)/12) if ((taxable_salary) * 12) <= 1500000 else (((1000000*0.01) + (500000*0.1) + (((taxable_salary)*12) - 1500000) * 0.2)/12) if ((taxable_salary)*12) <= 2500000 else (((1000000*0.01) + (500000*0.1) + (1000000*0.2) + ((taxable_salary)*12 - 2500000) *0.27)/12) if ((taxable_salary)*12)<=4000000 else (((1000000*0.01) + (500000*0.1) + (1000000*0.2) + (1500000*0.27) + ((taxable_salary)*12 - 4000000)*0.29)/12) if ((taxable_salary)*12)>4000000 else 0",
                "exempted_from_income_tax": 0,
                "name": "Income Tax Unmarried",
                "salary_component": "Income Tax Unmarried",
                "salary_component_abbr": "income_tax_unmarried",
                "type": "Deduction"
            },
            {
                "variable_based_on_taxable_salary": 1,
                "exempted_from_income_tax": 0,
                "name": "TDS",
                "salary_component": "TDS",
                "salary_component_abbr": "tds",
                "type": "Deduction"
            },
            {
                "amount_based_on_formula": 1,
                "exempted_from_income_tax": 0,
                "formula": "0.01/12 * (annual_taxable_amount if annual_taxable_amount <= 1000000 else 1000000)",
                "name": "Social Security Tax",
                "salary_component": "Social Security Tax",
                "salary_component_abbr": "social_security_tax",
                "type": "Deduction"
            },
            {
                "is_flexible_benefit": 1,
                "pay_against_benefit_claim": 1,
                "create_separate_payment_entry_against_benefit_claim": 1,
                "name": "Festival Allowance",
                "salary_component": "Festival Allowance",
                "salary_component_abbr": "festival_allowance",
                "type": "Earning"
            },
            {
                "amount_based_on_formula": 1,
                "formula": "custom_basic_salary",
                "name": "Basic Salary",
                "salary_component": "Basic Salary",
                "salary_component_abbr": "basic_salary",
                "type": "Earning"
            },
            {
                "amount_based_on_formula": 1,
                "formula": "nsa_other_allowance",
                "name": "Other Allowance",
                "salary_component": "Other Allowance",
                "salary_component_abbr": "other_allowance",
                "type": "Earning"
            },
            {
                "amount_based_on_formula": 1,
                "formula": "custom_basic_remuneration * .0833",
                "name": "Gratuity",
                "salary_component": "Gratuity",
                "salary_component_abbr": "gratuity",
                "type": "Earning"
            },
            {
                "amount_based_on_formula": 1,
                "formula": "custom_basic_remuneration * .1",
                "name": "Provident Fund Employee",
                "salary_component": "Provident Fund Employee",
                "salary_component_abbr": "provident_fund_employee",
                "type": "Deduction"
            },
            {
                "amount_based_on_formula": 1,
                "formula": "custom_basic_remuneration * .1",
                "name": "Provident Fund Employer",
                "salary_component": "Provident Fund Employer",
                "salary_component_abbr": "provident_fund_employer",
                "type": "Earning"
            },
            {
                "amount_based_on_formula": 1,
                "formula": "custom_basic_remuneration * .1",
                "name": "Provident Fund Employer Deduction",
                "salary_component": "Provident Fund Employer Deduction",
                "salary_component_abbr": "provident_fund_employer_deduction",
                "type": "Deduction"
            },
            {
                "amount_based_on_formula": 1,
                "formula": "custom_basic_remuneration * .0833",
                "name": "Gratuity Deduction",
                "salary_component": "Gratuity Deduction",
                "salary_component_abbr": "gratuity_deduction",
                "type": "Deduction"
            },
            {
                "amount_based_on_formula": 1,
                "formula": "custom_basic_remuneration * .20",
                "name": "Employer's Contribution SSF Deduction",
                "salary_component": "Employer's Contribution SSF Deduction",
                "salary_component_abbr": "employers_contribution_ssf_deduction",
                "type": "Deduction"
            },
            {
                "amount_based_on_formula": 1,
                "formula": "custom_basic_remuneration * .11",
                "name": "Employee's Contribution SSF",
                "salary_component": "Employee's Contribution SSF",
                "salary_component_abbr": "employees_contribution_ssf",
                "type": "Deduction"
            },
            {
                "amount_based_on_formula": 1,
                "formula": "custom_basic_remuneration * .20",
                "name": "Employer's Contribution SSF",
                "salary_component": "Employer's Contribution SSF",
                "salary_component_abbr": "employers_contribution_ssf",
                "type": "Earning"
            },
            {
                "amount_based_on_formula": 1,
                "formula": "custom_dearness_allowance",
                "name": "Dearness Allowance",
                "salary_component": "Dearness Allowance",
                "salary_component_abbr": "dearness_allowance",
                "type": "Earning",
                "description": "\u092e\u0939\u0901\u0917\u0940 \u092d\u0924\u094d\u0924\u093e. Part of the statutory minimum wage; excluded from the SSF/PF base by default.",
            },
            {
                "name": "Overtime",
                "salary_component": "Overtime",
                "salary_component_abbr": "overtime",
                "type": "Earning"
            },
            {
                "name": "Earning Adjustment",
                "salary_component": "Earning Adjustment",
                "salary_component_abbr": "earning_adjustment",
                "type": "Earning"
            },
            {
                "name": "Deduction Adjustment",
                "salary_component": "Deduction Adjustment",
                "salary_component_abbr": "deduction_adjustment",
                "type": "Deduction"
            },
            {
                "name": "Insurance",
                "salary_component": "Insurance",
                "salary_component_abbr": "insurance",
                "type": "Deduction"
            },
            {
                "amount_based_on_formula": 1,
                "formula": "cit_contribution",
                "name": "CIT",
                "salary_component": "CIT",
                "salary_component_abbr": "cit",
                "type": "Deduction"
            },
            {
                "amount_based_on_formula": 1,
                "formula": "custom_grade_amount",
                "name": "Employee Grade Amount",
                "salary_component": "Employee Grade Amount",
                "salary_component_abbr": "employee_grade_amount",
                "type": "Earning"
            },
            {
                "amount_based_on_formula": 1,
                "formula": LEAVE_LATE_FORMULA,
                "name": "Leave and Late Deduction",
                "salary_component": "Leave and Late Deduction",
                "salary_component_abbr": "leave_and_late_deduction",
                "type": "Deduction",
                "description": "C&R attendance amount. Informational only when earned-salary attendance deductions are enabled; otherwise posted as an actual deduction.",
            },
            {
                "amount_based_on_formula": 1,
                "formula": "leave_late_deduction_total",
                "name": "Leaves and Late Comings",
                "salary_component": "Leaves and Late Comings",
                "salary_component_abbr": "leaves_and_late_comings",
                "type": "Deduction",
                "description": "Legacy C&R attendance amount. Informational only when earned-salary attendance deductions are enabled; otherwise posted as an actual deduction.",
            },
        ]

        for component in salary_components:
            create_salary_component(component)

        frappe.logger().info("Finished creating multiple salary components.")

    except Exception as e:
        frappe.logger().error(f"Error while creating multiple salary components: {str(e)}")


LEAVE_LATE_FORMULA = "leave_late_deduction_total"
# One figure, computed once in compute_nepal_hr_variables and applied to earnings
# by the earned-salary pass. Spelling the terms out again here let the row drift
# from the amount actually charged every time a term moved -- which is how
# late/early half days leaving for penalty_days silently halved this row.
# Note: ½P / 1P occurrence-pool penalties are charged through penalty_days on their
# own configured base, and are excluded from unapproved_absent_days.


def update_salary_component_formulas():
    try:
        salary_components = frappe.get_all("Salary Component", fields=["name", "formula"])

        for component in salary_components:
            if component["name"] == "Basic Salary":
                frappe.db.set_value("Salary Component", component["name"], "formula", "custom_basic_salary")
            elif component["name"] == "Other Allowance":
                frappe.db.set_value("Salary Component", component["name"], "formula", "nsa_other_allowance")
            elif component["name"] == "CIT":
                frappe.db.set_value(
                    "Salary Component",
                    component["name"],
                    {"formula": "cit_contribution", "amount_based_on_formula": 1},
                )
            elif component["name"] in ("Leave and Late Deduction", "Leaves and Late Comings"):
                frappe.db.set_value(
                    "Salary Component",
                    component["name"],
                    {
                        "formula": LEAVE_LATE_FORMULA,
                        "amount_based_on_formula": 1,
                    },
                )

        frappe.db.commit()
        frappe.logger().info("Salary Component formulas updated successfully.")

    except Exception as e:
        frappe.logger().error(f"Error while updating Salary Component formulas: {str(e)}")