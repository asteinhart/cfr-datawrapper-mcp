# Changes from the upstream fork

This fork (`asteinhart/cfr-datawrapper-mcp`) is based on
[`palewire/datawrapper-mcp`](https://github.com/palewire/datawrapper-mcp). Every
commit in the history is upstream's; all the work below is in the current working
tree and not yet committed.

The headline change is **folder support**: the MCP server can now list and create
Datawrapper folders, place charts into folders on create/update, and report a
chart's folder location on retrieve. The rest is supporting tests, docs, and a
dependency-lock change.

> Generated 2026-06-30. To regenerate the underlying diff: `git diff` and
> `git status --porcelain` from the repo root.

---

## 1. New feature — folder support

### New MCP tools

| Tool | Type | What it does |
|------|------|--------------|
| `list_folders` | read-only | Lists every folder in the account as a flat array of `{id, name, parent_id, team_id}`, spanning the personal workspace and all teams. |
| `create_folder` | write | Creates a folder in the personal workspace (no args), inside a team (`team_id`), or as a subfolder (`parent_id`). Returns `{id, name, parent_id, team_id}`. |

### Changed MCP tools

| Tool | Change |
|------|--------|
| `create_chart` | New optional `folder_id` argument — chart is created in that folder, or at the account root when omitted. |
| `update_chart` | New optional `folder_id` argument — pass alone to do a folder-only move, or combine with `data`/`chart_config`. Folder-only moves skip the metadata `PATCH` and use the dedicated `move_chart` endpoint. |
| `get_chart` | Now returns `folder_id`, `team_id`, and (when the chart is in a folder) a human-readable `folder_path` like `"CFR / 2026 / Cuba"`. |

### Implementation notes

The `datawrapper` Python library already implements the underlying REST calls, so
the changes stay entirely in the MCP layer. Two quirks of `BaseChart` drove the
design:

- `BaseChart.model_dump()` drops `folderId`/`teamId`, so `get_chart` issues one
  extra raw metadata fetch (`chart._client.get(...)`) to recover them, reusing the
  client already cached on the chart instance (no second auth session).
- `BaseChart.update()` does not send `folderId`, so folder moves go through
  `client.move_chart(chart_id, folder_id)` rather than a config `PATCH`.

Root-level reads stay cheap: `get_folders()` is only called (to compute
`folder_path`) when the chart actually lives in a folder.

---

## 2. Files changed

### New files

| File | Purpose |
|------|---------|
| `datawrapper_mcp/handlers/folders.py` | Folder handlers (`list_folders`, `create_folder`) plus helpers `_fetch_all_folders`, `_walk_folders`, and `folder_path_for`. |
| `tests/test_folders.py` | Unit tests for the folder tree-flattener, path resolver, and both handlers (~297 lines, 14 tests). |
| `docs/proposals/folder-support.md` | Design proposal documenting the approach and the library calls relied on. |
| `.claude/settings.json`, `.claude/settings.local.json` | Claude Code harness config (local tooling — not a functional change to the server). |

### Modified source files

| File | Change |
|------|--------|
| `datawrapper_mcp/server.py` | Registers `list_folders` and `create_folder` MCP tools; adds `folder_id` parameter and docstrings to `create_chart`/`update_chart`; documents new `get_chart` return fields. (+116 lines) |
| `datawrapper_mcp/handlers/__init__.py` | Exports `create_folder` and `list_folders`. |
| `datawrapper_mcp/handlers/create.py` | Forwards `folder_id` to `chart.create()`. |
| `datawrapper_mcp/handlers/retrieve.py` | Surfaces `folder_id`/`team_id`/`folder_path` in the response. |
| `datawrapper_mcp/handlers/update.py` | Adds folder-move logic; only PATCHes metadata when data/config actually changed. |
| `datawrapper_mcp/types.py` | New `ListFoldersArgs` and `CreateFolderArgs` TypedDicts; `folder_id` added to `CreateChartArgs`/`UpdateChartArgs`. |

### Modified docs

| File | Change |
|------|--------|
| `README.md` | Tool table updated for folder support; adds `list_folders` row. |
| `AGENTS.md` | Tool table updated; adds `list_folders` and folder fields. |

### Modified tests (existing files)

`tests/conftest.py`, `tests/test_access_token.py`, `tests/test_mcp_client.py`,
`tests/test_preview.py`, `tests/test_retrieve.py`,
`tests/test_retrieve_type_conversion.py`, `tests/test_update.py` — all updated so
their mock charts expose a mocked `_client` (with `get`, `get_folders`,
`move_chart`) for the new raw-metadata and folder paths. New tests cover folder
forwarding on create, folder metadata on retrieve, and folder-only/combined moves
on update.

---

## 3. Dependency / lockfile change (review before committing)

`uv.lock` shows changes that look **environment-driven rather than intentional**,
so flag them before committing:

- `revision = 3` → `revision = 2` (lockfile format downgrade — likely a different
  local `uv` version rewriting the file).
- `fastmcp` pinned to `==3.2.4` (the latest upstream commit only bumped it to
  `3.2.0`) and `prefab-ui` to `==0.18.1`; adds the transitive `griffelib` dep.

`pyproject.toml` itself is unchanged, so the lock is out of sync with what
upstream committed. Consider regenerating the lock with the project's pinned `uv`
version, or excluding `uv.lock` from your commit, unless the bump is deliberate.

---

## 4. Summary diffstat

```
 AGENTS.md                              |   7 +-
 README.md                              |  21 +++---
 datawrapper_mcp/handlers/__init__.py   |   3 +
 datawrapper_mcp/handlers/create.py     |   2 +-
 datawrapper_mcp/handlers/retrieve.py   |  18 ++++-
 datawrapper_mcp/handlers/update.py     |  21 ++++--
 datawrapper_mcp/server.py              | 116 +++++++++++++++++++++++++++++++++
 datawrapper_mcp/types.py               |  17 +++++
 tests/conftest.py                      |  10 +++
 tests/test_access_token.py             |  10 ++-
 tests/test_mcp_client.py               |   6 ++
 tests/test_preview.py                  |  72 ++++++++++++++++++++
 tests/test_retrieve.py                 | 103 +++++++++++++++++++++++++++++
 tests/test_retrieve_type_conversion.py |   6 ++
 tests/test_update.py                   |  60 +++++++++++++++++
 uv.lock                                |  28 +++++---
 16 files changed, 470 insertions(+), 30 deletions(-)

 (untracked)
 datawrapper_mcp/handlers/folders.py
 tests/test_folders.py
 docs/proposals/folder-support.md
 .claude/
```
