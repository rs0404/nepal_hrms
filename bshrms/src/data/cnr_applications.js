import { createResource } from "frappe-ui"
import { employeeResource } from "./employee"

const CNR_DOCTYPES = [
	"Late Entry Application",
	"Early Exit Application",
	"Out of Office Application",
]

function makeMyResource(doctype, cacheKey) {
	return createResource({
		url: "nepal_hrms.api.cnr_applications.get_cnr_applications",
		params: {
			doctype,
			employee: employeeResource.data?.name,
			limit: 10,
		},
		auto: true,
		cache: cacheKey,
		transform(data) {
			return (data || []).map((row) => {
				row.doctype = doctype
				return row
			})
		},
	})
}

function makeTeamResource(doctype, cacheKey) {
	return createResource({
		url: "nepal_hrms.api.cnr_applications.get_cnr_applications",
		params: {
			doctype,
			for_approval: 1,
			limit: 10,
		},
		auto: true,
		cache: cacheKey,
		transform(data) {
			return (data || []).map((row) => {
				row.doctype = doctype
				return row
			})
		},
	})
}

export const myLateEntryApplications = makeMyResource(
	"Late Entry Application",
	"nepal_hrms:my_late_entry_apps"
)
export const myEarlyExitApplications = makeMyResource(
	"Early Exit Application",
	"nepal_hrms:my_early_exit_apps"
)
export const myOutOfOfficeApplications = makeMyResource(
	"Out of Office Application",
	"nepal_hrms:my_ooo_apps"
)

export const teamLateEntryApplications = makeTeamResource(
	"Late Entry Application",
	"nepal_hrms:team_late_entry_apps"
)
export const teamEarlyExitApplications = makeTeamResource(
	"Early Exit Application",
	"nepal_hrms:team_early_exit_apps"
)
export const teamOutOfOfficeApplications = makeTeamResource(
	"Out of Office Application",
	"nepal_hrms:team_ooo_apps"
)

export function reloadAllCnrApplications() {
	;[
		myLateEntryApplications,
		myEarlyExitApplications,
		myOutOfOfficeApplications,
		teamLateEntryApplications,
		teamEarlyExitApplications,
		teamOutOfOfficeApplications,
	].forEach((r) => r.reload())
}

export { CNR_DOCTYPES }
