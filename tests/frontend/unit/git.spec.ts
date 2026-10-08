import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/api/client", () => ({
	api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) },
}));

const { useGitStore } = await import("@/stores/git");
const { fieldsFrom } = await import("@/features/jobs/schemaForm");

const connection = {
	name: "GH",
	label: "GH",
	provider: "github",
	enabled: true,
	login: "smartchoice-iq",
	account_type: "Organization",
	scopes: ["repo"],
	verified_at: "2026-10-09T08:00:00Z",
};
const repo = {
	full_name: "smartchoice-iq/smart_features",
	name: "smart_features",
	owner: "smartchoice-iq",
	private: true,
	default_branch: "develop",
	clone_url: "https://github.com/smartchoice-iq/smart_features.git",
	description: null,
	pushed_at: null,
};

beforeEach(() => {
	setActivePinia(createPinia());
	GET.mockReset();
	POST.mockReset();
});

describe("git store (ADR 0005)", () => {
	it("connects, lists, searches, caches refs and disconnects", async () => {
		GET.mockResolvedValueOnce({ data: { items: [] } });
		const git = useGitStore();
		await git.fetchConnections();
		expect(git.loaded).toBe(true);
		POST.mockResolvedValueOnce({ data: { connection } });
		expect(await git.connect("GH", "ghp_x")).toEqual(connection);
		expect(POST.mock.calls[0]?.[1]).toEqual({ body: { label: "GH", token: "ghp_x" } });
		GET.mockResolvedValueOnce({ data: { items: [repo], next_page: 2 } });
		const page = await git.searchRepos("GH", "smart");
		expect(page.items[0]?.full_name).toBe(repo.full_name);
		GET.mockResolvedValueOnce({
			data: { repo, items: [{ name: "develop", kind: "branch", sha: "abc" }] },
		});
		await git.fetchRefs("GH", repo.full_name);
		await git.fetchRefs("GH", repo.full_name);
		expect(GET).toHaveBeenCalledTimes(3); // refs are cached per connection:repo
		POST.mockResolvedValueOnce({ data: { connection: "GH", deleted: true } });
		expect(await git.disconnect("GH")).toBe(true);
		expect(git.connections).toEqual([]);
	});

	it("keeps the error message when the token is rejected", async () => {
		const { ApiError } = await import("@/api/errors");
		POST.mockRejectedValueOnce(
			new ApiError(400, {
				code: "validation_error",
				message: "GitHub rejected the access token",
			})
		);
		const git = useGitStore();
		expect(await git.connect("GH", "bad")).toBeUndefined();
		expect(git.saveError).toContain("rejected");
	});
});

describe("schema form x-picker", () => {
	it("maps x-picker hints onto fields and ignores unknown ones", () => {
		const fields = fieldsFrom({
			type: "object",
			properties: {
				repo: { type: "string", "x-picker": "git_repo" },
				branch: { type: "string", "x-picker": "git_ref" },
				connection: { type: "string", "x-picker": "git_connection" },
				other: { type: "string", "x-picker": "nope" },
			},
		});
		expect(fields.map((f) => f.picker)).toEqual([
			"git_repo",
			"git_ref",
			"git_connection",
			undefined,
		]);
	});
});
