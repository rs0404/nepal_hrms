# Nepal HRMS: Developer notes

BS HRMS is the employee PWA at `/bshrms`. Backend HR/payroll lives in this app. Shared AD↔BS conversion stays in `nepal_compliance`.

## PWA

- Source: `bshrms/`
- Build: `cd apps/nepal_hrms/bshrms && yarn build` (base `/assets/nepal_hrms/bshrms/`)
- Entry: `nepal_hrms/www/bshrms.html`
- Calendar JS/CSS still load from `/assets/nepal_compliance/js|css/`

## Settings

Use **Nepal HRMS Settings** for late/early/OOO/sandwich/LWP. Nepali date enablement remains on **Nepal Compliance Settings**.

## Upstream sync

See [upstream-sync.md](upstream-sync.md).
