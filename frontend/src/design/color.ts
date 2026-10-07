/**
 * Minimal OKLCH → sRGB conversion and WCAG contrast, used to verify token pairs in tests and
 * to show live contrast ratios in the design showcase. Reference: Björn Ottosson, "OKLab".
 */
export interface Rgba {
	r: number;
	g: number;
	b: number;
	a: number;
}

const OKLCH = /oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*(?:\/\s*([\d.]+%?))?\s*\)/;

export function parseOklch(value: string): { l: number; c: number; h: number; a: number } | null {
	const m = OKLCH.exec(value);
	if (!m) return null;
	const [, l = "0", c = "0", h = "0", a] = m;
	const alpha = a === undefined ? 1 : a.endsWith("%") ? parseFloat(a) / 100 : parseFloat(a);
	return { l: parseFloat(l), c: parseFloat(c), h: parseFloat(h), a: alpha };
}

const clamp01 = (x: number): number => Math.min(1, Math.max(0, x));

/** Linear-light sRGB channels (0..1), gamut-clipped. */
export function oklchToLinearRgb(l: number, c: number, h: number): [number, number, number] {
	const hr = (h * Math.PI) / 180;
	const A = c * Math.cos(hr);
	const B = c * Math.sin(hr);
	const l_ = (l + 0.3963377774 * A + 0.2158037573 * B) ** 3;
	const m_ = (l - 0.1055613458 * A - 0.0638541728 * B) ** 3;
	const s_ = (l - 0.0894841775 * A - 1.291485548 * B) ** 3;
	return [
		clamp01(4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_),
		clamp01(-1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_),
		clamp01(-0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_),
	];
}

export function relativeLuminance([r, g, b]: [number, number, number]): number {
	return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

const toGamma = (x: number): number =>
	x <= 0.0031308 ? 12.92 * x : 1.055 * x ** (1 / 2.4) - 0.055;
const toLinear = (x: number): number => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4);

/** Alpha-composites `top` over an opaque `bottom` in gamma space, as browsers do. */
function composite(
	top: [number, number, number],
	alpha: number,
	bottom: [number, number, number]
): [number, number, number] {
	return top.map((t, i) => {
		const mixed = toGamma(t) * alpha + toGamma(bottom[i] ?? 0) * (1 - alpha);
		return toLinear(mixed);
	}) as [number, number, number];
}

/** WCAG 2 contrast between two colours given as linear-light RGB; fg may be translucent. */
export function contrastLinear(
	fg: [number, number, number],
	fgAlpha: number,
	bg: [number, number, number]
): number {
	const mixed = composite(fg, fgAlpha, bg);
	const [hi, lo] = [relativeLuminance(mixed), relativeLuminance(bg)].sort((x, y) => y - x) as [
		number,
		number,
	];
	return (hi + 0.05) / (lo + 0.05);
}

/** WCAG 2 contrast between two oklch() strings (as authored in tokens.css). */
export function contrastRatio(fg: string, bg: string): number {
	const f = parseOklch(fg);
	const b = parseOklch(bg);
	if (!f || !b) return NaN;
	return contrastLinear(oklchToLinearRgb(f.l, f.c, f.h), f.a, oklchToLinearRgb(b.l, b.c, b.h));
}

let probe: CanvasRenderingContext2D | null | undefined;

/**
 * Browser only: resolves any CSS colour (hex, lab(), oklch(), named) to linear RGB + alpha by
 * painting one pixel, so the result is exactly what the browser renders.
 */
export function resolveCssColor(
	value: string
): { rgb: [number, number, number]; a: number } | null {
	probe ??= document.createElement("canvas").getContext("2d", { willReadFrequently: true });
	if (!probe) return null;
	probe.clearRect(0, 0, 1, 1);
	probe.fillStyle = value;
	probe.fillRect(0, 0, 1, 1);
	const [r = 0, g = 0, b = 0, a = 0] = probe.getImageData(0, 0, 1, 1).data;
	return { rgb: [toLinear(r / 255), toLinear(g / 255), toLinear(b / 255)], a: a / 255 };
}
