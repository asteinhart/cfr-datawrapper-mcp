# Proposal — MCP folder support

## Context

The Datawrapper MCP server currently exposes no folder metadata. `get_chart` drops `folderId` / `teamId`, `create_chart` and `update_chart` have no folder argument, and there is no way to list folders. The underlying `datawrapper` Python library (v2.0.14, pinned in [pyproject.toml](../../pyproject.toml)) already implements every REST operation we need — the MCP layer just needs to surface them.

This proposal stays entirely within this repo — no upstream library changes. We pay one extra API round-trip in a couple of places, but the PR ships today and doesn't block on a library release. A later-optional upstream cleanup is sketched at the bottom.

## What the `datawrapper` library already gives us

Verified by reading the installed package:

- `Datawrapper.move_chart(chart_id, folder_id)` → `PATCH /v3/charts/{id}` with `{"folderId": folder_id}` (`datawrapper/__main__.py:1082`).
- `Datawrapper.get_folders()` → `GET /v3/folders` (returns a tree with top-level `list` and nested `children`) (`datawrapper/__main__.py:1428`).
- `BaseChart.create(access_token=..., folder_id=...)` already forwards `folder_id` to `POST /v3/charts` (`datawrapper/charts/base.py:615`).
- `BaseChart.get()` caches the `Datawrapper` client on `instance._client`, which we reuse to avoid opening a second auth session (`datawrapper/charts/base.py:547`).

Important gap: `BaseChart` does **not** declare `folder_id` / `team_id` as Pydantic fields, so `chart.model_dump()` silently drops them. `get_chart` must fetch raw metadata once via the underlying client to surface these. `BaseChart.update()` also doesn't send `folderId`, so moves use the dedicated `client.move_chart()` method.

## Tool changes

### 1. `get_chart` — add `folder_id`, `team_id`, `folder_path`

File: [datawrapper_mcp/handlers/retrieve.py](../../datawrapper_mcp/handlers/retrieve.py)

- After `chart = get_chart(chart_id, access_token=token)`, issue one extra `chart._client.get(f"{chart._client._CHARTS_URL}/{chart_id}")` to recover the raw `folderId`, `teamId` fields the Pydantic model discards.
- Add top-level keys `folder_id` (int or null) and `team_id` (str or null) alongside the existing `chart_id` / `title` / `public_url` / `edit_url`. Keep them flat, not nested under `config`, so the LLM doesn't have to dig.
- When `folder_id` is non-null, also call `chart._client.get_folders()` once, walk the tree, and return `folder_path` like `"CFR / 2026 / Cuba"` (separator: `" / "`). When the chart is at the root (`folder_id is None`), omit `folder_path` and skip the `get_folders` call — keeps root-level reads cheap.
- Put the tree walker + path resolver in `handlers/folders.py` (see §4) so `list_folders` reuses the flattener.

File: [datawrapper_mcp/types.py](../../datawrapper_mcp/types.py) — no change to `GetChartArgs` (no new caller-facing arg; `folder_path` is always computed when a folder exists).

File: [datawrapper_mcp/server.py](../../datawrapper_mcp/server.py) (`get_chart` tool, around line 403) — update the docstring to document the new response fields.

### 2. `create_chart` — accept `folder_id`

File: [datawrapper_mcp/handlers/create.py](../../datawrapper_mcp/handlers/create.py) (line 44)

Change `chart.create(access_token=token)` → `chart.create(access_token=token, folder_id=arguments.get("folder_id"))`. The library already accepts this param.

File: [datawrapper_mcp/types.py](../../datawrapper_mcp/types.py) — add `folder_id: NotRequired[int]` to `CreateChartArgs`.

File: [datawrapper_mcp/server.py](../../datawrapper_mcp/server.py) (`create_chart` tool, around line 167) — add `folder_id: int | None = None` to the tool signature; forward into `args` when provided; document in the docstring.

### 3. `update_chart` — accept `folder_id` (including folder-only moves)

File: [datawrapper_mcp/handlers/update.py](../../datawrapper_mcp/handlers/update.py)

`BaseChart.update()` does **not** accept `folder_id` (`datawrapper/charts/base.py:658` calls `client.update_chart(...)` without it). To move the chart, call `chart._client.move_chart(chart_id, folder_id)`. Reusing `chart._client` avoids a second auth session.

