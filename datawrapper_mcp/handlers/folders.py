"""Handler for listing Datawrapper folders and computing folder paths."""

import json
import os
from typing import Any

from datawrapper import Datawrapper
from mcp.types import TextContent

from ..types import CreateFolderArgs, ListFoldersArgs


def _fetch_all_folders(client: Datawrapper) -> list[dict[str, Any]]:
    """Return a flat list of every folder across personal workspace and all teams.

    The /v3/folders endpoint returns one ``list`` containing the personal
    workspace root (``type: "user"``, int id) and one stub per team
    (``type: "team"``, string id). Each entry already has its full ``folders``
    subtree populated, so a single call is enough.
    """
    top_items: list[dict[str, Any]] = client.get_folders().get("list") or []

    flat: list[dict[str, Any]] = []
    for item in top_items:
        if item.get("type") == "team":
            # Team stub's id is a string — skip emitting it as a folder, but
            # propagate it as team_id for descendants.
            _walk_folders(item.get("folders") or [], None, item.get("id"), flat)
        else:
            # Personal workspace — emit the root (int id, null name) and descend.
            root_id = item.get("id")
            if root_id is None:
                continue
            flat.append(
                {
                    "id": root_id,
                    "name": item.get("name"),
                    "parent_id": None,
                    "team_id": None,
                }
            )
            _walk_folders(item.get("folders") or [], root_id, None, flat)

    return flat


def _walk_folders(
    nodes: list[dict[str, Any]],
    parent_id: int | None,
    team_id: str | None,
    out: list[dict[str, Any]],
) -> None:
    """Recursively flatten a list of folder nodes into ``out``."""
    for node in nodes:
        node_id = node.get("id")
        if node_id is None:
            continue
        out.append(
            {
                "id": node_id,
                "name": node.get("name"),
                "parent_id": parent_id,
                "team_id": team_id,
            }
        )
        _walk_folders(node.get("folders") or [], node_id, team_id, out)


def folder_path_for(
    folders: list[dict[str, Any]],
    folder_id: int,
    separator: str = " / ",
) -> str | None:
    """Return the human-readable path for ``folder_id``, or None if missing."""
    by_id = {f["id"]: f for f in folders}
    node = by_id.get(folder_id)
    if node is None:
        return None

    names: list[str] = []
    seen: set[int] = set()
    while node is not None:
        if node["id"] in seen:
            break
        seen.add(node["id"])
        names.append(str(node.get("name") or ""))
        parent_id = node.get("parent_id")
        if parent_id is None:
            break
        node = by_id.get(parent_id)

    return separator.join(reversed(names))


async def list_folders(arguments: ListFoldersArgs) -> list[TextContent]:
    """List all folders in the caller's Datawrapper account as a flat list."""
    token = arguments.get("access_token") or os.getenv("DATAWRAPPER_ACCESS_TOKEN")
    client = Datawrapper(access_token=token)
    flat = _fetch_all_folders(client)
    return [TextContent(type="text", text=json.dumps(flat, indent=2))]


async def create_folder(arguments: CreateFolderArgs) -> list[TextContent]:
    """Create a new folder in the caller's personal workspace or a team."""
    token = arguments.get("access_token") or os.getenv("DATAWRAPPER_ACCESS_TOKEN")
    client = Datawrapper(access_token=token)
    response = client.create_folder(
        name=arguments["name"],
        parent_id=arguments.get("parent_id"),
        team_id=arguments.get("team_id"),
    )
    result = {
        "id": response.get("id"),
        "name": response.get("name"),
        "parent_id": response.get("parentId"),
        "team_id": response.get("teamId"),
    }
    return [TextContent(type="text", text=json.dumps(result, indent=2))]
