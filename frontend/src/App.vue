<script setup lang="ts">
import { RouterView, useRoute } from "vue-router";
import { IcToastHost } from "@/design/components";
import AppShell from "@/app/AppShell.vue";

const route = useRoute();
</script>

<template>
	<!-- The showcase is a full-page document of its own; everything else lives in the shell. -->
	<RouterView v-if="route.name === 'design'" />
	<AppShell v-else />
	<IcToastHost />
</template>
