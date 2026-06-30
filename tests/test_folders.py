"""Tests for the list_folders handler and folder-tree helpers."""

import json
from unittest.mock import MagicMock, patch

import pytest

from datawrapper_mcp.handlers.folders import (
    _fetch_all_folders,
    _walk_folders,
    create_folder,
    folder_path_for,
    list_folders,
)


class TestWalkFolders:
    """Unit tests for the recursive folder walker."""

    def test_empty_input_adds_nothing(self):
        out: list = []
        _walk_folders([], None, None, out)
        assert out == []

    def test_flattens_nested_tree(self):
        nodes = [
            {
                "id": 1,
                "name": "Root",
                "folders": [
                    {
                        "id": 2,
                        "name": "Child",
                        "folders": [{"id": 3, "name": "Grandchild"}],
                    },
                ],
            },
        ]
        out: list = []
        _walk_folders(nodes, None, None, out)
        assert out == [
            {"id": 1, "name": "Root", "parent_id": None, "team_id": None},
            {"id": 2, "name": "Child", "parent_id": 1, "team_id": None},
            {"id": 3, "name": "Grandchild", "parent_id": 2, "team_id": None},
        ]

    def test_team_id_propagates_to_descendants(self):
        nodes = [
            {
                "id": 10,
                "name": "TeamRoot",
                "folders": [{"id": 11, "name": "Inside"}],
            },
        ]
        out: list = []
        _walk_folders(nodes, None, "teamA", out)
        assert out[0]["team_id"] == "teamA"
        assert out[1]["team_id"] == "teamA"


class TestFolderPathFor:
    """Unit tests for folder_path_for helper."""

    def test_builds_path_with_default_separator(self):
        folders = [
            {"id": 1, "name": "CFR", "parent_id": None, "team_id": None},
            {"id": 7, "name": "2026", "parent_id": 1, "team_id": None},
            {"id": 42, "name": "Cuba", "parent_id": 7, "team_id": None},
        ]
        assert folder_path_for(folders, 42) == "CFR / 2026 / Cuba"

    def test_root_level_folder_returns_own_name(self):
        folders = [{"id": 1, "name": "Solo", "parent_id": None, "team_id": None}]
        assert folder_path_for(folders, 1) == "Solo"

    def test_missing_folder_returns_none(self):
        folders = [{"id": 1, "name": "X", "parent_id": None, "team_id": None}]
        assert folder_path_for(folders, 999) is None

    def test_custom_separator(self):
        folders = [
            {"id": 1, "name": "A", "parent_id": None, "team_id": None},
            {"id": 2, "name": "B", "parent_id": 1, "team_id": None},
        ]
        assert folder_path_for(folders, 2, separator=" > ") == "A > B"


class TestFetchAllFolders:
    """Unit tests for _fetch_all_folders — the single-call fetcher."""

    def test_personal_workspace_root_and_subtree(self):
        """Personal workspace root is emitted (null name) with its nested folders."""
        top_tree = {
            "list": [
                {
                    "type": "user",
                    "id": 1,
                    "name": None,
                    "folders": [{"id": 2, "name": "MyFolder", "folders": []}],
                },
            ]
        }
        fake_client = MagicMock()
        fake_client.get_folders.return_value = top_tree

        result = _fetch_all_folders(fake_client)

        fake_client.get.assert_not_called()
        assert result == [
            {"id": 1, "name": None, "parent_id": None, "team_id": None},
            {"id": 2, "name": "MyFolder", "parent_id": 1, "team_id": None},
        ]

    def test_team_stub_skipped_but_its_folders_emitted_with_team_id(self):
        """Team stubs (string id) are not emitted, but their folders carry team_id."""
        top_tree = {
            "list": [
                {
                    "type": "team",
                    "id": "myteam",
                    "name": "My Team",
                    "folders": [
                        {
                            "id": 10,
                            "name": "2026",
                            "folders": [{"id": 11, "name": "Cuba", "folders": []}],
                        },
                    ],
                },
            ]
        }
        fake_client = MagicMock()
        fake_client.get_folders.return_value = top_tree

        result = _fetch_all_folders(fake_client)

        fake_client.get.assert_not_called()
        assert result == [
            {"id": 10, "name": "2026", "parent_id": None, "team_id": "myteam"},
            {"id": 11, "name": "Cuba", "parent_id": 10, "team_id": "myteam"},
        ]

    def test_mixed_personal_and_team(self):
        """Personal workspace and team folders are merged into one flat list."""
        top_tree = {
            "list": [
                {
                    "type": "user",
                    "id": 999,
                    "name": None,
                    "folders": [{"id": 1000, "name": "Personal", "folders": []}],
                },
                {
                    "type": "team",
                    "id": "teamA",
                    "name": "Team A",
                    "folders": [{"id": 50, "name": "TeamFolder", "folders": []}],
                },
            ]
        }
        fake_client = MagicMock()
        fake_client.get_folders.return_value = top_tree

        result = _fetch_all_folders(fake_client)

        ids = [r["id"] for r in result]
        assert ids == [999, 1000, 50]
        assert next(r for r in result if r["id"] == 50)["team_id"] == "teamA"
        assert next(r for r in result if r["id"] == 1000)["team_id"] is None


