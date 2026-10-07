/** Boot data injected by the Frappe page (`infra_control/www/infra.html`, docs/runbooks/frontend_build.md). */
export interface InfraBoot {
	csrf_token: string;
	site_name: string;
	session_user: string;
	roles: string[];
	base_path: string;
	api_base: string;
	socketio_path: string;
}

declare global {
	interface Window {
		infra_boot?: Partial<InfraBoot>;
	}
}

/**
 * In `npm run dev` there is no Frappe page. The mock accepts any site and any user; against a real
 * site (dev proxy with INFRA_SITE) the realtime namespace must be that site, so VITE_INFRA_SITE
 * overrides it.
 */
export const DEV_BOOT: InfraBoot = {
	csrf_token: "",
	site_name: (import.meta.env.VITE_INFRA_SITE as string | undefined) ?? "mock.localhost",
	session_user: "dev@mock.localhost",
	roles: ["Infra Admin", "Infra Operator", "Infra Viewer"],
	base_path: "/infra/",
	api_base: "/api/method/infra_control.api.",
	socketio_path: "/socket.io",
};

export function readBoot(): InfraBoot | null {
	const raw = window.infra_boot;
	if (!raw?.session_user) return null;
	return {
		csrf_token: raw.csrf_token ?? "",
		site_name: raw.site_name ?? "",
		session_user: raw.session_user,
		roles: raw.roles ?? [],
		base_path: raw.base_path ?? "/infra/",
		api_base: raw.api_base ?? "/api/method/infra_control.api.",
		socketio_path: raw.socketio_path ?? "/socket.io",
	};
}
