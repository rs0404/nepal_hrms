// Copyright (c) 2026, Yarsa Labs Pvt. Ltd. and contributors
// For license information, please see license.txt

// Turning device push on and off, in one place so the Profile toggle and the
// Settings page cannot drift apart.
//
// enableNotification() calls Notification.requestPermission() itself, so the
// browser prompt appears on its own the first time. What it cannot do is show
// that prompt again once the browser has stored a denial -- requestPermission()
// then resolves "denied" without asking anybody. That case needs saying out
// loud, because the switch otherwise just snaps back with no explanation.

import { computed, ref } from "vue"

import { arePushNotificationsEnabled } from "@/data/notifications"

const enabled = ref(Boolean(window.frappePushNotification?.isNotificationEnabled()))
const busy = ref(false)

function browserPermission() {
	if (typeof Notification === "undefined") return "unsupported"
	return Notification.permission
}

export function usePushNotifications(__) {
	const translate = __ || ((text) => text)

	if (!arePushNotificationsEnabled.data) arePushNotificationsEnabled.reload()

	// The site has to be set up for push before any of this means anything.
	const siteSupportsPush = computed(() =>
		Boolean(
			window.frappe?.boot?.push_relay_server_url && arePushNotificationsEnabled.data
		)
	)

	const blockedByBrowser = computed(
		() => !enabled.value && browserPermission() === "denied"
	)

	const unavailableReason = computed(() => {
		if (browserPermission() === "unsupported") {
			return translate("This browser does not support notifications")
		}
		if (!siteSupportsPush.value) {
			return translate("Push notifications have been disabled on your site")
		}
		if (blockedByBrowser.value) {
			return translate(
				"Notifications are blocked for this site. Allow them in your browser settings, then try again."
			)
		}
		return ""
	})

	// Blocked is deliberately still tappable: the message above is the only way
	// the employee learns why nothing happens, and it cannot be hovered.
	const disabled = computed(
		() => busy.value || browserPermission() === "unsupported" || !siteSupportsPush.value
	)

	async function setEnabled(next) {
		if (busy.value) return { ok: false }

		if (!siteSupportsPush.value) {
			return { ok: false, message: unavailableReason.value }
		}

		busy.value = true
		try {
			if (!next) {
				await window.frappePushNotification.disableNotification()
				enabled.value = false
				return { ok: true, message: translate("Push notifications disabled") }
			}

			// Shows the browser prompt when the permission has never been answered.
			const data = await window.frappePushNotification.enableNotification()
			enabled.value = Boolean(data?.permission_granted)

			if (enabled.value) {
				return { ok: true, message: translate("Push notifications enabled") }
			}
			return {
				ok: false,
				message:
					browserPermission() === "denied"
						? translate(
								"Notifications are blocked for this site. Allow them in your browser settings, then try again."
						  )
						: translate("Push Notification permission denied"),
			}
		} catch (error) {
			enabled.value = Boolean(window.frappePushNotification?.isNotificationEnabled())
			return { ok: false, message: error?.message || translate("Something went wrong") }
		} finally {
			busy.value = false
		}
	}

	return {
		enabled,
		busy,
		disabled,
		siteSupportsPush,
		blockedByBrowser,
		unavailableReason,
		setEnabled,
	}
}
