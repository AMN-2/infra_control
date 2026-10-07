import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";
import { toApiError } from "./errors";

declare global {
	interface Window {
		/** Injected by the Frappe page that serves the SPA. */
		csrf_token?: string;
	}
}

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** Frappe rejects session-authenticated writes without the CSRF token. */
const csrf: Middleware = {
	onRequest({ request }) {
		const token = window.csrf_token;
		if (token && UNSAFE_METHODS.has(request.method)) {
			request.headers.set("X-Frappe-CSRF-Token", token);
		}
		return request;
	},
};

/**
 * Contract rule (contracts/openapi.yaml, FrappeFrameworkError): re-authenticate on 401, or on a
 * 403 whose body has no `error` envelope (expired session); a 403 with the envelope is a
 * permission problem for the current user.
 */
export function needsReauthentication(status: number, body: unknown): boolean {
	if (status === 401) return true;
	if (status !== 403) return false;
	return !(typeof body === "object" && body !== null && "error" in body);
}

/** Set once at startup (main.ts) so the client never imports a store. */
export const authHooks: { onReauthenticate: () => void } = { onReauthenticate: () => undefined };

/** Turns error envelopes into thrown ApiError so stores handle one shape. */
const errors: Middleware = {
	async onResponse({ response }) {
		if (response.ok) return response;
		const body: unknown = await response
			.clone()
			.json()
			.catch(() => null);
		if (needsReauthentication(response.status, body)) authHooks.onReauthenticate();
		throw toApiError(response.status, body);
	},
};

/**
 * The only way the UI talks to the backend. Typed from contracts/openapi.yaml via
 * `npm run gen:api`; there are no hand-written fetch calls anywhere else.
 */
export const api = createClient<paths>({ baseUrl: "", credentials: "same-origin" });
api.use(csrf, errors);
