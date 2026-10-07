/** Error envelope shared by every endpoint (plan §6.1). */
export interface ApiErrorBody {
	code: string;
	message: string;
	details?: unknown;
}

export class ApiError extends Error {
	readonly code: string;
	readonly status: number;
	readonly details: unknown;

	constructor(status: number, body: ApiErrorBody) {
		super(body.message);
		this.name = "ApiError";
		this.status = status;
		this.code = body.code;
		this.details = body.details;
	}
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null;
}

/** Normalises any failed response body into an ApiError. */
export function toApiError(status: number, body: unknown): ApiError {
	if (isRecord(body) && isRecord(body.error)) {
		const { code, message, details } = body.error;
		if (typeof code === "string" && typeof message === "string") {
			return new ApiError(status, { code, message, details });
		}
	}
	return new ApiError(status, {
		code: "unknown_error",
		message: `Request failed with status ${status}`,
	});
}
