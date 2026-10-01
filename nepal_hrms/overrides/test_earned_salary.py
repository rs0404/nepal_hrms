from datetime import date
from unittest import TestCase
from unittest.mock import patch

import frappe
from frappe import _dict
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from nepal_hrms.overrides.salary_slip import (
    CustomPayrollEntry,
    CustomSalarySlip,
    _matches_component,
    _skips_tax_projection,
    allocate_attendance_deduction,
)


def component(key, amount, contributes):
    return {"key": key, "amount": amount, "contributes": contributes}


class FakeSalaryRow(_dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.flags = _dict()

    def precision(self, _fieldname):
        return 2


class FakeMeta:
    @staticmethod
    def has_field(fieldname):
        return fieldname in ("custom_fixed_amount", "custom_fixed_gross_pay")


class FakeSalarySlip:
    def __init__(self, deductions, result):
        self.deductions = deductions
        self._earned_salary_result = _dict(result)

    def get(self, fieldname):
        return getattr(self, fieldname, [])

    _regular_component_amount = staticmethod(
        CustomSalarySlip._regular_component_amount
    )
    _set_fixed_amount = staticmethod(CustomSalarySlip._set_fixed_amount)


class FakeFixedAmountSlip:
    def __init__(self, earnings):
        self.earnings = earnings
        self.meta = FakeMeta()
        self.custom_fixed_gross_pay = 0

    def get(self, fieldname):
        return getattr(self, fieldname, [])

    @staticmethod
    def precision(_fieldname):
        return 2

    _regular_component_amount = staticmethod(
        CustomSalarySlip._regular_component_amount
    )
    _set_fixed_amount = staticmethod(CustomSalarySlip._set_fixed_amount)


class FakeEarningSlip:
    def __init__(self, earnings, components, variables):
        self.earnings = earnings
        self._components = components
        self._nepal_hr_vars = variables

    def get(self, fieldname):
        return getattr(self, fieldname, [])

    def _fixed_salary_components(self, _settings):
        return self._components, {
            index: self.earnings[index] for index in range(len(self._components))
        }

    @staticmethod
    def _has_attendance_deduction_component():
        return True

    _regular_component_amount = staticmethod(
        CustomSalarySlip._regular_component_amount
    )


class TestAttendanceDeductionAllocation(TestCase):
    def test_allowances_first_preserves_basic_when_allowances_are_enough(self):
        result = allocate_attendance_deduction(
            [
                component("basic", 60_000, True),
                component("allowance", 40_000, False),
            ],
            6_666.67,
        )

        self.assertEqual(result["earned_amounts"]["basic"], 60_000)
        self.assertEqual(result["earned_amounts"]["allowance"], 33_333.33)
        self.assertEqual(result["earned_contribution_base"], 60_000)
        self.assertEqual(result["unapplied_deduction"], 0)

    def test_proportional_mode_reduces_basic_and_allowances(self):
        result = allocate_attendance_deduction(
            [
                component("basic", 60_000, True),
                component("allowance", 40_000, False),
            ],
            6_666.67,
            proportional=True,
        )

        self.assertEqual(result["earned_amounts"]["basic"], 56_000)
        self.assertEqual(result["earned_amounts"]["allowance"], 37_333.33)
        self.assertEqual(result["earned_contribution_base"], 56_000)

    def test_allowance_shortfall_spills_into_basic(self):
        result = allocate_attendance_deduction(
            [
                component("basic", 60_000, True),
                component("allowance", 4_000, False),
            ],
            6_000,
        )

        self.assertEqual(result["earned_amounts"]["allowance"], 0)
        self.assertEqual(result["earned_amounts"]["basic"], 58_000)
        self.assertEqual(result["earned_contribution_base"], 58_000)

    def test_non_contribution_allowances_share_reduction_proportionally(self):
        result = allocate_attendance_deduction(
            [
                component("basic", 60_000, True),
                component("da", 10_000, False),
                component("transport", 30_000, False),
            ],
            8_000,
        )

        self.assertEqual(result["earned_amounts"]["da"], 8_000)
        self.assertEqual(result["earned_amounts"]["transport"], 24_000)
        self.assertEqual(result["earned_amounts"]["basic"], 60_000)

    def test_contribution_flags_control_the_earned_base(self):
        result = allocate_attendance_deduction(
            [
                component("basic", 50_000, True),
                component("grade", 5_000, True),
                component("da", 5_000, False),
            ],
            10_000,
        )

        self.assertEqual(result["earned_amounts"]["da"], 0)
        self.assertEqual(result["earned_amounts"]["basic"], 45_454.55)
        self.assertEqual(result["earned_amounts"]["grade"], 4_545.45)
        self.assertEqual(result["fixed_contribution_base"], 55_000)
        self.assertEqual(result["earned_contribution_base"], 50_000)

    def test_oversized_deduction_stops_at_zero_and_returns_residual(self):
        result = allocate_attendance_deduction(
            [
                component("basic", 6_000, True),
                component("allowance", 4_000, False),
            ],
            12_000,
        )

        self.assertEqual(result["earned_amounts"], {"basic": 0, "allowance": 0})
        self.assertEqual(result["applied_deduction"], 10_000)
        self.assertEqual(result["unapplied_deduction"], 2_000)


class TestEarnedSalaryRows(TestCase):
    def test_fixed_amount_excludes_one_off_additional_salary(self):
        row = FakeSalaryRow(
            amount=63_000,
            additional_amount=3_000,
            custom_fixed_amount=0,
            meta=FakeMeta(),
        )
        slip = FakeFixedAmountSlip([row])

        CustomSalarySlip._populate_fixed_earning_amounts(slip)
        CustomSalarySlip._set_fixed_gross_pay(slip)

        self.assertEqual(row.custom_fixed_amount, 60_000)
        self.assertEqual(slip.custom_fixed_gross_pay, 60_000)

    def test_fixed_amount_is_available_on_deductions(self):
        row = FakeSalaryRow(
            amount=6_483.75,
            default_amount=6_483.75,
            additional_amount=0,
            custom_fixed_amount=0,
            meta=FakeMeta(),
        )
        slip = FakeSalarySlip([row], {})

        CustomSalarySlip._populate_fixed_deduction_amounts(slip)

        self.assertEqual(row.custom_fixed_amount, 6_483.75)

    @patch(
        "nepal_hrms.custom_code.attendance_policy.get_hr_settings",
        return_value={
            "calculate_attendance_deductions_through_earned_salary": 0
        },
    )
    def test_setting_can_restore_legacy_actual_deduction_mode(self, _settings):
        slip = _dict()
        self.assertFalse(CustomSalarySlip._earned_salary_mode_enabled(slip))

    def test_component_matching_supports_legacy_and_variant_names(self):
        roots = ("Leave and Late Deduction", "Leaves and Late Comings")
        self.assertTrue(_matches_component("Leave and Late Deduction", roots))
        self.assertTrue(_matches_component("Leave and Late Deduction - Salary", roots))
        self.assertTrue(_matches_component("Leaves and Late Comings", roots))
        self.assertFalse(_matches_component("Deduction Adjustment - Salary", roots))
        self.assertTrue(
            _matches_component(
                "Blog Allowance",
                ("Other Allowance", "Miscellaneous Allowance", "Blog Allowance"),
            )
        )

    def test_payment_day_recalculation_preserves_adjusted_earned_amount(self):
        row = FakeSalaryRow(
            amount=56_000,
            default_amount=60_000,
            additional_amount=0,
            depends_on_payment_days=1,
        )
        row.flags.nepal_earned_salary_adjusted = True

        amount, additional = CustomSalarySlip.get_amount_based_on_payment_days(
            _dict(), row
        )

        self.assertEqual(
            CustomSalarySlip._regular_component_amount(row),
            60_000,
        )
        self.assertEqual(amount, 56_000)
        self.assertEqual(additional, 0)

    def test_overwrite_additional_salary_uses_effective_non_negative_amount(self):
        row = FakeSalaryRow(
            amount=80_000,
            default_amount=100_000,
            additional_amount=-20_000,
            additional_salary="TEST-OVERWRITE",
        )

        self.assertEqual(
            CustomSalarySlip._regular_component_amount(row),
            80_000,
        )
        self.assertEqual(
            CustomSalarySlip._preserved_additional_amount(row),
            0,
        )

    def test_additional_only_salary_is_not_part_of_fixed_allocation(self):
        row = FakeSalaryRow(
            amount=10_000,
            default_amount=0,
            additional_amount=10_000,
            additional_salary="TEST-ADDITIONAL",
        )

        self.assertEqual(CustomSalarySlip._regular_component_amount(row), 0)
        self.assertEqual(
            CustomSalarySlip._preserved_additional_amount(row),
            10_000,
        )

    def test_unconfigured_structures_do_not_start_deducting_attendance(self):
        slip = _dict(
            _salary_structure_doc=_dict(
                deductions=[_dict(salary_component="TDS")]
            )
        )
        self.assertFalse(
            CustomSalarySlip._has_attendance_deduction_component(slip)
        )

    def test_attendance_row_becomes_informational_when_fully_applied(self):
        row = FakeSalaryRow(
            salary_component="Leave and Late Deduction - Salary",
            amount=6_666.67,
            do_not_include_in_total=0,
            do_not_include_in_accounts=0,
            exempted_from_income_tax=1,
        )
        slip = FakeSalarySlip(
            [row],
            {"unapplied_deduction": 0},
        )

        CustomSalarySlip._make_attendance_deduction_informational(slip)

        self.assertEqual(row.amount, 6_666.67)
        self.assertEqual(row.do_not_include_in_total, 1)
        self.assertEqual(row.do_not_include_in_accounts, 1)
        self.assertEqual(row.exempted_from_income_tax, 0)

    @patch(
        "nepal_hrms.overrides.salary_slip.frappe.get_cached_value",
        return_value=(0, 0, 1),
    )
    def test_recalculation_restores_actual_deduction_flags(self, _cached_value):
        row = FakeSalaryRow(
            salary_component="Leave and Late Deduction - Salary",
            amount=6_666.67,
            do_not_include_in_total=1,
            do_not_include_in_accounts=1,
            exempted_from_income_tax=0,
        )
        slip = FakeSalarySlip([row], {})

        CustomSalarySlip._restore_attendance_deduction_flags(slip)

        self.assertEqual(row.do_not_include_in_total, 0)
        self.assertEqual(row.do_not_include_in_accounts, 0)
        self.assertEqual(row.exempted_from_income_tax, 1)

    def test_oversized_residual_remains_an_actual_deduction(self):
        row = FakeSalaryRow(
            salary_component="Leave and Late Deduction - Salary",
            amount=12_000,
            do_not_include_in_total=0,
            do_not_include_in_accounts=0,
            exempted_from_income_tax=1,
        )
        slip = FakeSalarySlip(
            [row],
            {"unapplied_deduction": 2_000},
        )

        CustomSalarySlip._make_attendance_deduction_informational(slip)

        self.assertEqual(row.amount, 2_000)
        self.assertEqual(row.do_not_include_in_total, 0)
        self.assertEqual(row.do_not_include_in_accounts, 0)

    @patch("nepal_hrms.overrides.salary_slip._component_flag", return_value=0)
    def test_unticked_attendance_component_stays_a_real_deduction(self, _flag):
        row = FakeSalaryRow(
            salary_component="Leave and Late Deduction - Salary",
            amount=6_666.67,
            do_not_include_in_total=0,
            do_not_include_in_accounts=0,
            exempted_from_income_tax=1,
        )
        slip = FakeSalarySlip([row], {"unapplied_deduction": 0})

        CustomSalarySlip._make_attendance_deduction_informational(slip)

        self.assertEqual(row.do_not_include_in_total, 0)
        self.assertEqual(row.do_not_include_in_accounts, 0)

    @patch("nepal_hrms.overrides.salary_slip._component_flag", return_value=1)
    def test_other_ticked_deduction_is_show_only(self, _flag):
        row = FakeSalaryRow(
            salary_component="Canteen Deduction",
            amount=1_500,
            do_not_include_in_total=0,
            do_not_include_in_accounts=0,
            exempted_from_income_tax=1,
        )
        slip = FakeSalarySlip([row], {})

        CustomSalarySlip._make_taken_from_earnings_informational(slip)

        self.assertEqual(row.amount, 1_500)
        self.assertEqual(row.do_not_include_in_total, 1)
        self.assertEqual(row.do_not_include_in_accounts, 1)
        self.assertEqual(row.exempted_from_income_tax, 0)

    def test_tax_projection_skips_ticked_components_only(self):
        flags = {
            ("Leave and Late Deduction - Salary", "custom_taken_from_earnings"): 1,
            ("Leave and Late Deduction - Salary", "custom_skip_tax_projection"): 1,
            ("Overtime Recovery", "custom_taken_from_earnings"): 0,
            ("Overtime Recovery", "custom_skip_tax_projection"): 1,
            ("CIT", "custom_taken_from_earnings"): 0,
            ("CIT", "custom_skip_tax_projection"): 0,
        }
        with patch(
            "nepal_hrms.overrides.salary_slip._component_flag",
            side_effect=lambda component, field: flags[(component, field)],
        ):
            self.assertTrue(_skips_tax_projection("Leave and Late Deduction - Salary"))
            self.assertTrue(_skips_tax_projection("Overtime Recovery"))
            self.assertFalse(_skips_tax_projection("CIT"))

    def test_contribution_deduction_scales_with_earned_basic(self):
        row = FakeSalaryRow(
            salary_component="Employee's Contribution SSF",
            amount=6_600,
            additional_amount=0,
        )
        slip = FakeSalarySlip(
            [row],
            {
                "fixed_contribution_base": 60_000,
                "earned_contribution_base": 56_000,
            },
        )

        CustomSalarySlip._scale_contribution_deductions(slip)

        self.assertEqual(row.amount, 6_160)

    @patch(
        "nepal_hrms.custom_code.attendance_policy.get_hr_settings",
        return_value={
            "proportionally_reduce_earnings_for_attendance_deductions": 1
        },
    )
    def test_proportional_earnings_and_employer_ssf_are_updated_together(
        self, _settings
    ):
        earnings = [
            FakeSalaryRow(
                salary_component="Basic Salary - Salary",
                amount=60_000,
                additional_amount=0,
            ),
            FakeSalaryRow(
                salary_component="Transport Allowance",
                amount=40_000,
                additional_amount=0,
            ),
            FakeSalaryRow(
                salary_component="Employer's Contribution SSF - Salary",
                amount=12_000,
                additional_amount=0,
            ),
        ]
        components = [
            component(0, 60_000, True),
            component(1, 40_000, False),
        ]
        slip = FakeEarningSlip(
            earnings,
            components,
            {"leave_late_deduction_total": 6_666.67},
        )

        CustomSalarySlip._apply_attendance_deduction_to_earnings(slip)

        self.assertEqual(earnings[0].amount, 56_000)
        self.assertEqual(earnings[1].amount, 37_333.33)
        self.assertEqual(earnings[2].amount, 11_200)
        self.assertEqual(
            slip._nepal_hr_vars["earned_basic_remuneration"],
            56_000,
        )


class TestEarnedSalaryAccountingSources(FrappeTestCase):
    def setUp(self):
        self.salary_slip_name = f"TEST-EARNED-SALARY-{frappe.generate_hash(length=8)}"
        self.payroll_entry_name = f"TEST-PAYROLL-{frappe.generate_hash(length=8)}"
        self.start_date = date(2026, 8, 1)
        self.end_date = date(2026, 8, 31)

        salary_slip = frappe.get_doc(
            {
                "doctype": "Salary Slip",
                "name": self.salary_slip_name,
                "employee": "TEST-EARNED-EMPLOYEE",
                "employee_name": "Test Earned Employee",
                "company": "Test Earned Company",
                "posting_date": self.end_date,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "payroll_frequency": "Monthly",
                "currency": "NPR",
                "exchange_rate": 1,
                "salary_structure": "Test Earned Structure",
                "payroll_entry": self.payroll_entry_name,
                "salary_slip_based_on_timesheet": 0,
                "status": "Submitted",
                "docstatus": 1,
            }
        )
        salary_slip.db_insert()

        self._insert_detail("earnings", "Basic Salary - Salary", 56_000)
        self._insert_detail("earnings", "Transport Allowance", 37_333.33)
        self._insert_detail(
            "earnings", "Employer's Contribution SSF - Salary", 11_200
        )
        self._insert_detail(
            "deductions",
            "Leave and Late Deduction - Salary",
            6_666.67,
            do_not_include_in_total=1,
            do_not_include_in_accounts=1,
        )
        self._insert_detail(
            "deductions", "Employee's Contribution SSF", 6_160
        )
        self._insert_detail(
            "deductions",
            "Employer's Contribution SSF Deduction",
            11_200,
        )

    def tearDown(self):
        frappe.db.delete("Salary Detail", {"parent": self.salary_slip_name})
        frappe.db.delete("Salary Slip", {"name": self.salary_slip_name})

    def _insert_detail(
        self,
        parentfield,
        salary_component,
        amount,
        do_not_include_in_total=0,
        do_not_include_in_accounts=0,
    ):
        frappe.get_doc(
            {
                "doctype": "Salary Detail",
                "name": frappe.generate_hash(length=10),
                "parent": self.salary_slip_name,
                "parenttype": "Salary Slip",
                "parentfield": parentfield,
                "salary_component": salary_component,
                "abbr": frappe.scrub(salary_component),
                "amount": amount,
                "do_not_include_in_total": do_not_include_in_total,
                "do_not_include_in_accounts": do_not_include_in_accounts,
            }
        ).db_insert()

    def _payroll_entry(self):
        return CustomPayrollEntry(
            {
                "doctype": "Payroll Entry",
                "name": self.payroll_entry_name,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "salary_slip_based_on_timesheet": 0,
            }
        )

    def test_accrual_source_contains_earned_rows_but_not_attendance_credit(self):
        payroll_entry = self._payroll_entry()

        earnings = payroll_entry.get_salary_components("earnings")
        deductions = payroll_entry.get_salary_components("deductions")

        self.assertEqual(
            flt(sum(row.amount for row in earnings), 2),
            104_533.33,
        )
        self.assertEqual(
            flt(sum(row.amount for row in deductions), 2),
            17_360,
        )
        self.assertNotIn(
            "Leave and Late Deduction - Salary",
            {row.salary_component for row in deductions},
        )

    def test_bank_source_equals_net_pay_and_excludes_informational_row(self):
        details = self._payroll_entry().get_salary_slip_details()
        earnings = sum(
            row.amount for row in details if row.parentfield == "earnings"
        )
        deductions = sum(
            row.amount for row in details if row.parentfield == "deductions"
        )

        self.assertEqual(flt(earnings - deductions, 2), 87_173.33)
        self.assertNotIn(
            "Leave and Late Deduction - Salary",
            {row.salary_component for row in details},
        )

    def test_manual_totals_exclude_informational_attendance_row(self):
        salary_slip = CustomSalarySlip(
            {
                "doctype": "Salary Slip",
                "currency": "NPR",
                "exchange_rate": 1,
                "salary_slip_based_on_timesheet": 0,
            }
        )
        salary_slip.append(
            "earnings",
            {
                "salary_component": "Basic Salary - Salary",
                "amount": 100_000,
            },
        )
        salary_slip.append(
            "deductions",
            {
                "salary_component": "Leave and Late Deduction - Salary",
                "amount": 10_000,
                "do_not_include_in_total": 1,
                "do_not_include_in_accounts": 1,
            },
        )
        salary_slip.append(
            "deductions",
            {
                "salary_component": "Employee's Contribution SSF",
                "amount": 11_000,
            },
        )

        salary_slip.set_totals()

        self.assertEqual(salary_slip.gross_pay, 100_000)
        self.assertEqual(salary_slip.total_deduction, 11_000)
        self.assertEqual(salary_slip.net_pay, 89_000)
