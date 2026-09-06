import { createApp } from "vue"
import App from "./App.vue"
import router from "./router"
import { initSocket } from "./socket"

import {
	Button,
	Input,
	setConfig,
	frappeRequest,
	resourcesPlugin,
	FormControl,
} from "frappe-ui"
import { translationsPlugin } from "./plugins/translationsPlugin.js"
import EmptyState from "@/components/EmptyState.vue"

import { IonicVue } from "@ionic/vue"

import { session } from "@/data/session"
import { userResource } from "@/data/user"
import { employeeResource } from "@/data/employee"

import dayjs from "@/utils/dayjs"
import getIonicConfig from "@/utils/ionicConfig"
import {
	identityMatches,
	syncCsrfFromCookie,
	waitForResourceData,
} from "@/utils/startup"

import FrappePushNotification from "../public/frappe-push-notification"

/* Core CSS required for Ionic components to work properly */
import "@ionic/vue/css/core.css"

/* Theme variables */
import "./theme/variables.css"

import "./main.css"

syncCsrfFromCookie()

const app = createApp(App)
const socket = createLazySocket()

setConfig("resourceFetcher", frappeRequest)
app.use(resourcesPlugin)
app.use(translationsPlugin)

app.component("Button", Button)
app.component("Input", Input)
app.component("FormControl", FormControl)
app.component("EmptyState", EmptyState)

app.use(router)
app.use(IonicVue, getIonicConfig())

if (session?.isLoggedIn && !employeeResource?.data) {
	employeeResource.reload()
}

app.provide("$session", session)
app.provide("$user", userResource)
app.provide("$employee", employeeResource)
app.provide("$socket", socket)
app.provide("$dayjs", dayjs)

const BSHRMS_SW = "/assets/nepal_hrms/bshrms/sw.js"

function createLazySocket() {
	let real = null
	const queue = []
	const api = {
		emit(...args) {
			if (!real) {
				queue.push(["emit", args])
				return api
			}
			return real.emit(...args)
		},
		on(...args) {
			if (!real) {
				queue.push(["on", args])
				return api
			}
			return real.on(...args)
		},
		off(...args) {
			if (!real) {
				for (let i = queue.length - 1; i >= 0; i--) {
					if (queue[i][0] === "on" && queue[i][1][0] === args[0]) {
						queue.splice(i, 1)
					}
				}
				return api
			}
			return real.off(...args)
		},
		__start() {
			if (real) return real
			real = initSocket()
			for (const [method, args] of queue) {
				real[method](...args)
			}
			queue.length = 0
			return real
		},
	}
	return api
}

function startSocketWhenIdle() {
	const start = () => socket.__start()
	if ("requestIdleCallback" in window) {
		window.requestIdleCallback(start, { timeout: 1500 })
	} else {
		setTimeout(start, 400)
	}
}

const registerServiceWorker = async () => {
	window.frappePushNotification = new FrappePushNotification("hrms")

	if (!("serviceWorker" in navigator)) {
		console.error("Service worker not enabled/supported by the browser")
		return
	}

	try {
		const registrations = await navigator.serviceWorker.getRegistrations()
		await Promise.all(
			registrations
				.filter((reg) =>
					reg.active?.scriptURL?.includes("/assets/hrms/frontend/sw.js")
				)
				.map((reg) => reg.unregister())
		)
	} catch (err) {
		console.error("Failed to unregister HRMS service worker", err)
	}

	try {
		const registration = await navigator.serviceWorker.register(BSHRMS_SW, {
			type: "classic",
		})

		if (!window.frappe?.boot?.push_relay_server_url) return

		window.frappePushNotification
			.fetchWebConfig()
			.then((config) => {
				const url = `${BSHRMS_SW}?config=${encodeURIComponent(
					JSON.stringify(config)
				)}`
				return navigator.serviceWorker
					.register(url, { type: "classic" })
					.then((reg) => window.frappePushNotification.initialize(reg))
			})
			.catch((err) => console.error("Failed to fetch FCM config", err))

		return registration
	} catch (err) {
		console.error("Failed to register service worker", err)
	}
}

function refreshIdentityInBackground() {
	userResource.reload().catch((error) => {
		if (error?.exc_type === "AuthenticationError") {
			session.user = null
			router.replace({ name: "Login" })
		}
	})
	employeeResource.reload()
}

router.isReady().then(async () => {
	if (import.meta.env.DEV) {
		await frappeRequest({
			url: "/api/method/hrms.www.hrms.get_context_for_dev",
		}).then(async (values) => {
			if (!window.frappe) window.frappe = {}
			window.frappe.boot = values
		})
	}

	if (window.frappe?.boot?.__messages) {
		await translationsPlugin.isReady()
	} else {
		translationsPlugin.isReady()
	}

	app.mount("#app")
	registerServiceWorker()
	startSocketWhenIdle()
})

router.beforeEach(async (to, _, next) => {
	let isLoggedIn = session.isLoggedIn

	if (isLoggedIn) {
		await Promise.all([
			waitForResourceData(userResource),
			waitForResourceData(employeeResource),
		])

		if (identityMatches(userResource, employeeResource)) {
			refreshIdentityInBackground()
			if (to.name === "Login") {
				return next({ name: "Home" })
			}
			return next()
		}

		try {
			await userResource.reload()
		} catch (error) {
			isLoggedIn = false
		}
	}

	if (!isLoggedIn) {
		// password reset page is outside the PWA scope
		if (to.path === "/update-password") {
			return next(false)
		} else if (to.name !== "Login") {
			next({ name: "Login" })
		} else {
			next()
		}
		return
	}

	if (to.name !== "InvalidEmployee") {
		if (!employeeResource.promise) employeeResource.reload()
		await employeeResource.promise
		if (
			!employeeResource?.data ||
			employeeResource?.data?.user_id !== userResource.data.name
		) {
			next({ name: "InvalidEmployee" })
		} else if (to.name === "Login") {
			next({ name: "Home" })
		} else {
			next()
		}
	} else {
		next()
	}
})
