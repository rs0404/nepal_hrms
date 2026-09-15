import frappe


def get_boot_info(bootinfo):
	if frappe.session.user == "Guest":
		return

	has_raven = False
	try:
		from nepal_hrms.notifications.raven_guard import raven_available

		has_raven = raven_available()
	except Exception:
		has_raven = False

	try:
		from nepal_hrms.custom_code.attendance_policy import get_hr_settings

		settings = get_hr_settings()
		bootinfo["nepal_hrms"] = {
			"enable_late_early_penalty": bool(settings.get("enable_late_early_penalty")),
			"use_nepali_date_in_attendance": bool(settings.get("use_nepali_date_in_attendance")),
			"has_raven": has_raven,
		}
	except Exception:
		bootinfo["nepal_hrms"] = {"has_raven": has_raven}
