/**
 * Read tokens from JavaScript (for ECharts, Vue Flow, xterm.js, which need concrete values).
 * The values themselves live only in tokens.css.
 */
export type TokenName = `--ic-${string}`;

export function token(name: TokenName, el: Element = document.documentElement): string {
	return getComputedStyle(el).getPropertyValue(name).trim();
}

export function tokenMs(name: TokenName, el?: Element): number {
	const raw = token(name, el);
	return raw.endsWith("ms") ? parseFloat(raw) : parseFloat(raw) * 1000;
}

/** The 4px grid in px, for layouts computed in script (SVG diagrams). Mirrors --ic-space-unit. */
export const spaceUnitPx = 4;

/** Shared ECharts plot insets, kept in design so chart features do not own physical layout. */
export const chartGrid = {
	top: spaceUnitPx * 3,
	right: spaceUnitPx * 3,
	bottom: spaceUnitPx * 6,
	left: spaceUnitPx * 12,
} as const;
