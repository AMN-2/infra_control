/**
 * Renders a playbook's `params_schema` (JSON Schema draft 2020-12, flat object) as form fields
 * and validates the values before `jobs.run`. The backend validates again with jsonschema; this
 * layer exists so the operator sees mistakes before a job is created.
 */

export type FieldKind =
	"string" | "password" | "boolean" | "number" | "integer" | "enum" | "strings";

export interface Field {
	name: string;
	kind: FieldKind;
	label: string;
	required: boolean;
	description?: string;
	default?: unknown;
	options?: string[];
	pattern?: string;
	minLength?: number;
	format?: string;
	minimum?: number;
	maximum?: number;
	/** `x-picker` (ADR 0005): the dialog renders a GitHub picker instead of a plain input. */
	picker?: "git_connection" | "git_repo" | "git_ref";
}

export type ParamValues = Record<string, unknown>;

function isRecord(v: unknown): v is Record<string, unknown> {
	return typeof v === "object" && v !== null && !Array.isArray(v);
}
function str(v: unknown): string | undefined {
	return typeof v === "string" ? v : undefined;
}
function num(v: unknown): number | undefined {
	return typeof v === "number" ? v : undefined;
}

function pickerOf(v: unknown): Field["picker"] {
	return v === "git_connection" || v === "git_repo" || v === "git_ref" ? v : undefined;
}

/** "admin_password" → "Admin password". */
export function labelFor(name: string): string {
	const words = name.replace(/[_-]+/g, " ").trim();
	return words.charAt(0).toUpperCase() + words.slice(1);
}

export function fieldsFrom(schema: unknown): Field[] {
	if (!isRecord(schema) || !isRecord(schema.properties)) return [];
	const required = new Set(
		Array.isArray(schema.required)
			? schema.required.filter((r): r is string => typeof r === "string")
			: []
	);
	return Object.entries(schema.properties).map(([name, raw]) => {
		const p = isRecord(raw) ? raw : {};
		const type = str(p.type);
		const options = Array.isArray(p.enum)
			? p.enum.filter((o): o is string => typeof o === "string")
			: undefined;
		let kind: FieldKind = "string";
		if (options) kind = "enum";
		else if (type === "boolean") kind = "boolean";
		else if (type === "integer") kind = "integer";
		else if (type === "number") kind = "number";
		else if (type === "array") kind = "strings";
		else if (p.format === "password" || p.writeOnly === true) kind = "password";
		return {
			name,
			kind,
			label: labelFor(name),
			required: required.has(name),
			description: str(p.description),
			default: p.default,
			options,
			pattern: str(p.pattern),
			minLength: num(p.minLength),
			format: str(p.format),
			minimum: num(p.minimum),
			maximum: num(p.maximum),
			picker: pickerOf(p["x-picker"]),
		};
	});
}

/** Starting values: schema defaults, else the empty value of the kind. */
export function initialValues(fields: readonly Field[]): ParamValues {
	const out: ParamValues = {};
	for (const f of fields) {
		if (f.default !== undefined) out[f.name] = f.default;
		else if (f.kind === "boolean") out[f.name] = false;
		else if (f.kind === "strings") out[f.name] = [];
		else if (f.kind === "number" || f.kind === "integer") out[f.name] = null;
		else out[f.name] = "";
	}
	return out;
}

const HOSTNAME =
	/^(?=.{1,253}$)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$/i;

function isEmpty(f: Field, v: unknown): boolean {
	if (f.kind === "boolean") return false;
	if (f.kind === "strings") return !Array.isArray(v) || v.length === 0;
	if (f.kind === "number" || f.kind === "integer")
		return v === null || v === undefined || v === "";
	return v === undefined || v === null || v === "";
}

/** Field name → first problem, for fields with a problem only. */
export function validate(fields: readonly Field[], values: ParamValues): Record<string, string> {
	const errors: Record<string, string> = {};
	for (const f of fields) {
		const v = values[f.name];
		if (isEmpty(f, v)) {
			if (f.required) errors[f.name] = "Required";
			continue;
		}
		switch (f.kind) {
			case "string":
			case "password": {
				const s = typeof v === "string" ? v : String(v);
				if (f.minLength !== undefined && s.length < f.minLength)
					errors[f.name] = `At least ${f.minLength} characters`;
				else if (f.pattern && !new RegExp(f.pattern).test(s))
					errors[f.name] = "Does not match the required format";
				else if (f.format === "hostname" && !HOSTNAME.test(s))
					errors[f.name] = "Not a valid hostname";
				break;
			}
			case "number":
			case "integer": {
				const n = typeof v === "number" ? v : Number(v);
				if (Number.isNaN(n)) errors[f.name] = "Must be a number";
				else if (f.kind === "integer" && !Number.isInteger(n))
					errors[f.name] = "Must be a whole number";
				else if (f.minimum !== undefined && n < f.minimum)
					errors[f.name] = `At least ${f.minimum}`;
				else if (f.maximum !== undefined && n > f.maximum)
					errors[f.name] = `At most ${f.maximum}`;
				break;
			}
			case "enum":
				if (!f.options?.includes(String(v))) errors[f.name] = "Pick one of the options";
				break;
			default:
				break;
		}
	}
	return errors;
}

/** Values as `jobs.run` wants them: optional empties dropped, numbers as numbers. */
export function toParams(fields: readonly Field[], values: ParamValues): ParamValues {
	const out: ParamValues = {};
	for (const f of fields) {
		const v = values[f.name];
		if (isEmpty(f, v)) continue;
		if (f.kind === "number" || f.kind === "integer")
			out[f.name] = typeof v === "number" ? v : Number(v);
		else out[f.name] = v;
	}
	return out;
}

/** "a, b, c" ⇄ ["a","b","c"] for array-of-string fields rendered as one input. */
export function splitList(text: string): string[] {
	return text
		.split(/[,\s]+/)
		.map((s) => s.trim())
		.filter(Boolean);
}
