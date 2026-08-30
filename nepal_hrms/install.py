import frappe

from nepal_hrms.custom_code.payroll.income_tax_slab import create_income_tax_slabs_for_all_companies
from nepal_hrms.custom_field import create_custom_fields
from nepal_hrms.custom_code.payroll.payroll_settings import modify_email_salary_slip_default
from nepal_hrms.custom_code.leave_type.leave_type import setup_default_leave_types
from nepal_hrms.custom_code.payroll.salary_component import create_multiple_salary_components
from nepal_hrms.setup_roles import setup_roles


def install():
	create_custom_fields()
	create_multiple_salary_components()
	create_income_tax_slabs_for_all_companies()
	modify_email_salary_slip_default()
	setup_default_leave_types()
	setup_roles()
