/** Small, dependency-free time formatting shared by the screens. */

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** "just now", "3 min ago", "2 h ago", "5 d ago"; future stamps read "in …". */
export function relativeTime(iso: string, now: number = Date.now()): string {
	const t = Date.parse(iso);
	if (Number.isNaN(t)) return "";
	const diff = now - t;
	const abs = Math.abs(diff);
	const label = (() => {
		if (abs < MINUTE) return "just now";
		if (abs < HOUR) return `${Math.round(abs / MINUTE)} min`;
		if (abs < DAY) return `${Math.round(abs / HOUR)} h`;
		return `${Math.round(abs / DAY)} d`;
	})();
	if (label === "just now") return label;
	return diff >= 0 ? `${label} ago` : `in ${label}`;
}

/** Seconds since `iso`, never negative; null when the stamp is unreadable. */
export function secondsSince(iso: string, now: number = Date.now()): number | null {
	const t = Date.parse(iso);
	if (Number.isNaN(t)) return null;
	return Math.max(0, Math.round((now - t) / 1000));
}

/** "09:31" in the viewer's locale and timezone (hours and minutes only). */
export function shortTime(iso: string, locale?: string): string {
	const t = Date.parse(iso);
	if (Number.isNaN(t)) return "";
	return new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit" }).format(t);
}
