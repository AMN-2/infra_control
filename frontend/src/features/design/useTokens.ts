import { onMounted, ref, type Ref } from "vue";
import { contrastLinear, resolveCssColor } from "@/design/color";
import { token, type TokenName } from "@/design/tokens";

/** Reads token values after mount so the showcase displays what the browser actually resolved. */
export function useTokenValues<T extends TokenName>(names: readonly T[]): Ref<Record<T, string>> {
	const values = ref({}) as Ref<Record<T, string>>;
	onMounted(() => {
		values.value = Object.fromEntries(names.map((n) => [n, token(n)])) as Record<T, string>;
	});
	return values;
}

/** Live contrast ratio between two tokens, formatted for display. */
export function useContrast(fg: TokenName, bg: TokenName): Ref<string> {
	const out = ref("…");
	onMounted(() => {
		const f = resolveCssColor(token(fg));
		const b = resolveCssColor(token(bg));
		const ratio = f && b ? contrastLinear(f.rgb, f.a, b.rgb) : NaN;
		out.value = Number.isFinite(ratio) ? `${ratio.toFixed(1)}:1` : "n/a";
	});
	return out;
}
