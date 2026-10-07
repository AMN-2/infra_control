"""Resolve the built Vue SPA (Agent B's `frontend/`) for the `/infra` page.

Vite writes a manifest next to its hashed bundles. This module turns that manifest into the
`<script>` and `<link>` URLs the page needs. It has no Frappe dependency so it is unit-tested
without a site; `infra_control/www/infra.py` is the thin Frappe wrapper around it.

Layout (see docs/runbooks/frontend_build.md):

    frontend/dist/                      <- `vite build` output (Agent B)
    infra_control/public/frontend/      <- copy of dist, served at /assets/infra_control/frontend/
        .vite/manifest.json             <- Vite >= 5 manifest location
        manifest.json                   <- Vite 4 location (also accepted)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Where `bench build` publishes `infra_control/public/`. Frappe serves `<app>/public/x` at
# `/assets/<app>/x`, so the SPA must be built with `INFRA_UI_BASE` equal to this value.
ASSET_BASE = "/assets/infra_control/frontend/"

# The Vite entry. With `index.html` as the build input (the default), Vite keys the entry chunk
# by "index.html"; a build with `src/main.ts` as rollup input keys it by that. Both are accepted,
# then any single chunk marked `isEntry` (the live gate found the page looking only for
# "src/main.ts" while the real build emitted "index.html").
ENTRY = "src/main.ts"
ENTRY_CANDIDATES = ("index.html", "src/main.ts")


def find_entry(manifest: dict[str, Any]) -> str:
	for key in ENTRY_CANDIDATES:
		if key in manifest:
			return key
	entries = [k for k, v in manifest.items() if isinstance(v, dict) and v.get("isEntry")]
	if len(entries) == 1:
		return entries[0]
	raise SpaNotBuiltError(f"no entry in Vite manifest (keys: {sorted(manifest)[:5]}...)")


MANIFEST_CANDIDATES = (".vite/manifest.json", "manifest.json")


@dataclass(frozen=True)
class SpaAssets:
	"""Everything the HTML page needs to boot the SPA."""

	entry: str
	"""URL of the entry module, e.g. `/assets/infra_control/frontend/assets/index-abc123.js`."""
	styles: tuple[str, ...] = ()
	"""CSS URLs for the entry and its statically imported chunks, in manifest order."""
	preloads: tuple[str, ...] = ()
	"""JS chunk URLs statically imported by the entry, for `<link rel="modulepreload">`."""


class SpaNotBuiltError(RuntimeError):
	"""The frontend bundle is missing or its manifest has no usable entry."""


def public_frontend_dir() -> Path:
	"""`infra_control/public/frontend/` inside the installed package."""
	return Path(__file__).resolve().parents[1] / "public" / "frontend"


def find_manifest(frontend_dir: Path) -> Path | None:
	for rel in MANIFEST_CANDIDATES:
		candidate = frontend_dir / rel
		if candidate.is_file():
			return candidate
	return None


def resolve_assets(
	manifest: dict[str, Any], *, base: str = ASSET_BASE, entry: str | None = None
) -> SpaAssets:
	"""Walk the Vite manifest from `entry`, collecting its CSS and statically imported chunks.

	Dynamic imports are left to the browser (they are lazy by design, plan section 10.4).
	"""
	entry = entry or find_entry(manifest)
	if entry not in manifest:
		raise SpaNotBuiltError(f"entry {entry!r} not in Vite manifest (keys: {sorted(manifest)[:5]}...)")
	if not base.endswith("/"):
		base += "/"

	styles: list[str] = []
	preloads: list[str] = []
	seen: set[str] = set()

	def visit(key: str, *, is_entry: bool) -> None:
		if key in seen:
			return
		seen.add(key)
		chunk = manifest.get(key)
		if not isinstance(chunk, dict):
			return
		# Depth-first so a chunk's own CSS lands before the importer's, matching Vite's order.
		for imported in chunk.get("imports", ()):
			visit(str(imported), is_entry=False)
		for css in chunk.get("css", ()):
			url = base + str(css)
			if url not in styles:
				styles.append(url)
		if not is_entry and "file" in chunk:
			preloads.append(base + str(chunk["file"]))

	visit(entry, is_entry=True)
	entry_file = manifest[entry].get("file")
	if not isinstance(entry_file, str) or not entry_file:
		raise SpaNotBuiltError(f"entry {entry!r} has no 'file' in the Vite manifest")
	return SpaAssets(entry=base + entry_file, styles=tuple(styles), preloads=tuple(preloads))


def load_assets(frontend_dir: Path | None = None) -> SpaAssets:
	"""Read the manifest from disk and resolve it. Raises `SpaNotBuiltError` when absent."""
	frontend_dir = frontend_dir or public_frontend_dir()
	manifest_path = find_manifest(frontend_dir)
	if manifest_path is None:
		raise SpaNotBuiltError(
			f"no Vite manifest under {frontend_dir}; build the frontend first "
			"(docs/runbooks/frontend_build.md)"
		)
	with manifest_path.open(encoding="utf-8") as fh:
		manifest = json.load(fh)
	if not isinstance(manifest, dict):
		raise SpaNotBuiltError(f"{manifest_path} is not a JSON object")
	return resolve_assets(manifest)


@dataclass(frozen=True)
class SpaBoot:
	"""Data the page injects as `window.infra_boot` (and `window.csrf_token`)."""

	csrf_token: str
	site_name: str
	session_user: str
	roles: tuple[str, ...] = ()
	"""Infra roles the user holds (hierarchy applied), for the client-side guard and menus."""
	base_path: str = "/infra/"
	api_base: str = "/api/method/infra_control.api."
	socketio_path: str = "/socket.io"
	extra: dict[str, Any] = field(default_factory=dict)

	def as_dict(self) -> dict[str, Any]:
		return {
			"csrf_token": self.csrf_token,
			"site_name": self.site_name,
			"session_user": self.session_user,
			"roles": list(self.roles),
			"base_path": self.base_path,
			"api_base": self.api_base,
			"socketio_path": self.socketio_path,
			**self.extra,
		}
