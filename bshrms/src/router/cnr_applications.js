const form = () => import("@/views/cnr/CnrApplicationForm.vue")
const list = () => import("@/views/cnr/CnrApplicationList.vue")

const routes = [
	{
		name: "LateEntryApplicationListView",
		path: "/late-entry-applications",
		component: list,
	},
	{
		name: "LateEntryApplicationFormView",
		path: "/late-entry-applications/new",
		component: form,
	},
	{
		name: "LateEntryApplicationDetailView",
		path: "/late-entry-applications/:id",
		props: true,
		component: form,
	},
	{
		name: "EarlyExitApplicationListView",
		path: "/early-exit-applications",
		component: list,
	},
	{
		name: "EarlyExitApplicationFormView",
		path: "/early-exit-applications/new",
		component: form,
	},
	{
		name: "EarlyExitApplicationDetailView",
		path: "/early-exit-applications/:id",
		props: true,
		component: form,
	},
	{
		name: "OutOfOfficeApplicationListView",
		path: "/out-of-office-applications",
		component: list,
	},
	{
		name: "OutOfOfficeApplicationFormView",
		path: "/out-of-office-applications/new",
		component: form,
	},
	{
		name: "OutOfOfficeApplicationDetailView",
		path: "/out-of-office-applications/:id",
		props: true,
		component: form,
	},
]

export default routes
