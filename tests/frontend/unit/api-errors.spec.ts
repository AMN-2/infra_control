import { describe, expect, it } from "vitest";
import { ApiError, toApiError } from "@/api/errors";

describe("toApiError", () => {
	it("reads the contract error envelope", () => {
		const err = toApiError(409, {
			error: { code: "capability_missing", message: "No ssh", details: { cap: "ssh" } },
		});
		expect(err).toBeInstanceOf(ApiError);
		expect(err.status).toBe(409);
		expect(err.code).toBe("capability_missing");
		expect(err.message).toBe("No ssh");
		expect(err.details).toEqual({ cap: "ssh" });
	});

	it("falls back to unknown_error for unexpected bodies", () => {
		for (const body of [null, "oops", { error: "flat" }, { error: { code: 1 } }]) {
			const err = toApiError(502, body);
			expect(err.code).toBe("unknown_error");
			expect(err.status).toBe(502);
		}
	});
});

describe("realtimeOrigin", () => {
	it("uses the page origin behind nginx and the Socket.IO port on Frappe's dev server", async () => {
		const { realtimeOrigin, readBoot } = await import("@/api/boot");
		const loc = { protocol: "http:", hostname: "ops-staging.localhost" };
		expect(realtimeOrigin({ socketio_port: null }, loc)).toBeUndefined();
		expect(realtimeOrigin(null, loc)).toBeUndefined();
		expect(realtimeOrigin({ socketio_port: 9000 }, loc)).toBe(
			"http://ops-staging.localhost:9000"
		);
		window.infra_boot = { session_user: "u", socketio_port: 9000 };
		expect(readBoot()?.socketio_port).toBe(9000);
		window.infra_boot = { session_user: "u" };
		expect(readBoot()?.socketio_port).toBeNull();
		delete window.infra_boot;
	});
});
