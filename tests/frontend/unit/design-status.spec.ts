import { describe, expect, it } from "vitest";
import { jobStatusTone, liveStates, serverStatusTone, siteStatusTone } from "@/design/status";

describe("status tones", () => {
	it("covers every enum value from plan §5", () => {
		expect(Object.keys(serverStatusTone).sort()).toEqual(
			["Provisioning", "Active", "Degraded", "Down", "Archived"].sort()
		);
		expect(Object.keys(siteStatusTone).sort()).toEqual(
			["Pending", "Active", "Maintenance", "Suspended", "Broken", "Archived"].sort()
		);
		expect(Object.keys(jobStatusTone).sort()).toEqual(
			["Queued", "Running", "Success", "Failed", "Cancelled", "Skipped"].sort()
		);
	});

	it("keeps the four §10.1 meanings identical across entities", () => {
		expect(serverStatusTone.Active).toBe("healthy");
		expect(siteStatusTone.Active).toBe("healthy");
		expect(jobStatusTone.Success).toBe("healthy");
		expect(serverStatusTone.Down).toBe("down");
		expect(jobStatusTone.Failed).toBe("down");
		expect(jobStatusTone.Running).toBe("running");
	});

	it("only animates genuinely live states", () => {
		expect([...liveStates].sort()).toEqual(["Provisioning", "Running"]);
	});
});
