# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Re-raise the accrual Journal Entry for a submitted Payroll Entry.

Stock HRMS posts the accrual JV exactly once, from inside the background job
that submits the salary slips. If that JV is later cancelled -- to correct a
component's expense account, say -- nothing brings it back: the only route
stock offers is cancelling the whole Payroll Entry and re-running payroll.

Re-raising is safe, because the slips are the bookkeeping. Cancelling a Journal
Entry clears `journal_entry` on every salary slip it covered (hrms unlinks them
on cancel), and `PayrollEntry.get_sal_slip_list` only picks up slips whose
`journal_entry` is empty. So slips a cancelled JV covered become eligible
again, and slips a live JV holds never are -- which is also what stops this
double-posting.

Accrual entries are told apart from the payment side by voucher type: the
accrual is a plain "Journal Entry" while bank and cash payments are "Bank
Entry" and "Cash Entry" (the same split stock uses in has_bank_entries).
"""

import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.utils import get_link_to_form

ACCRUAL_VOUCHER_TYPE = "Journal Entry"

# ERPNext refuses a journal row on one of these without a party.
PARTY_TRACKED_ACCOUNT_TYPES = ("Receivable", "Payable")

# Marks a deduction that needs an employee on its journal row but has no
# Employee Advance document to reference.
PARTY_ONLY_DEDUCTION = "__party_only__"


def is_party_tracked_component(company, salary_component):
	"""Does this component post to an account ERPNext demands a party on?"""
	account = frappe.db.get_value(
		"Salary Component Account",
		{"parent": salary_component, "company": company},
		"account",
		cache=True,
	)
	if not account:
		# Stock throws about the missing account further down; not our business here.
		return False

	return frappe.get_cached_value("Account", account, "account_type") in PARTY_TRACKED_ACCOUNT_TYPES


def partition_advance_entries(entries):
	"""Split rows that reference an Employee Advance from those that only carry a party."""
	linked = [e for e in entries if e.get("reference_name")]
	unlinked = [e for e in entries if not e.get("reference_name")]
	return linked, unlinked


def get_accrual_journal_entries(payroll_entry):
	"""Every accrual JV ever raised against this Payroll Entry, newest first."""
	je = frappe.qb.DocType("Journal Entry")
	jea = frappe.qb.DocType("Journal Entry Account")

	return (
		frappe.qb.from_(je)
		.inner_join(jea)
		.on(je.name == jea.parent)
		.select(je.name, je.docstatus, je.posting_date, je.total_debit)
		.distinct()
		.where(
			(jea.reference_type == "Payroll Entry")
			& (jea.reference_name == payroll_entry)
			& (je.voucher_type == ACCRUAL_VOUCHER_TYPE)
		)
		.orderby(je.creation, order=Order.desc)
	).run(as_dict=True)


def summarize(entries, docstatus, pending_slips):
	"""Decide whether the button should be offered. Kept free of the database
	so the rule can be read -- and tested -- on its own."""
	posted = [e["name"] for e in entries if e["docstatus"] == 1]
	cancelled = [e["name"] for e in entries if e["docstatus"] == 2]

	return {
		"posted": posted,
		"cancelled": cancelled,
		"pending_slips": pending_slips,
		# A live accrual JV, or nothing left to accrue, means there is nothing to do.
		"can_create": bool(docstatus == 1 and not posted and pending_slips),
	}


def get_status(doc):
	"""What the Payroll Entry form needs to decide whether to show the button."""
	pending = len(doc.get_sal_slip_list(ss_status=1)) if doc.docstatus == 1 else 0
	return summarize(get_accrual_journal_entries(doc.name), doc.docstatus, pending)


def create(doc):
	"""Post the accrual JV for whatever submitted slips are still unaccrued."""
	doc.check_permission("write")

	if doc.docstatus != 1:
		frappe.throw(_("Submit this Payroll Entry before creating its accrual Journal Entry."))

	existing = get_accrual_journal_entries(doc.name)
	posted = [e.name for e in existing if e.docstatus == 1]
	if posted:
		frappe.throw(
			_("{0} is already posted against this Payroll Entry. Cancel it first to raise a new one.").format(
				get_link_to_form("Journal Entry", posted[0])
			)
		)

	slips = doc.get_sal_slip_list(ss_status=1, as_dict=True)
	if not slips:
		frappe.throw(
			_("No submitted salary slip on this Payroll Entry is waiting for an accrual entry.")
		)

	before = {e.name for e in existing}
	doc.make_accrual_jv_entry(slips)
	created = [e.name for e in get_accrual_journal_entries(doc.name) if e.name not in before]

	return {"journal_entry": created[0] if created else None, "slips": len(slips)}
