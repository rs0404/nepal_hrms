import frappe
from frappe import _
from frappe.utils import flt, getdate, formatdate
from datetime import date
from hrms.hr.utils import validate_active_employee
from hrms.payroll.doctype.payroll_period.payroll_period import get_payroll_period
from hrms.payroll.doctype.employee_benefit_claim.employee_benefit_claim import EmployeeBenefitClaim as HRMSEmployeeBenefitClaim


class CustomEmployeeBenefitClaim(HRMSEmployeeBenefitClaim):
    """Festival allowance claims on top of stock Employee Benefit Claim.

    HRMS 16 rebuilt this doctype around the benefit ledger: the claim is dated
    by payroll_date (claim_date is gone), stock validates only the date, the
    amount against max_amount_eligible and one claim per component per month,
    and submitting raises an Additional Salary. The HRMS 15 checks this class
    used to call (validate_max_benefit_for_component, ..._for_sal_struct,
    validate_benefit_claim_amount, validate_non_pro_rata_benefit_claim) and the
    pay_against_benefit_claim field no longer exist.
    """

    def validate(self):
        validate_active_employee(self.employee)

        if not self.get("claim_festival_allowance"):
            return super().validate()

        self.ensure_festival_allowance_not_already_claimed()

        # The festival rule, not the benefit ledger, says what can be claimed.
        max_benefits = self.set_max_amount_eligible(self.employee, self.payroll_date)

        if not flt(self.claimed_amount):
            self.claimed_amount = max_benefits

        # Stock: payroll date not in the past, amount above zero and within
        # max_amount_eligible, one claim per component per month. With one
        # festival claim per payroll period that covers what the HRMS 15
        # running-total checks enforced.
        super().validate()

    def ensure_festival_allowance_not_already_claimed(self):
        payroll_period = get_payroll_period(
            self.payroll_date,
            self.payroll_date,
            frappe.db.get_value("Employee", self.employee, "company")
        )

        if not payroll_period:
            frappe.throw(_("No payroll period found for the claim date."))

        existing = frappe.db.exists(
            "Employee Benefit Claim",
            {
            "employee": self.employee,
            "claim_festival_allowance": 1,
            "docstatus": ["!=", 2],
            "name": ["!=", self.name],
            "payroll_date": ["between", [payroll_period.start_date, payroll_period.end_date]],
            },
        )

        if existing:
            frappe.throw(
                _("Festival allowance has already been claimed by employee {0} for this Payroll Period.").format(
                    self.employee,
                    formatdate(payroll_period.start_date),
                    formatdate(payroll_period.end_date),
                )
            )

    def set_max_amount_eligible(self, employee, claim_date):
        if not employee:
            self.max_amount_eligible = 0
            return self.max_amount_eligible

        emp = frappe.get_doc("Employee", employee)

        if not emp.date_of_joining:
            self.max_amount_eligible = 0
            return self.max_amount_eligible

        base_salary = flt(emp.revised_salary) if emp.revised_salary else flt(emp.ctc)
        if not base_salary:
            self.max_amount_eligible = 0
            return self.max_amount_eligible

        doj = getdate(emp.date_of_joining)
        source_date = claim_date or self.get("payroll_date")
        claim_dt = getdate(source_date) if source_date else date.today()

        if doj > claim_dt:
            self.max_amount_eligible = 0
            return self.max_amount_eligible

        months_worked = (claim_dt.year - doj.year) * 12 + (claim_dt.month - doj.month)
        if claim_dt.day < doj.day:
            months_worked -= 1

        if months_worked < 0:
            months_worked = 0

        if months_worked >= 12:
            self.max_amount_eligible = flt(base_salary * 0.6)
        else:
            per_month_ctc = flt((base_salary * 0.6) / 12.0)
            self.max_amount_eligible = flt(per_month_ctc * months_worked)

        return self.max_amount_eligible