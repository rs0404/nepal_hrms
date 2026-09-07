# Nepal HRMS 0.1.0 (pre-release)

**Tag:** `v0.1.0-beta`  
**Status:** Pre-release — first public cut of Nepal HRMS for Frappe v15 / Frappe HR v15  
**Date:** 7 September 2026  
**License:** GPL-3.0-or-later · Copyright © 2026 Yarsa Labs Pvt. Ltd.

This is not a 1.0. Expect settings, payroll formulas, and PWA copy to keep moving. Use on a staging site first.

---

## What this release includes

### BSHRMS (employee PWA at `/bshrms`)

- Installable PWA (standalone display, white launcher icon, service worker)
- Tabs: Home, Attendance, Leaves, Expenses, Salary
- Check-in: Normal and OOO Work, geolocation, BS + AD dates
- Quick links and request inbox (My / Team / OOO Approvals)
- Attendance calendar in BS and AD; select future working days for leave
- Split leave: gapped calendar days create separate draft Leave Applications
- Frequent leave-type chips; remaining includes Open drafts; LWP not capped
- Save blocked when Open drafts of a type exceed remaining (except LWP)
- Live / Leave board (role-gated), monthly application counts (Approved / Rejected / Pending)
- Calendar refresh after leave save
- Notifications, profile, push settings
- Home paints last-visit data from cache, then revalidates

### Nepal HRMS Settings

- HR & Attendance: Nepali dates, working hours, late/early penalty windows and occurrence pool, sandwich leave, frequent leave types, paid OOO hours, continuous LWP gross, self-approval blocks, PWA board/calendar role tables
- Payroll: daily rate basis, deduction bases, period/continuous LWP gross, SSF/PF contribution switches, overtime multiplier, leave encashment formula, BS payroll period, minimum wage, GL accounts, scheduled payroll, one-click payroll setup

### Live Attendance

- Desk Kanban: Pending, Active, Checked Out, On Leave, Upcoming
- Department groups, server clock, BS date, punch timeline, OOO tag
- Same board inside the PWA (Cal / Live toggle)

### Report BS

- Monthly Attendance Sheet BS (P / HD / WO / Hol / Lv / Ab / WFH)
- Worked vs target hours, employee hierarchy permissions
- Recalculate C&R and spreadsheet download

### Attendance policy

- Late/early/OOO CNR applications and pool engine
- OOO Work check-ins with GPS path logs and manager include/reject
- Sandwich absents and Attendance Policy Escape
- Bulk late/early recalculation

### Leave

- Default Home / Sick leave types
- Monthly allocation on BS month start
- Sandwich validation on Leave Application
- Draft remaining balance; split leave; cancel own

### Payroll

- SSF and PF & Gratuity salary structures (salary and wages)
- SSA breakdown (Basic, DA, Grade, other allowances)
- Slip deductions: late/early/OOO half-days, unapproved absents, sandwich, LWP gross rules
- Projected TDS / CIT / retirement ceiling
- Scheduled Payroll Entry creation
- Period overrides and minimum wage

### Desk

- Nepal HRMS workspace, dashboards, BS date fields across HR documents
- Role: Attendance Report Viewer

---

## Install

```bash
bench get-app nepal_hrms
bench --site [site] install-app nepal_hrms
bench --site [site] migrate
```

Requires ERPNext, Frappe HR (`hrms`), and Nepal Compliance (`nepal_compliance`) on Frappe v15.

After install: open **Nepal HRMS Settings**, run **Payroll Setup** if you want the bundled structures, assign PWA board roles, and open `/bshrms` as an Employee.

---

## Known limitations

- Pre-1.0: settings defaults and payroll formulas may change
- Installed PWA icons are cached by the browser; remove and re-add the home-screen shortcut after icon changes
- Keep HR/payroll overrides out of `nepal_compliance` (see `docs/upstream-sync.md`)
- Live Attendance desk page name is `live_attendance_boar-1` (legacy page id)
- Monthly Attendance Sheet BS is the BS attendance report; there is no separate BS payroll report DocType

---

## License

GNU GPL v3 or later. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
