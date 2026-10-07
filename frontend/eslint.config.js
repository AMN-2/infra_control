import pluginVue from "eslint-plugin-vue";
import { defineConfigWithVueTs, vueTsConfigs } from "@vue/eslint-config-typescript";
import globals from "globals";
import prettier from "eslint-config-prettier";

export default defineConfigWithVueTs(
	{
		ignores: [
			"dist/**",
			"coverage/**",
			"playwright-report/**",
			"test-results/**",
			"src/api/schema.d.ts",
		],
	},
	pluginVue.configs["flat/recommended"],
	vueTsConfigs.strictTypeChecked,
	prettier,
	{
		languageOptions: { globals: globals.browser },
		rules: {
			"vue/multi-word-component-names": "off",
			"vue/max-attributes-per-line": "off",
			"vue/singleline-html-element-content-newline": "off",
			"vue/html-self-closing": "off",
			"vue/block-lang": ["error", { script: { lang: "ts" } }],
			"vue/component-api-style": ["error", ["script-setup"]],
			"@typescript-eslint/restrict-template-expressions": ["error", { allowNumber: true }],
			// Components never touch the network or the socket directly (plan §10.4).
			"no-restricted-globals": [
				"error",
				{ name: "fetch", message: "Use the generated client in src/api." },
			],
			"no-restricted-imports": [
				"error",
				{
					paths: [
						{
							name: "socket.io-client",
							message: "Only src/realtime may import the socket.",
						},
					],
				},
			],
		},
	},
	{
		files: ["src/realtime/**"],
		rules: { "no-restricted-imports": "off" },
	},
	{
		files: ["*.config.js", "scripts/**"],
		extends: [vueTsConfigs.disableTypeChecked],
		languageOptions: { globals: globals.node },
	}
);
