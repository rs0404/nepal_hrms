<template>
	<ion-page>
		<ion-header class="ion-no-border">
			<div class="w-full sm:w-96">
				<div class="flex flex-col bg-white shadow-sm p-4">
					<div class="flex flex-row justify-between items-center">
						<div class="flex flex-row items-center gap-2 min-w-0">
							<img
								v-if="!props.pageTitle"
								:src="APP_ICON"
								alt=""
								class="h-8 w-8 shrink-0 rounded-lg ring-1 ring-gray-200"
							/>
							<h2 class="text-xl font-bold tracking-wide text-gray-900 truncate">
								{{ props.pageTitle || __("NEPAL HRMS") }}
							</h2>
							<slot name="header-extra"></slot>
						</div>
						<div class="flex flex-row items-center gap-3 ml-auto shrink-0">
							<router-link
								:to="{ name: 'Notifications' }"
								v-slot="{ navigate }"
								class="flex flex-col items-center"
							>
								<span class="relative inline-block" @click="navigate">
									<FeatherIcon 
										name="bell" 
										class="h-6 w-6 text-gray-600" 
										style="height: 24px; width: 24px;"
									/>
									<span
										v-if="unreadNotificationsCount.data"
										class="absolute top-0 right-0.5 inline-block w-2 h-2 bg-red-600 rounded-full border border-white"
									>
									</span>
								</span>
							</router-link>
							<router-link
								:to="{ name: 'Profile' }"
								class="flex flex-col items-center"
							>
								<Avatar
									:image="user.data.user_image"
									:label="user.data.first_name"
									size="xl"
								/>
							</router-link>
						</div>
					</div>
				</div>
			</div>
		</ion-header>

		<ion-content class="ion-no-padding">
			<ion-refresher slot="fixed" @ionRefresh="onPullRefresh">
				<ion-refresher-content></ion-refresher-content>
			</ion-refresher>
			<!-- Re-keyed on refresh so the page's own resources load again too. -->
			<div :key="refreshKey" class="flex flex-col h-screen w-screen sm:w-96">
				<slot name="body"></slot>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
// Bound, not a literal src: Vite would try to bundle a literal /assets path.
const APP_ICON = "/assets/nepal_hrms/icon/app-icon.svg"

import {
	IonHeader,
	IonContent,
	IonPage,
	IonRefresher,
	IonRefresherContent,
	onIonViewWillEnter,
} from "@ionic/vue"
import { FeatherIcon, Avatar } from "frappe-ui"

import { unreadNotificationsCount } from "@/data/notifications"

import { inject, ref } from "vue"

import { reloadLoadedResources } from "@/utils/pull_refresh"

const user = inject("$user")
const emit = defineEmits(["viewWillEnter"])

const props = defineProps({
	pageTitle: {
		type: String,
		required: false,
		default: "",
	},
})

onIonViewWillEnter(() => emit("viewWillEnter"))

const refreshKey = ref(0)

async function onPullRefresh(event) {
	try {
		await reloadLoadedResources()
		refreshKey.value += 1
		emit("viewWillEnter")
	} finally {
		event.target.complete()
	}
}
</script>
