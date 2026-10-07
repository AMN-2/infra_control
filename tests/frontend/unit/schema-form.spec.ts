import { describe, expect, it } from "vitest";
import {
	fieldsFrom,
	initialValues,
	labelFor,
	splitList,
	toParams,
	validate,
} from "@/features/jobs/schemaForm";

const provision = {
	type: "object",
	additionalProperties: false,
	required: ["hostname", "region", "size"],
	properties: {
		hostname: { type: "string", pattern: "^[a-z0-9.-]{3,63}$" },
		region: { type: "string" },
		size: { type: "string" },
		role: { type: "string", enum: ["app", "db", "proxy", "all"], default: "all" },
		tags: { type: "array", items: { type: "string" }, default: [] },
	},
};
const createSite = {
	type: "object",
	required: ["domain", "admin_password"],
	properties: {
		domain: { type: "string", format: "hostname" },
		apps: { type: "array", items: { type: "string" }, default: [] },
		admin_password: { type: "string", format: "password", writeOnly: true, minLength: 12 },
	},
};

describe("schemaForm", () => {
	it("derives fields, kinds and defaults from params_schema", () => {
		const f = fieldsFrom(provision);
		expect(f.map((x) => [x.name, x.kind, x.required])).toEqual([
			["hostname", "string", true],
			["region", "string", true],
			["size", "string", true],
			["role", "enum", false],
			["tags", "strings", false],
		]);
		expect(initialValues(f)).toEqual({
			hostname: "",
			region: "",
			size: "",
			role: "all",
			tags: [],
		});
		expect(fieldsFrom(createSite).find((x) => x.name === "admin_password")?.kind).toBe(
			"password"
		);
		expect(fieldsFrom({})).toEqual([]);
		expect(fieldsFrom(null)).toEqual([]);
		expect(labelFor("admin_password")).toBe("Admin password");
	});

	it("validates required, pattern, minLength, hostname and enums", () => {
		const f = fieldsFrom(provision);
		expect(validate(f, initialValues(f))).toEqual({
			hostname: "Required",
			region: "Required",
			size: "Required",
		});
		expect(
			validate(f, {
				hostname: "BAD HOST",
				region: "fra1",
				size: "s-1",
				role: "all",
				tags: [],
			})
		).toEqual({ hostname: "Does not match the required format" });
		expect(
			validate(f, {
				hostname: "app-03.fra1",
				region: "fra1",
				size: "s-1",
				role: "x",
				tags: [],
			})
		).toEqual({ role: "Pick one of the options" });

		const g = fieldsFrom(createSite);
		expect(validate(g, { domain: "not a host", apps: [], admin_password: "short" })).toEqual({
			domain: "Not a valid hostname",
			admin_password: "At least 12 characters",
		});
		expect(
			validate(g, {
				domain: "erp.client-d.iq",
				apps: [],
				admin_password: "correct-horse-battery",
			})
		).toEqual({});
	});

	it("validates numbers and booleans", () => {
		const f = fieldsFrom({
			required: ["count"],
			properties: {
				count: { type: "integer", minimum: 1, maximum: 5 },
				ratio: { type: "number" },
				on: { type: "boolean" },
			},
		});
		expect(initialValues(f)).toEqual({ count: null, ratio: null, on: false });
		expect(validate(f, { count: null, ratio: null, on: false })).toEqual({
			count: "Required",
		});
		expect(validate(f, { count: 1.5, ratio: "x", on: true })).toEqual({
			count: "Must be a whole number",
			ratio: "Must be a number",
		});
		expect(validate(f, { count: 9, ratio: 0.5, on: true })).toEqual({ count: "At most 5" });
		expect(toParams(f, { count: "3", ratio: null, on: false })).toEqual({
			count: 3,
			on: false,
		});
	});

	it("drops optional empties and keeps lists in params", () => {
		const f = fieldsFrom(provision);
		expect(
			toParams(f, {
				hostname: "app-03.fra1",
				region: "fra1",
				size: "s-1",
				role: "all",
				tags: [],
			})
		).toEqual({ hostname: "app-03.fra1", region: "fra1", size: "s-1", role: "all" });
		expect(splitList("erpnext, hrms  posawesome")).toEqual(["erpnext", "hrms", "posawesome"]);
	});
});
