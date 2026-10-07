"""Q-B2: the `/infra` page resolves the built SPA from the Vite manifest and is wired in hooks."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from infra_control.core import spa

MANIFEST = {
	"src/main.ts": {
		"file": "assets/index-AbC123.js",
		"src": "src/main.ts",
		"isEntry": True,
		"css": ["assets/index-Def456.css"],
		"imports": ["_vendor-Ghi789.js"],
		"dynamicImports": ["src/features/design/DesignShowcase.vue"],
	},
	"_vendor-Ghi789.js": {
		"file": "assets/vendor-Ghi789.js",
		"css": ["assets/vendor-Jkl012.css"],
	},
	"src/features/design/DesignShowcase.vue": {
		"file": "assets/DesignShowcase-Mno345.js",
		"css": ["assets/DesignShowcase-Pqr678.css"],
		"isDynamicEntry": True,
	},
}


def test_resolve_assets_walks_static_imports_only() -> None:
	assets = spa.resolve_assets(MANIFEST)
	assert assets.entry == "/assets/infra_control/frontend/assets/index-AbC123.js"
	# vendor css first (depth-first), entry css second; the lazy chunk's css is not preloaded
	assert assets.styles == (
		"/assets/infra_control/frontend/assets/vendor-Jkl012.css",
		"/assets/infra_control/frontend/assets/index-Def456.css",
	)
	assert assets.preloads == ("/assets/infra_control/frontend/assets/vendor-Ghi789.js",)


def test_resolve_assets_accepts_the_entry_key_vite_really_emits() -> None:
	"""Live gate: the default build (index.html input) keys the entry chunk "index.html"."""
	real = {
		"index.html": {
			"file": "assets/index-DxVwq0nk.js",
			"name": "index",
			"src": "index.html",
			"isEntry": True,
			"imports": ["_components-Cv-EN6uo.js"],
			"css": ["assets/index-bJbK9LwN.css"],
		},
		"_components-Cv-EN6uo.js": {"file": "assets/components-Cv-EN6uo.js"},
	}
	assets = spa.resolve_assets(real)
	assert assets.entry == "/assets/infra_control/frontend/assets/index-DxVwq0nk.js"
	assert assets.preloads == ("/assets/infra_control/frontend/assets/components-Cv-EN6uo.js",)
	other = {"app.ts": {"file": "assets/app-1.js", "isEntry": True}}
	assert spa.resolve_assets(other).entry.endswith("assets/app-1.js")
	two = {"a.ts": {"file": "a.js", "isEntry": True}, "b.ts": {"file": "b.js", "isEntry": True}}
	with pytest.raises(spa.SpaNotBuiltError):
		spa.resolve_assets(two)


def test_resolve_assets_base_gets_trailing_slash() -> None:
	assets = spa.resolve_assets(MANIFEST, base="/x")
	assert assets.entry.startswith("/x/assets/")


def test_resolve_assets_missing_entry() -> None:
	with pytest.raises(spa.SpaNotBuiltError):
		spa.resolve_assets({"other.ts": {"file": "a.js"}})
	with pytest.raises(spa.SpaNotBuiltError):
		spa.resolve_assets({spa.ENTRY: {"isEntry": True}})


def test_load_assets_from_disk(tmp_path: Path) -> None:
	with pytest.raises(spa.SpaNotBuiltError, match=r"frontend_build\.md"):
		spa.load_assets(tmp_path)
	(tmp_path / ".vite").mkdir()
	(tmp_path / ".vite" / "manifest.json").write_text(json.dumps(MANIFEST))
	assert spa.load_assets(tmp_path).entry.endswith("index-AbC123.js")


def test_load_assets_accepts_vite4_manifest_location(tmp_path: Path) -> None:
	(tmp_path / "manifest.json").write_text(json.dumps(MANIFEST))
	assert spa.find_manifest(tmp_path) == tmp_path / "manifest.json"


def test_public_frontend_dir_is_the_asset_base(repo_root: Path) -> None:
	assert spa.public_frontend_dir() == repo_root / "infra_control" / "public" / "frontend"
	assert spa.ASSET_BASE == "/assets/infra_control/frontend/"


def test_boot_dict_has_what_the_client_needs() -> None:
	boot = spa.SpaBoot(
		csrf_token="t", site_name="s", session_user="u", roles=("Infra Admin", "Infra Viewer"), extra={"k": 1}
	).as_dict()
	assert boot["csrf_token"] == "t"
	assert boot["roles"] == ["Infra Admin", "Infra Viewer"]
	assert spa.SpaBoot(csrf_token="t", site_name="s", session_user="u").as_dict()["roles"] == []
	assert boot["api_base"] == "/api/method/infra_control.api."
	assert boot["socketio_path"] == "/socket.io"
	assert boot["base_path"] == "/infra/"
	assert boot["k"] == 1


def test_hooks_route_every_infra_subpath_to_the_page() -> None:
	hooks = importlib.import_module("infra_control.hooks")
	assert hooks.website_route_rules == [{"from_route": "/infra/<path:app_path>", "to_route": "infra"}]


def test_page_template_boots_the_spa(repo_root: Path) -> None:
	www = repo_root / "infra_control" / "www"
	html = (www / "infra.html").read_text()
	assert (www / "infra.py").exists()
	assert "window.csrf_token" in html and "window.infra_boot" in html
	assert '<div id="app"></div>' in html
	assert "</body>" in html, "a full document stops Frappe wrapping it in the web base template"
	assert "{% extends" not in html


def test_built_frontend_is_ignored_by_git(repo_root: Path) -> None:
	ignore = (repo_root / ".gitignore").read_text()
	assert "infra_control/public/frontend/*" in ignore
	assert (repo_root / "infra_control" / "public" / "frontend" / ".gitkeep").exists()
