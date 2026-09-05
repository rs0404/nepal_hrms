import { createResource } from "frappe-ui"

export const recentlyApprovedTeamRequests = createResource({
	url: "nepal_hrms.api.request_dashboard.get_recently_approved_team_requests",
	params: { limit: 20 },
	auto: true,
	cache: "nepal_hrms:recently_approved_team_requests",
	transform(data) {
		return data || []
	},
})
