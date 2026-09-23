"""Nepal's employee tax exemption categories, created by payroll setup.

FY 2083/84 limits, each the most an employee may declare in the year:

  Life insurance premium              Rs 40,000
  Health insurance premium            Rs 20,000
  Private building insurance premium  Rs 10,000
  Children's education fee            Rs 25,000   (or 25% of tuition, if lower)
  Donation to a tax-exempt body       Rs 3,00,000 (or 5% of adjusted taxable
                                                   income, if lower)

Frappe HR enforces only the fixed amount. The percentage caps have to be checked
by whoever approves the proof.

Not here on purpose: approved retirement contributions (SSF, PF, CIT) are
already capped from the salary components by retirement_tax.py, so a category
would count them twice; the female and medical tax credits reduce tax, not
income, which this doctype cannot express.
"""

import frappe

# category: (category max, [(sub-category, sub-category max)])
TAX_EXEMPTION_CATEGORIES = {
	"Life Insurance": (40000, [("Life Insurance Premium", 40000)]),
	"Health Insurance": (20000, [("Health Insurance", 20000)]),
	"Private Building Insurance": (10000, [("Private Building Insurance Premium", 10000)]),
	"Children's Education Fee": (25000, [("Children's Education Fee", 25000)]),
	"Donation": (300000, [("Donation to Tax-Exempt Organisation", 300000)]),
}


def _upsert(doctype, name, values):
	if frappe.db.exists(doctype, name):
		doc = frappe.get_doc(doctype, name)
		changed = {key: value for key, value in values.items() if doc.get(key) != value}
		if not changed:
			return "unchanged"
		doc.update(changed)
		doc.save(ignore_permissions=True)
		return "updated"
	doc = frappe.new_doc(doctype)
	doc.update(values)
	doc.insert(ignore_permissions=True, set_name=name)
	return "created"


def ensure_tax_exemption_categories():
	"""Create the categories, or bring their limits back to the statutory ones.

	The category goes first: a sub-category links to it.
	"""
	log = []
	for category, (category_max, subs) in TAX_EXEMPTION_CATEGORIES.items():
		action = _upsert(
			"Employee Tax Exemption Category",
			category,
			{"max_amount": category_max, "is_active": 1},
		)
		log.append({"name": category, "action": action})
		for sub, sub_max in subs:
			action = _upsert(
				"Employee Tax Exemption Sub Category",
				sub,
				{"exemption_category": category, "max_amount": sub_max, "is_active": 1},
			)
			log.append({"name": sub, "action": action})
	return log
