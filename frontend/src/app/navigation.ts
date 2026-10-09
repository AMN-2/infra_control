import type { Component } from "vue";
import {
	Activity,
	Bell,
	Boxes,
	Globe,
	Layers,
	ListChecks,
	Package,
	Server,
	Users,
} from "lucide-vue-next";

export interface NavItem {
	name: string;
	label: string;
	to: string;
	icon: Component;
	/** Keyboard shortcut shown in the palette (g then key). */
	key: string;
}

/** Primary navigation (plan §10.2 screens), in reading order. */
export const navigation: readonly NavItem[] = [
	{ name: "overview", label: "Overview", to: "/overview", icon: Activity, key: "o" },
	{ name: "topology", label: "Topology", to: "/topology", icon: Boxes, key: "t" },
	{ name: "servers", label: "Servers", to: "/servers", icon: Server, key: "s" },
	{ name: "benches", label: "Benches", to: "/benches", icon: Package, key: "h" },
	{ name: "sites", label: "Sites", to: "/sites", icon: Globe, key: "i" },
	{ name: "tenants", label: "Tenants", to: "/tenants", icon: Users, key: "c" },
	{ name: "jobs", label: "Jobs", to: "/jobs", icon: ListChecks, key: "j" },
	{ name: "bulk", label: "Bulk rollouts", to: "/bulk", icon: Layers, key: "b" },
	{ name: "alerts", label: "Alerts", to: "/alerts", icon: Bell, key: "a" },
];
