import { describe, expect, it } from "vitest";
import { routes } from "@/router";

describe("routes", () => {
	it("lazy-loads every route component", () => {
		for (const route of routes) {
			expect(typeof route.component).toBe("function");
		}
	});
});
