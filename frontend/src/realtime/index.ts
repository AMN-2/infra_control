export type { EventMap, EventName } from "./events.generated";
export {
	_resetForTests,
	connectRealtime,
	disconnectRealtime,
	injectEvent,
	onEvent,
	realtimeDropped,
	realtimeError,
	realtimeState,
	type ConnectionState,
	type SocketFactory,
	type SocketLike,
} from "./socket";
export { validateEvent } from "./validate";
