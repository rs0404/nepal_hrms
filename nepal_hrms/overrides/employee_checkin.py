import frappe
from hrms.hr.doctype.employee_checkin.employee_checkin import EmployeeCheckin

class CustomEmployeeCheckin(EmployeeCheckin):
	def validate_distance_from_shift_location(self):
		# Bypass geofencing if custom_attendance_type is 'OOO Work'
		if getattr(self, "custom_attendance_type", None) == "OOO Work":
			# Only require lat/long on Check-In, not Check-Out, and allow 0.0 coordinates
			if self.log_type == "IN" and (self.latitude is None or self.longitude is None):
				frappe.throw(frappe._("Latitude and longitude values are required for checking in."))
			return
		
		# Otherwise, use the original validation logic
		return super().validate_distance_from_shift_location()