class TestListFoldersHandler:
    """Integration tests for the list_folders async handler."""

    @pytest.mark.asyncio
    async def test_returns_flat_json_list(self):
        tree = {
            "list": [
                {
                    "type": "user",
                    "id": 1,
                    "name": "Root",
                    "folders": [{"id": 2, "name": "Child", "folders": []}],
                },
            ]
        }

        fake_client = MagicMock()
        fake_client.get_folders.return_value = tree

        with patch(
            "datawrapper_mcp.handlers.folders.Datawrapper", return_value=fake_client
        ) as dw_cls:
            result = await list_folders({"access_token": "secret-token"})

        dw_cls.assert_called_once_with(access_token="secret-token")
        fake_client.get_folders.assert_called_once_with()

        assert len(result) == 1
        assert result[0].type == "text"
        payload = json.loads(result[0].text)
        assert payload == [
            {"id": 1, "name": "Root", "parent_id": None, "team_id": None},
            {"id": 2, "name": "Child", "parent_id": 1, "team_id": None},
        ]

    @pytest.mark.asyncio
    async def test_falls_back_to_env_token(self, mock_api_token):
        fake_client = MagicMock()
        fake_client.get_folders.return_value = {"list": []}

        with patch(
            "datawrapper_mcp.handlers.folders.Datawrapper", return_value=fake_client
        ) as dw_cls:
            await list_folders({})

        dw_cls.assert_called_once_with(access_token="test_token_12345")


class TestCreateFolderHandler:
    """Integration tests for the create_folder async handler."""

    @pytest.mark.asyncio
    async def test_creates_top_level_personal_folder(self):
        fake_client = MagicMock()
        fake_client.create_folder.return_value = {
            "id": 500,
            "name": "New",
            "parentId": None,
            "teamId": None,
        }

        with patch(
            "datawrapper_mcp.handlers.folders.Datawrapper", return_value=fake_client
        ) as dw_cls:
            result = await create_folder(
                {"name": "New", "access_token": "secret-token"}
            )

        dw_cls.assert_called_once_with(access_token="secret-token")
        fake_client.create_folder.assert_called_once_with(
            name="New", parent_id=None, team_id=None
        )
        payload = json.loads(result[0].text)
        assert payload == {
            "id": 500,
            "name": "New",
            "parent_id": None,
            "team_id": None,
        }

    @pytest.mark.asyncio
    async def test_creates_subfolder_with_parent_and_team(self):
        fake_client = MagicMock()
        fake_client.create_folder.return_value = {
            "id": 501,
            "name": "Cuba",
            "parentId": 7,
            "teamId": "teamX",
        }

        with patch(
            "datawrapper_mcp.handlers.folders.Datawrapper", return_value=fake_client
        ):
            result = await create_folder(
                {
                    "name": "Cuba",
                    "parent_id": 7,
                    "team_id": "teamX",
                    "access_token": "secret-token",
                }
            )

        fake_client.create_folder.assert_called_once_with(
            name="Cuba", parent_id=7, team_id="teamX"
        )
        payload = json.loads(result[0].text)
        assert payload["id"] == 501
        assert payload["parent_id"] == 7
        assert payload["team_id"] == "teamX"

    @pytest.mark.asyncio
    async def test_falls_back_to_env_token(self, mock_api_token):
        fake_client = MagicMock()
        fake_client.create_folder.return_value = {
            "id": 1,
            "name": "x",
            "parentId": None,
            "teamId": None,
        }

        with patch(
            "datawrapper_mcp.handlers.folders.Datawrapper", return_value=fake_client
        ) as dw_cls:
            await create_folder({"name": "x"})

        dw_cls.assert_called_once_with(access_token="test_token_12345")
