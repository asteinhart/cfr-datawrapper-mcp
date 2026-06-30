"""Handler for updating Datawrapper charts."""

from typing import Any

from datawrapper import get_chart
from mcp.types import ImageContent

from ..types import UpdateChartArgs
from ..utils import json_to_dataframe
from .preview import try_export_preview


async def update_chart(
    arguments: UpdateChartArgs,
) -> tuple[dict[str, Any], list[ImageContent]]:
    """Update an existing chart's data or configuration.

    Returns:
        A tuple of (metadata_dict, preview_images).
    """
    chart_id = arguments["chart_id"]
    token = arguments.get("access_token")
    folder_id = arguments.get("folder_id")

    has_data = "data" in arguments
    has_config = "chart_config" in arguments

    # Get chart using factory function - returns correct Pydantic class instance
    chart = get_chart(chart_id, access_token=token)

    # Update data if provided
    if has_data:
        df = json_to_dataframe(arguments["data"])
        chart.data = df

    # Update config if provided
    if has_config:
        # Directly set attributes on the chart instance
        # Pydantic will validate each assignment automatically due to validate_assignment=True
        try:
            # Build a mapping of aliases to field names
            alias_to_field = {}
            for field_name, field_info in chart.model_fields.items():
                # Add the field name itself
                alias_to_field[field_name] = field_name
                # Add any aliases
                if field_info.alias:
                    alias_to_field[field_info.alias] = field_name

            for key, value in arguments["chart_config"].items():
                # Convert alias to field name if needed
                field_name = alias_to_field.get(key, key)
                setattr(chart, field_name, value)

        except Exception as e:
            raise ValueError(
                f"Invalid chart configuration: {str(e)}\n\n"
                f"Use get_chart_schema to see the valid schema for this chart type. "
                f"Only high-level Pydantic fields are accepted."
            )

    # Only call chart.update() when there's actually a data/config change.
    # Folder-only moves go through the dedicated move_chart endpoint — there's
    # no point issuing a redundant metadata PATCH.
    if has_data or has_config:
        chart.update(access_token=token)

    if folder_id is not None:
        # BaseChart.update() does not send folderId, so moves go through the
        # dedicated PATCH endpoint. Reuse chart._client (populated by
        # BaseChart.get) to avoid opening a second auth session.
        chart._client.move_chart(chart_id, folder_id)

    metadata: dict[str, Any] = {
        "chart_id": chart.chart_id,
        "title": chart.title,
        "edit_url": chart.get_editor_url(),
    }

    images: list[ImageContent] = []
    preview = try_export_preview(chart, access_token=token)
    if preview:
        images.append(preview)

    return metadata, images
