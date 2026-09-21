"""Re-pull a draft Salary Slip's absence figures from submitted Attendance.

Payroll Settings.payroll_based_on = "Leave" makes HRMS ignore Attendance rows
entirely, so a slip saved before attendance was marked (or before a C&R
recalculation rewrote it) keeps absent_days = 0 while the calendar says
otherwise. This syncs the slip to what Attendance currently holds.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt


# What changed materially. absent_days is HRMS's internal bucket: it holds genuine
# absence AND every C&R penalty, which is why it is not what we show anyone.
SYNC_FIELDS = ("absent_days", "payment_days", "leave_without_pay", "net_pay")

# What a payroll officer reads, in the same words the Monthly Attendance Sheet BS
# uses: penalties on their own line, absence meaning only genuine absence.
REPORT_FIELDS = (
	"custom_penalty_days",
	"custom_unapproved_absent_days",
	"leave_without_pay",
	"custom_paid_leave_days",
	"net_pay",
)


def _attendance_absent_days(doc):
	"""Absent days Attendance currently implies, whatever payroll_based_on says.

	Mirrors what HRMS counts in its "Attendance" mode: full Absent rows, plus the
	unpaid half of a Half Day. That second part is where C&R penalties land -- a ½P
	or a major delay is a Half Day whose other half is Absent -- so leaving it out
	would sync a slip that still under-reports every penalty.
	"""
	settings = frappe.get_single("Payroll Settings")
	half_day_units = flt(settings.daily_wages_fraction_for_half_day) or 0.5
	consider_on_holidays = cint(settings.consider_marked_attendance_on_holidays)

	# Both HRMS helpers read self.start_date, so the BS tail extension has to be in
	# force here too or the sync would disagree with the slip it just recalculated.
	with doc._bs_extended_period():
		holidays = doc.get_holidays_for_employee(doc.start_date, doc.end_date)
		_lwp, absent = doc.calculate_lwp_ppl_and_absent_days_based_on_attendance(
			holidays, half_day_units, consider_on_holidays
		)
		half_absent = doc.get_half_absent_days(consider_on_holidays, holidays)
	return flt(absent) + flt(half_absent) * half_day_units


def _snapshot(doc):
	fields = set(SYNC_FIELDS) | set(REPORT_FIELDS)
	return {field: flt(doc.get(field)) for field in sorted(fields)}


def seed_absence_from_attendance(doc):
	"""Put attendance-derived absence on the slip, ready to be calculated.

	Shared by the Sync with Attendance button and by slip creation, so a slip made
	from a Payroll Entry starts from the same figures the button would give it.
	"""
	absent = _attendance_absent_days(doc)
	doc.absent_days = absent
	# The slip narrows absent_days to genuine absence and reports penalties on their
	# own line, so the full bucket has to be handed over explicitly or the recompute
	# reads a stale zero and sheds every penalty.
	if doc.meta.has_field("custom_total_unpaid_days"):
		doc.custom_total_unpaid_days = absent
	if doc.meta.has_field("custom_absent_days_manual"):
		doc.custom_absent_days_manual = 1
	doc.flags.use_manual_absent_days = 1
	# Tells apply_manual_absent_days this figure came from Attendance, not a human.
	doc.flags.absent_days_from_attendance = 1
	return absent


def sync_slip(doc, save=True):
	"""Apply attendance-derived absence to one slip. Returns a result row."""
	row = {
		"name": doc.name,
		"employee": doc.employee,
		"employee_name": doc.employee_name,
		"before": _snapshot(doc),
	}

	absent = seed_absence_from_attendance(doc)

	# No lwp argument on purpose. HRMS keeps whatever non-zero figure it is handed
	# (`if not lwp: lwp = actual_lwp`), so passing the stored one pins a stale value
	# forever -- exactly what a sync exists to correct.
	doc.get_working_days_details()
	doc.calculate_net_pay()

	row["attendance_absent_days"] = absent
	row["after"] = _snapshot(doc)
	row["changed"] = any(
		abs(row["before"][f] - row["after"][f]) > 1e-9 for f in SYNC_FIELDS
	)

	if save and row["changed"]:
		doc.save()

	return row


@frappe.whitelist()
def sync_with_attendance(slips, dry_run=0):
	"""Sync one or more draft Salary Slips with submitted Attendance.

	slips: a slip name, or a JSON list of names (list view selection).
	dry_run: compute and report without writing.
	"""
	if isinstance(slips, str):
		try:
			slips = json.loads(slips)
		except (ValueError, TypeError):
			slips = [slips]
	if not isinstance(slips, (list, tuple)):
		slips = [slips]

	names = [n for n in (str(s).strip() for s in slips) if n]
	if not names:
		frappe.throw(_("Select at least one Salary Slip."))

	dry_run = cint(dry_run)
	results = []
	skipped = []

	for name in names:
		if not frappe.has_permission("Salary Slip", "write", doc=name):
			skipped.append({"name": name, "reason": _("No write permission")})
			continue

		doc = frappe.get_doc("Salary Slip", name)
		if doc.docstatus != 0:
			skipped.append({"name": name, "reason": _("Only draft slips can be synced")})
			continue

		try:
			results.append(sync_slip(doc, save=not dry_run))
		except Exception:
			frappe.log_error(
				title="Salary Slip attendance sync failed",
				message=f"{name}\n{frappe.get_traceback()}",
			)
			skipped.append({"name": name, "reason": _("Sync failed; see Error Log")})

	if dry_run:
		frappe.db.rollback()

	changed = [r for r in results if r["changed"]]
	return {
		"dry_run": dry_run,
		"total": len(names),
		"synced": len(changed),
		"unchanged": len(results) - len(changed),
		"results": results,
		"skipped": skipped,
	}
