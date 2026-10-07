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

/** Turns error envelopes into thrown ApiError so stores handle one shape. */
const errors: Middleware = {
	async onResponse({ response }) {
		if (response.ok) return response;
		const body: unknown = await response
			.clone()
			.json()
			.catch(() => null);
		throw toApiError(response.status, body);
	},
};

/**
 * The only way the UI talks to the backend. Typed from contracts/openapi.yaml via
 * `npm run gen:api`; there are no hand-written fetch calls anywhere else.
 */
export const api = createClient<paths>({ baseUrl: "", credentials: "same-origin" });
api.use(csrf, errors);
