# Nepal HRMS

Nepali HR and Payroll for Frappe HR: Bikram Sambat dates, attendance policy (late/early/OOO), Nepal payroll, and the **BS HRMS** employee PWA at `/bshrms`.

## Dependencies

Install in this order:

1. ERPNext
2. Frappe HR (`hrms`)
3. Nepal Compliance (`nepal_compliance`) — shared AD↔BS date libraries
4. Nepal HRMS (`nepal_hrms`)

## Apps screen

The **BS HRMS** tile opens `/bshrms`. Desk calendar widgets continue to load from Nepal Compliance public assets.

## Pulling Nepal Compliance

Keep HR/payroll overrides in this app only. After merging upstream `nepal-compliance`, drop any payroll/HR files that land in `nepal_compliance` so both apps do not override the same DocTypes. See [docs/upstream-sync.md](docs/upstream-sync.md).
