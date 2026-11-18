# Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Comments on a request, read and written from the PWA's request sheet.

They are ordinary Comment records, so the desk form shows the same thread.
A tagged person gets Frappe's own mention notification (desk bell, email) and
a PWA Notification, which is the list the PWA reads.
"""

import frappe
from frappe import _
from frappe.utils import escape_html, get_fullname

from nepal_hrms.api.team_requests import SPECS, _can_decide

COMMENTABLE = (*SPECS.keys(), "Expense Claim")
MAX_COMMENT = 2000
MAX_MENTIONS = 10


def _get_doc(doctype, name):
	if doctype not in COMMENTABLE:
		frappe.throw(_("{0} cannot be commented on from here.").format(doctype))
	doc = frappe.get_doc(doctype, name)
	if _can_see(doc):
		return doc
	frappe.throw(_("Not permitted"), frappe.PermissionError)


def _can_see(doc):
	"""Anyone who can open the request in the sheet: its owner, HR, its approvers."""
	from nepal_hrms.custom_code.approval_authority import is_own

	if frappe.has_permission(doc.doctype, "read", doc=doc):
		return True
	if doc.get("employee") and is_own(doc.employee):
		return True
	return doc.doctype in SPECS and bool(_can_decide(doc))


def _parts(content):
	"""Comment HTML as text and mention parts, so the PWA never renders raw HTML."""
	from bs4 import BeautifulSoup, NavigableString

	soup = BeautifulSoup(content or "", "html.parser")
	for br in soup.find_all("br"):
		br.replace_with("\n")
	for block in soup.find_all(["p", "div"]):
		block.append("\n")

	parts = []

	def walk(node):
		for child in node.children:
			if isinstance(child, NavigableString):
				if str(child):
					parts.append({"text": str(child)})
			elif "mention" in (child.get("class") or []):
				label = child.get("data-value") or child.get_text().lstrip("@")
				parts.append({"mention": label, "user": child.get("data-id")})
			else:
				walk(child)

	walk(soup)
	if parts and "text" in parts[-1]:
		parts[-1]["text"] = parts[-1]["text"].rstrip()
	return [p for p in parts if p.get("mention") or p.get("text")]


def attach_comment_counts(rows):
	"""Set comment_count on each {doctype, name} row: one grouped query per doctype."""
	by_doctype = {}
	for row in rows:
		if row.get("doctype") and row.get("name"):
			by_doctype.setdefault(row["doctype"], []).append(row["name"])
	counts = {}
	for doctype, names in by_doctype.items():
		for name, count in frappe.get_all(
			"Comment",
			filters={
				"comment_type": "Comment",
				"reference_doctype": doctype,
				"reference_name": ["in", names],
			},
			# v16 rejects SQL functions written as strings in get_all fields
			fields=["reference_name", {"COUNT": "name", "as": "n"}],
			group_by="reference_name",
			as_list=True,
		):
			counts[(doctype, name)] = count
	for row in rows:
		row["comment_count"] = counts.get((row.get("doctype"), row.get("name")), 0)
	return rows


@frappe.whitelist()
def get_comment_counts(requests):
	"""Counts for rows that come from stock HRMS lists (Expense Claims)."""
	rows = [
		{"doctype": r.get("doctype"), "name": r.get("name")}
		for r in (frappe.parse_json(requests) or [])[:100]
		if r.get("doctype") in COMMENTABLE
		and frappe.has_permission(r.get("doctype"), "read", doc=r.get("name"))
	]
	return {f"{r['doctype']}::{r['name']}": r["comment_count"] for r in attach_comment_counts(rows)}


@frappe.whitelist()
def get_request_comments(doctype, name):
	doc = _get_doc(doctype, name)
	comments = frappe.get_all(
		"Comment",
		filters={
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			"comment_type": "Comment",
		},
		fields=["name", "comment_email", "comment_by", "content", "creation"],
		order_by="creation asc",
	)
	return [
		{
			"name": c.name,
			"user": c.comment_email,
			"full_name": c.comment_by or get_fullname(c.comment_email),
			"creation": c.creation,
			"parts": _parts(c.content),
		}
		for c in comments
	]


@frappe.whitelist(methods=["POST"])
def add_request_comment(doctype, name, content, mentions=None):
	"""Add a comment. mentions: [{"user", "name"}]; each "@name" in the text becomes a tag."""
	doc = _get_doc(doctype, name)
	content = (content or "").strip()
	if not content:
		frappe.throw(_("Comment cannot be empty."))
	if len(content) > MAX_COMMENT:
		frappe.throw(_("Keep the comment under {0} characters.").format(MAX_COMMENT))

	html = escape_html(content)
	tagged = []
	requested = (frappe.parse_json(mentions) or [])[:MAX_MENTIONS]
	# Longest name first, so "@Ram" never claims the start of "@Ram Bahadur".
	requested.sort(key=lambda m: len((m or {}).get("name") or ""), reverse=True)
	for mention in requested:
		user = (mention or {}).get("user")
		if not user or user in tagged or not frappe.db.get_value("User", user, "enabled"):
			continue
		label = get_fullname(user)
		token = escape_html(f"@{(mention.get('name') or label).strip()}")
		if token not in html:
			continue
		span = (
			f'<span class="mention" data-id="{escape_html(user)}" '
			f'data-value="{escape_html(label)}" data-denotation-char="@">@{escape_html(label)}</span>'
		)
		html = html.replace(token, span, 1)
		tagged.append(user)

	comment = frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Comment",
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			"comment_email": frappe.session.user,
			"comment_by": get_fullname(frappe.session.user),
			"content": html.replace("\n", "<br>"),
		}
	)
	# The desk mention notification comes from Comment itself (notify_mentions).
	comment.insert(ignore_permissions=True)
	_share_with_tagged(doc, tagged)
	_notify_tagged(doc, tagged, content)
	return {"name": comment.name, "tagged": tagged}


def _share_with_tagged(doc, users):
	"""Tagging asks for someone's input, so they must be able to open the request.

	Read-only, and only for those who cannot already see it.
	"""
	from frappe.share import add_docshare

	for user in users:
		if frappe.has_permission(doc.doctype, "read", doc=doc, user=user):
			continue
		add_docshare(doc.doctype, doc.name, user, read=1, flags={"ignore_share_permission": True})


def _notify_tagged(doc, users, content):
	sender = frappe.session.user
	snippet = content if len(content) <= 120 else content[:117] + "..."
	message = _("<b>{0}</b> mentioned you on {1} of {2}: {3}").format(
		escape_html(get_fullname(sender)),
		_(doc.doctype),
		escape_html(doc.get("employee_name") or doc.name),
		escape_html(snippet),
	)
	for user in users:
		if user == sender:
			continue
		try:
			frappe.get_doc(
				{
					"doctype": "PWA Notification",
					"from_user": sender,
					"to_user": user,
					"message": message,
					"reference_document_type": doc.doctype,
					"reference_document_name": doc.name,
				}
			).insert(ignore_permissions=True)
		except Exception:
			# A failed push must not lose the comment that was just written.
			frappe.log_error(frappe.get_traceback(), "Nepal request comment notification failed")
