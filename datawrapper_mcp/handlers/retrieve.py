"""Handler for retrieving chart information."""

import json
from typing import Any

from mcp.types import TextContent
from datawrapper import get_chart

from ..config import API_TYPE_TO_SIMPLIFIED
from ..types import GetChartArgs
from .folders import _fetch_all_folders, folder_path_for


async def get_chart_info(arguments: GetChartArgs) -> list[TextContent]:
    """Get information about an existing chart including complete configuration."""
    chart_id = arguments["chart_id"]
    token = arguments.get("access_token")

    # Get chart using factory function
    chart = get_chart(chart_id, access_token=token)

    # Get the complete config
    config = chart.model_dump()

    # Convert DataFrame to list of records if data exists
    if config.get("data") is not None and hasattr(config["data"], "to_dict"):
        config["data"] = config["data"].to_dict(orient="records")

    # Convert API type to simplified name for consistency with list_chart_types
    simplified_type = API_TYPE_TO_SIMPLIFIED.get(chart.chart_type, chart.chart_type)

    # BaseChart drops folderId/teamId from model_dump, so fetch raw metadata
    # once to surface them alongside the config.
    raw: dict[str, Any] = chart._client.get(f"{chart._client._CHARTS_URL}/{chart_id}")
    folder_id = raw.get("folderId")
    team_id = raw.get("teamId")

    result: dict[str, Any] = {
        "chart_id": chart.chart_id,
        "title": chart.title,
        "type": simplified_type,
        "folder_id": folder_id,
        "team_id": team_id,
        "config": config,
        "public_url": chart.get_public_url(),
        "edit_url": chart.get_editor_url(),
    }

    if folder_id is not None:
        folders = _fetch_all_folders(chart._client)
        path = folder_path_for(folders, folder_id)
        if path is not None:
            result["folder_path"] = path

    return [TextContent(type="text", text=json.dumps(result, indent=2))]
