const routes = [
	{
		name: "LeaveApplicationListView",
		path: "/leave-applications",
		component: () => import("@/views/leave/List.vue"),
	},
	{
		name: "LeaveApplicationFormView",
		path: "/leave-applications/new",
		component: () => import("@/views/leave/Form.vue"),
	},
	{
		name: "LeaveApplicationDetailView",
		path: "/leave-applications/:id",
		props: true,
		component: () => import("@/views/leave/Form.vue"),
	},
	{
		name: "CompensatoryLeaveRequestFormView",
		path: "/compensatory-leave/new",
		component: () => import("@/views/leave/CompensatoryLeaveForm.vue"),
	},
	{
		name: "CompensatoryLeaveRequestDetailView",
		path: "/compensatory-leave/:id",
		props: true,
		component: () => import("@/views/leave/CompensatoryLeaveForm.vue"),
	},
]

export default routes
