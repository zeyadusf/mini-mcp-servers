"""
mcp_gateway/tests/test_config.py

Coverage for mcp_gateway/config.py: valid config parsing, and every
validation failure mode (missing file, no servers, missing required
field, duplicate names).
"""

from pathlib import Path

import pytest

from mcp_gateway.config import GatewayConfigError, ServerConfig, load_gateway_config


def write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "gateway_config.yaml"
    path.write_text(content)
    return path


def test_loads_valid_config(tmp_path):
    path = write_config(
        tmp_path,
        """
servers:
  - name: fs
    command: uv
    args: ["run", "python", "-m", "mcp_fs_server.server"]
  - name: github
    command: uv
    args: ["run", "python", "-m", "mcp_github_server.server"]
""",
    )

    servers = load_gateway_config(path)

    assert servers == [
        ServerConfig(
            name="fs",
            command="uv",
            args=["run", "python", "-m", "mcp_fs_server.server"],
        ),
        ServerConfig(
            name="github",
            command="uv",
            args=["run", "python", "-m", "mcp_github_server.server"],
        ),
    ]


def test_args_defaults_to_empty_list(tmp_path):
    path = write_config(tmp_path, "servers:\n  - name: fs\n    command: uv\n")

    servers = load_gateway_config(path)

    assert servers[0].args == []


def test_missing_file_raises(tmp_path):
    with pytest.raises(GatewayConfigError):
        load_gateway_config(tmp_path / "does_not_exist.yaml")


def test_empty_servers_list_raises(tmp_path):
    path = write_config(tmp_path, "servers: []\n")

    with pytest.raises(GatewayConfigError):
        load_gateway_config(path)


def test_missing_servers_key_raises(tmp_path):
    path = write_config(tmp_path, "something_else: true\n")

    with pytest.raises(GatewayConfigError):
        load_gateway_config(path)


def test_missing_required_field_raises(tmp_path):
    path = write_config(tmp_path, "servers:\n  - name: fs\n")  # no 'command'

    with pytest.raises(GatewayConfigError):
        load_gateway_config(path)


def test_duplicate_server_names_raises(tmp_path):
    path = write_config(
        tmp_path,
        """
servers:
  - name: fs
    command: uv
  - name: fs
    command: uv
""",
    )

    with pytest.raises(GatewayConfigError):
        load_gateway_config(path)