Allow folder-only moves: if the caller passes `folder_id` with no `data` and no `chart_config`, skip `chart.update()` entirely and call `move_chart` only. This matches the REST API (move is its own PATCH endpoint) and avoids a redundant metadata PATCH.

If the caller passes both a config/data change and `folder_id`, run `chart.update()` first, then `move_chart` — two PATCH calls. The preview export continues to run on success.

File: [datawrapper_mcp/types.py](../../datawrapper_mcp/types.py) — add `folder_id: NotRequired[int]` to `UpdateChartArgs`.

File: [datawrapper_mcp/server.py](../../datawrapper_mcp/server.py) (`update_chart` tool, around line 456) — add `folder_id: int | None = None` to the signature; forward into `arguments` when provided; update the "WHAT YOU CAN UPDATE" list in the docstring.

### 4. `list_folders` (new tool)

New file: `datawrapper_mcp/handlers/folders.py`

```python
from datawrapper import Datawrapper
from mcp.types import TextContent
from ..types import ListFoldersArgs

async def list_folders(arguments: ListFoldersArgs) -> list[TextContent]:
    client = Datawrapper(access_token=arguments.get("access_token"))
    tree = client.get_folders()
    flat = _flatten(tree)  # → [{id, name, parent_id, team_id}, ...]
    return [TextContent(type="text", text=json.dumps(flat, indent=2))]
```

`_flatten` walks the Datawrapper folder tree (top-level `list` with nested `children`) into a flat list. Also export a `folder_path_for(folders, folder_id)` helper that `retrieve.py` reuses for the `folder_path` string.

Updates:
- [datawrapper_mcp/types.py](../../datawrapper_mcp/types.py) — add `ListFoldersArgs` TypedDict (only `access_token: NotRequired[str]`).
- [datawrapper_mcp/handlers/__init__.py](../../datawrapper_mcp/handlers/__init__.py) — export `list_folders`.
- [datawrapper_mcp/server.py](../../datawrapper_mcp/server.py) — register `@mcp.tool(readOnlyHint=True, idempotentHint=True)` wrapping the handler. Add `"list_folders"` to `BearerTokenMiddleware.inject_for` (around line 48).

## Files to modify

| File | Change |
|---|---|
| [datawrapper_mcp/types.py](../../datawrapper_mcp/types.py) | Add `folder_id` to `CreateChartArgs` / `UpdateChartArgs`; new `ListFoldersArgs`. |
| [datawrapper_mcp/handlers/retrieve.py](../../datawrapper_mcp/handlers/retrieve.py) | Extra raw-metadata fetch for `folder_id` / `team_id`; compute `folder_path` when in a folder. |
| [datawrapper_mcp/handlers/create.py](../../datawrapper_mcp/handlers/create.py) | Pass `folder_id` through to `chart.create()`. |
| [datawrapper_mcp/handlers/update.py](../../datawrapper_mcp/handlers/update.py) | Call `chart._client.move_chart()` when `folder_id` is provided; allow folder-only updates. |
| `datawrapper_mcp/handlers/folders.py` (new) | `list_folders` handler + tree flattener + `folder_path_for` helper. |
| [datawrapper_mcp/handlers/__init__.py](../../datawrapper_mcp/handlers/__init__.py) | Export `list_folders`. |
| [datawrapper_mcp/server.py](../../datawrapper_mcp/server.py) | Extend signatures / docstrings of `get_chart`, `create_chart`, `update_chart`; register `list_folders`; add to `BearerTokenMiddleware.inject_for`. |
| [tests/conftest.py](../../tests/conftest.py) | Mock `Datawrapper.get_folders`, `Datawrapper.move_chart`, and `chart._client.get(...)` for the raw-metadata call. |
| [tests/test_retrieve.py](../../tests/test_retrieve.py) | Assert `folder_id` / `team_id` / `folder_path` when chart is in a folder; assert no `get_folders()` call and null/missing `folder_path` at root. |
| [tests/test_create.py](../../tests/test_create.py) | Assert `chart.create` called with `folder_id` kwarg. |
| [tests/test_update.py](../../tests/test_update.py) | Assert `move_chart` called; add folder-only case (no `data` / `chart_config`) that skips `chart.update()`. |
| `tests/test_folders.py` (new) | `list_folders` flattening, tree-walk edge cases, auth propagation. |
| [AGENTS.md](../../AGENTS.md) | Add `list_folders` to the "Available MCP Tools" table; note `folder_id` on create / update. |
| [README.md](../../README.md) | Same — tools table at lines 44–55. |

