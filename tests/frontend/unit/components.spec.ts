import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
	clearToasts,
	createLogBuffer,
	dismissToast,
	IcBadge,
	IcButton,
	IcConfirmDialog,
	IcProgress,
	IcStatusBadge,
	IcTable,
	IcTabs,
	IcTimeline,
	pushToast,
	toasts,
} from "@/design/components";
import { toneFor } from "@/design/status";

afterEach(() => {
	clearToasts();
});

describe("IcButton", () => {
	it("blocks clicks while loading and keeps its label (no spinner)", () => {
		const w = mount(IcButton, { props: { loading: true }, slots: { default: "Save" } });
		expect(w.text()).toBe("Save");
		expect(w.attributes("disabled")).toBeDefined();
		expect(w.attributes("aria-busy")).toBe("true");
	});
	it("renders variants with token classes only", () => {
		const w = mount(IcButton, { props: { variant: "primary" } });
		expect(w.classes()).toContain("bg-accent");
	});
});

describe("status badges", () => {
	it("maps every entity through status.ts and pulses only live states", () => {
		expect(toneFor("server", "Down")).toBe("down");
		expect(toneFor("severity", "info")).toBe("running");
		expect(toneFor("job", "Nonsense")).toBe("neutral");
		const live = mount(IcStatusBadge, { props: { entity: "job", status: "Running" } });
		expect(live.find(".ic-pulse").exists()).toBe(true);
		const idle = mount(IcStatusBadge, { props: { entity: "job", status: "Queued" } });
		expect(idle.find(".ic-pulse").exists()).toBe(false);
		expect(
			mount(IcBadge, { props: { tone: "down" }, slots: { default: "x" } }).classes()
		).toContain("text-down");
	});
});

describe("IcTable", () => {
	const columns = [
		{ key: "name", label: "Name" },
		{ key: "cpu", label: "CPU", align: "end" as const },
	];
	it("renders rows, slots and emits row clicks", async () => {
		const rows = [
			{ name: "a", cpu: 1 },
			{ name: "b", cpu: 2 },
		];
		const w = mount(IcTable, {
			props: { columns, rows, rowKey: "name", clickable: true },
			slots: {
				"cell-cpu": `<template #cell-cpu="{ value }"><b>{{ value }}%</b></template>`,
			},
		});
		expect(w.findAll("tbody tr")).toHaveLength(2);
		expect(w.find("b").text()).toBe("1%");
		await w.findAll("tbody tr")[1]?.trigger("click");
		expect(w.emitted("rowClick")?.[0]).toEqual([rows[1]]);
	});
	it("shows skeletons while loading and an empty state otherwise", () => {
		const loading = mount(IcTable, {
			props: { columns, rows: [], rowKey: "name", loading: true },
		});
		expect(loading.findAll('[role="status"]').length).toBeGreaterThan(0);
		const empty = mount(IcTable, {
			props: { columns, rows: [], rowKey: "name", emptyTitle: "No servers" },
		});
		expect(empty.find('[data-testid="empty-state"]').text()).toContain("No servers");
	});
});

describe("IcConfirmDialog", () => {
	it("enables confirm only when the typed value equals the expected one", async () => {
		const w = mount(IcConfirmDialog, {
			props: { modelValue: true, title: "Reboot", expected: "SRV-0001" },
			attachTo: document.body,
		});
		await nextTick();
		const input = document.querySelector<HTMLInputElement>('[data-testid="confirm-input"]');
		const submit = document.querySelector<HTMLButtonElement>('[data-testid="confirm-submit"]');
		if (!input || !submit) throw new Error("confirm dialog did not render its controls");
		expect(submit.disabled).toBe(true);
		input.value = "SRV-000";
		input.dispatchEvent(new Event("input"));
		await nextTick();
		expect(submit.disabled).toBe(true);
		input.value = "SRV-0001";
		input.dispatchEvent(new Event("input"));
		await nextTick();
		expect(submit.disabled).toBe(false);
		submit.click();
		expect(w.emitted("confirm")?.[0]).toEqual(["SRV-0001"]);
		w.unmount();
	});
});

describe("IcTabs", () => {
	it("moves selection with arrow keys", async () => {
		const w = mount(IcTabs, {
			props: {
				modelValue: "a",
				label: "t",
				tabs: [
					{ id: "a", label: "A" },
					{ id: "b", label: "B" },
				],
				"onUpdate:modelValue": (v: string) => w.setProps({ modelValue: v }),
			},
		});
		await w.find('[role="tab"]').trigger("keydown", { key: "ArrowRight" });
		expect(w.emitted("update:modelValue")?.[0]).toEqual(["b"]);
	});
});

describe("IcTimeline", () => {
	it("expands the running step and marks statuses", () => {
		const w = mount(IcTimeline, {
			props: {
				steps: [
					{ idx: 0, title: "Backup", status: "Success", output: "done" },
					{ idx: 1, title: "Migrate", status: "Running", output: "working" },
					{ idx: 2, title: "Health", status: "Queued" },
				],
			},
		});
		const items = w.findAll("li");
		expect(items.map((i) => i.attributes("data-status"))).toEqual([
			"Success",
			"Running",
			"Queued",
		]);
		expect(w.find("pre").text()).toBe("working");
		expect(w.findAll("pre")).toHaveLength(1);
	});
});

describe("IcProgress", () => {
	it("clamps and animates with a transform, never width", () => {
		const w = mount(IcProgress, { props: { value: 140 } });
		expect(w.find('[role="progressbar"]').attributes("aria-valuenow")).toBe("100");
		expect(w.find('[role="progressbar"] > div').attributes("style")).toContain("scaleX(1)");
	});
});

describe("toasts", () => {
	it("pushes, caps at five and dismisses", () => {
		for (let i = 0; i < 7; i++) pushToast({ title: `t${i}`, timeout: 0 });
		expect(toasts.items).toHaveLength(5);
		const newest = toasts.items[0];
		if (!newest) throw new Error("toast list is empty");
		expect(newest.title).toBe("t6");
		dismissToast(newest.id);
		expect(toasts.items[0]?.title).toBe("t5");
	});
});

describe("log buffer", () => {
	it("coalesces chunks into one flush per interval", () => {
		const flushed: string[] = [];
		const scheduled: (() => void)[] = [];
		const buf = createLogBuffer(
			(t) => {
				flushed.push(t);
			},
			50,
			(fn) => {
				scheduled.push(fn);
				return 0;
			}
		);
		buf.push("a");
		buf.push("b");
		buf.push("c");
		expect(scheduled).toHaveLength(1);
		expect(flushed).toEqual([]);
		const flush = scheduled[0];
		if (!flush) throw new Error("no flush was scheduled");
		flush();
		expect(flushed).toEqual(["abc"]);
		buf.push("d");
		expect(scheduled).toHaveLength(2);
		expect(buf.pending()).toBe(1);
		vi.useRealTimers();
	});
});
