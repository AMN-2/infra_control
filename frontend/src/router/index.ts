import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

/** The SPA is served at /infra (plan §2). Every feature route is lazy-loaded (plan §10.4). */
export const routes: RouteRecordRaw[] = [
	{
		path: "/",
		name: "home",
		component: () => import("@/features/home/HomeView.vue"),
	},
];

export const router = createRouter({
	history: createWebHistory("/infra/"),
	routes,
});
