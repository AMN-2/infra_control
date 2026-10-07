import { ref, type Ref } from "vue";
import { ApiError } from "@/api/errors";

/** Loading / error state every store exposes the same way (loading, empty and error states, DoD). */
export interface AsyncState {
	loading: Ref<boolean>;
	error: Ref<ApiError | null>;
	run: <T>(fn: () => Promise<T>) => Promise<T | undefined>;
}

export function useAsyncState(): AsyncState {
	const loading = ref(false);
	const error = ref<ApiError | null>(null);
	async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
		loading.value = true;
		error.value = null;
		try {
			return await fn();
		} catch (e) {
			error.value =
				e instanceof ApiError
					? e
					: new ApiError(0, { code: "network_error", message: String(e) });
			return undefined;
		} finally {
			loading.value = false;
		}
	}
	return { loading, error, run };
}

/** openapi-fetch returns { data, error }; the error middleware already throws, so data is set. */
export function unwrap<T>(result: { data?: T }): T {
	if (result.data === undefined)
		throw new ApiError(0, { code: "empty_response", message: "Empty response" });
	return result.data;
}
