import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

/** The SPA is served at /infra (plan §2). Every feature route is lazy-loaded (plan §10.4). */
export const routes: RouteRecordRaw[] = [
	{
		path: "/",
		name: "home",
		component: () => import("@/features/home/HomeView.vue"),
	},
	{
		// Living design-system showcase for review (B0.2). Restricted to Infra Admin once auth lands (Q-B7).
		path: "/_design",
		name: "design",
		component: () => import("@/features/design/DesignShowcase.vue"),
	},
];

export const router = createRouter({
	history: createWebHistory("/infra/"),
	routes,
});
