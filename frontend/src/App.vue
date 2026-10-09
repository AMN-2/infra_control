<script setup lang="ts">
import { RouterView, useRoute } from "vue-router";
import { IcToastHost } from "@/design/components";
import AppShell from "@/app/AppShell.vue";
import CinematicStage from "@/features/login/CinematicStage.vue";
import { useLoginController } from "@/features/login/useLoginTransition";

const route = useRoute();
const login = useLoginController();
</script>

<template>
	<!-- The showcase and the login are full-page documents of their own; everything else lives in the shell. -->
	<RouterView v-if="route.name === 'design' || route.name === 'login'" />
	<AppShell v-else />
	<!-- Outside the router view so the success film survives the route change into the dashboard. -->
	<CinematicStage v-if="route.name === 'login' || login.state.stageActive" />
	<IcToastHost />
</template>
