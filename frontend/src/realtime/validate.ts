import Ajv2020, { type ValidateFunction } from "ajv/dist/2020";
import addFormats from "ajv-formats";
import { eventSchemas, type EventMap, type EventName } from "./events.generated";

const ajv = new Ajv2020({ allErrors: false, strict: true });
addFormats(ajv);
const compiled = new Map<EventName, ValidateFunction>();

export const eventNames = Object.keys(eventSchemas) as EventName[];

export function isEventName(name: string): name is EventName {
	return name in eventSchemas;
}

/** Validates a payload against the contract schema; the socket drops anything that fails. */
export function validateEvent<E extends EventName>(
	event: E,
	payload: unknown
): { ok: true; payload: EventMap[E] } | { ok: false; error: string } {
	let fn = compiled.get(event);
	if (!fn) {
		fn = ajv.compile(eventSchemas[event]);
		compiled.set(event, fn);
	}
	// The schema is the contract for this event, so a passing payload has the generated type.
	if (fn(payload)) return { ok: true, payload: payload as unknown as EventMap[E] };
	return { ok: false, error: ajv.errorsText(fn.errors) };
}
