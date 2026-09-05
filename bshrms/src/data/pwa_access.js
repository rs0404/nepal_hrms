import { createResource } from "frappe-ui"

export const pwaAccess = createResource({
	url: "nepal_hrms.api.pwa_access.get_pwa_access_permissions",
	auto: true,
	cache: "nepal_hrms:pwa_access",
	transform(data) {
		return data || {}
	},
})
