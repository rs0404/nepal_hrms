from hrms.payroll.doctype.salary_structure.salary_structure import SalaryStructure as HRMSSalaryStructure


class CustomSalaryStructure(HRMSSalaryStructure):
    """Stock Salary Structure; nothing is overridden on HRMS 16.

    On HRMS 15 this class softened validate_max_benefits_with_flexi(), which
    refused a structure whose flexible benefit components had no Max Benefits
    amount. HRMS 16 dropped that check: flexible benefits are now validated
    from the Employee Benefits table, by a module function. The method would
    never be called, so it is gone.

    The class stays because the hook does: without it nepal_compliance's
    override of Salary Structure would become the controller instead.
    """
