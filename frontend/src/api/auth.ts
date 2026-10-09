/**
 * Sign-in against Frappe's own `/api/method/login` (ADR 0008). This is the one request outside
 * the generated client: the endpoint belongs to the framework, not to contracts/openapi.yaml,
 * and it is the same request Frappe's login page sends. Nothing here touches the password
 * beyond posting it once; it is never logged or stored.
 */
import { api } from "./client";
import type { InfraBoot } from "./boot";
import { ApiError } from "./errors";

export interface Credentials {
	usr: string;
	pwd: string;
}

export type LoginResult =
	| { kind: "ok" }
	/** Two-factor step: Frappe cached the credentials under `tmpId`; send the code with it. */
	| { kind: "mfa"; tmpId: string; prompt: string; method: string }
	| { kind: "error"; message: string; status: number };

const LOGIN_URL = "/api/method/login";
const MESSAGES: Record<number, string> = {
	401: "Invalid email or password.",
	403: "Too many failed attempts. Wait a few minutes and try again.",
	417: "This account is disabled.",
	429: "Too many attempts. Wait a few minutes and try again.",
};

function stripHtml(text: string): string {
	return text.replace(/<[^>]*>/g, "").trim();
}

/** Frappe reports failures in `message`, `exception` or the `_server_messages` JSON list. */
export function parseLoginError(status: number, body: unknown): string {
	if (typeof body === "object" && body !== null) {
		const b = body as Record<string, unknown>;
		if (typeof b._server_messages === "string") {
			try {
				const list = JSON.parse(b._server_messages) as unknown;
				if (Array.isArray(list) && list.length) {
					const first = list[0] as unknown;
					const parsed =
						typeof first === "string" ? (JSON.parse(first) as unknown) : first;
					const message = (parsed as { message?: unknown } | null)?.message;
					if (typeof message === "string" && message) return stripHtml(message);
				}
			} catch {
				/* fall through to the status text */
			}
		}
		if (typeof b.message === "string" && b.message && status !== 401)
			return stripHtml(b.message);
	}
	return MESSAGES[status] ?? "Sign-in failed. Try again.";
}

export function parseLoginResponse(status: number, body: unknown): LoginResult {
	const b = (typeof body === "object" && body !== null ? body : {}) as Record<string, unknown>;
	if (status >= 200 && status < 300) {
		const verification = b.verification as { prompt?: unknown; method?: unknown } | undefined;
		if (verification && typeof b.tmp_id === "string") {
			return {
				kind: "mfa",
				tmpId: b.tmp_id,
				prompt:
					typeof verification.prompt === "string"
						? stripHtml(verification.prompt)
						: "Enter the verification code.",
				method: typeof verification.method === "string" ? verification.method : "OTP App",
			};
		}
		if (b.message === "Password Reset") {
			return {
				kind: "error",
				status,
				message: "Your password has expired. Reset it from the standard login page.",
			};
		}
		if (b.message === "Logged In" || typeof b.full_name === "string" || "home_page" in b) {
			return { kind: "ok" };
		}
		return { kind: "error", status, message: "Unexpected response from the server." };
	}
	return { kind: "error", status, message: parseLoginError(status, body) };
}

async function post(body: Record<string, string>): Promise<LoginResult> {
	let response: Response;
	try {
		// eslint-disable-next-line no-restricted-globals -- framework endpoint, see module doc.
		response = await fetch(LOGIN_URL, {
			method: "POST",
			credentials: "same-origin",
			headers: {
				"Content-Type": "application/json",
				Accept: "application/json",
				"X-Requested-With": "XMLHttpRequest",
			},
			body: JSON.stringify(body),
		});
	} catch {
		return {
			kind: "error",
			status: 0,
			message: "Network error. Check the connection and retry.",
		};
	}
	const data: unknown = await response.json().catch(() => null);
	return parseLoginResponse(response.status, data);
}

export function login(credentials: Credentials): Promise<LoginResult> {
	return post({ usr: credentials.usr, pwd: credentials.pwd });
}

/** Second step of two-factor sign-in. The credentials stay in Frappe's cache under `tmpId`. */
export function confirmOtp(tmpId: string, otp: string): Promise<LoginResult> {
	return post({ tmp_id: tmpId, otp });
}

/** The new session's boot data; 403 permission_denied means "signed in, but no Infra role". */
export async function fetchBoot(): Promise<InfraBoot> {
	const { data } = await api.GET("/api/method/infra_control.api.session.boot");
	if (!data) {
		throw new ApiError(500, {
			code: "internal_error",
			message: "Empty boot response",
			details: {},
		});
	}
	return { ...data, socketio_port: data.socketio_port ?? null };
}

export const DEFAULT_DESTINATION = "/overview";

/**
 * Where to go after sign-in. Only same-origin paths under the SPA are honoured; anything else
 * (another origin, a protocol-relative URL, the login page itself) falls back to the overview.
 * Returns the path relative to the router base (`/infra`).
 */
export function safeDestination(
	raw: string | null | undefined,
	origin: string = window.location.origin
): string {
	if (!raw || raw.startsWith("//") || raw.includes("\\")) return DEFAULT_DESTINATION;
	let url: URL;
	try {
		url = new URL(raw, origin);
	} catch {
		return DEFAULT_DESTINATION;
	}
	if (url.origin !== origin) return DEFAULT_DESTINATION;
	if (url.pathname !== "/infra" && !url.pathname.startsWith("/infra/"))
		return DEFAULT_DESTINATION;
	const inner = url.pathname.slice("/infra".length) || "/";
	if (inner === "/" || inner === "/login" || inner.startsWith("/login/"))
		return DEFAULT_DESTINATION;
	return inner + url.search;
}