## Reuse notes

- Auth already flows through `BearerTokenMiddleware` ([datawrapper_mcp/middleware.py](../../datawrapper_mcp/middleware.py) line 20); add `"list_folders"` to the inject set so `Authorization: Bearer …` forwards.
- Reuse `chart._client` (set by `BaseChart.get()`) for raw-metadata fetch, `move_chart`, and `get_folders` — avoids a second auth session.
- Conftest pattern is already `MagicMock`-based ([tests/conftest.py](../../tests/conftest.py)). Extend `mock_chart` with a `_client` attribute exposing `get`, `get_folders`, `move_chart`.
- `folder_id` type is `int` across the library (`datawrapper/__main__.py:598`). Use `int` in TypedDicts and tool signatures.

## Resolved design decisions

- **Response shape**: folder/team fields are top-level (`folder_id`, `team_id`, `folder_path`) on `get_chart`, alongside `chart_id` / `public_url`.
- **Folder-only moves**: `update_chart` accepts `folder_id` alone — no `data` or `chart_config` required. Handler skips `chart.update()` in that case and only calls `move_chart`.
- **`folder_path` policy**: always computed when `folder_id` is set (one `get_folders()` call per `get_chart` on a foldered chart). Skipped when the chart is at the root.
- **Path separator**: `" / "` (matches the example in the original request).

## Verification

1. **Unit tests** — `uv run pytest --cov -sv` (this is what CI runs; see `.github/workflows/continuous-deployment.yaml`). New coverage: `folder_id` round-trip on create, folder move via `update_chart`, folder-only update skips `chart.update()`, `list_folders` flattening, `folder_path` resolution, access-token propagation, root-level charts omit `folder_path`.
2. **Type check** — `uv run mypy datawrapper_mcp`.
3. **MCP Inspector smoke test** — start the server and issue `list_folders`, `create_chart` with a `folder_id`, `get_chart` on that chart (expect `folder_path` populated), `update_chart` with just `folder_id` (expect chart moved).
4. **Live API sanity check (optional)** — with a real `DATAWRAPPER_ACCESS_TOKEN`, confirm in the Datawrapper web UI that the chart lands in and moves between the expected folders.

## Possible future upstream changes (out of scope here)

If we want to drop the MCP-side workarounds later, the `palewire/datawrapper` library could carry folder state as first-class Pydantic data. These are **not** part of this PR — listed here so the option is on the record.

### Change 1 — stop dropping `folderId` / `teamId` on read

File in the library: `datawrapper/charts/base.py`

Declare the fields on `BaseChart`, next to the existing `chart_id` field (around line 243):

```python
folder_id: int | None = Field(default=None, alias="folderId")
team_id: str | None = Field(default=None, alias="teamId")
```

Confirm `populate_by_name=True` in `model_config` so both snake_case and the API's camelCase deserialize. With this change, `BaseChart.get()` populates `folder_id` / `team_id` from the raw response that it's already fetching (around line 575) — and `chart.model_dump()` includes them.

MCP impact: the `retrieve.py` handler stops doing the raw-metadata fetch and reads `chart.folder_id` / `chart.team_id` directly off `model_dump()`. Saves one API round-trip per `get_chart` call.

### Change 2 — let `BaseChart.update()` send `folderId`

File in the library: `datawrapper/charts/base.py` — `BaseChart.update()` (around line 658).

Pass `folder_id=self.folder_id` through to `client.update_chart(...)`.

File in the library: `datawrapper/__main__.py` — `Datawrapper.update_chart()` (around line 776).

Add `folder_id: int | None = None` kwarg and include `folderId` in the PATCH body when non-null (same pattern already used for `title`, `theme`). Not sending the field preserves the server-side folder.

MCP impact: the `update.py` handler replaces the `chart._client.move_chart(...)` call with `chart.folder_id = new; chart.update()`. Moves go through the canonical update path — no special case, no second PATCH when a move is combined with a metadata change.

### Sequencing if we pursue these later

1. PR the two library changes together, release a new `datawrapper` version.
2. In this repo: bump the pin in [pyproject.toml](../../pyproject.toml), delete the raw-metadata fetch in `retrieve.py`, and swap `move_chart` for attribute-assignment + `chart.update()` in `update.py`. Tests adjust to drop the `move_chart` / raw-metadata mocks.

Net effect: one fewer API call on every `get_chart`, and one fewer on every `update_chart` that bundles a move with other edits.
