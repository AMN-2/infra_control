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
