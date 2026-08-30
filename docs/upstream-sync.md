# Upstream Nepal Compliance sync

`nepal_hrms` owns all HR/Payroll overrides (Salary Slip, Attendance, Leave, CNR/OOO, BS HRMS PWA).

`nepal_compliance` should keep IRD/VAT/CBMS, invoice print formats, and shared Nepali date libraries only.

## After `git pull` / merge of upstream nepal-compliance

Upstream still ships some payroll files. If those land in `nepal_compliance` again, two apps can override the same DocType (last installed wins, or both `doc_events` fire).

Drop or revert these from `nepal_compliance` if they reappear:

- `overrides/salary_slip.py`, `overrides/salary_structure.py`, `overrides/employee_checkin.py`, `overrides/shift_type.py`, `overrides/attendance_*.py`, `overrides/employee_benefit_claim.py`, `overrides/hrms_api.py`, `overrides/employee_dashboard.py`
- `custom_code/` attendance, leave, payroll (keep `print_settings.py`)
- `api/` attendance, CNR, OOO
- CNR DocTypes, Monthly Attendance Sheet BS, Live Attendance Board
- `bshrms/`, `www/bshrms.*`, `public/bshrms/`
- HR entries in `hooks.py` (`override_doctype_class` for Salary Slip, Attendance `doc_events`, `/bshrms` route)

Leave in `nepal_compliance`: `nepali_date_utils/`, desk calendar JS (`nepali_date_lib.js`, `nepali_calendar_lib.js`), accounting custom fields, CBMS/IRD.
