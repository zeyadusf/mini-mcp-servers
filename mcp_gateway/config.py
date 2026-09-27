"""
mcp_gateway/config.py

Loads the Gateway's config file: which downstream MCP servers to
launch as subprocesses, and how.

Design decisions (see project ADR log for full reasoning):
  - Config lives in a YAML file, not hardcoded in server.py — same
    "config file for anything that changes without a code change"
    philosophy as global_config.yaml in TesseractCLI.
  - No env-var passthrough list in the config: each downstream server
    subprocess inherits the Gateway's FULL environment (os.environ),
    same as any normal subprocess would by default. Each server's own
    config.py (FS_SERVER_WORKSPACE, GITHUB_TOKEN, ...) is responsible
    for validating what IT needs from that environment — the Gateway
    doesn't need to know or care what each server requires.
  - Server names must be unique: they become the namespace prefix
    (see registry.py), so a collision here would silently merge two
    servers' tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class GatewayConfigError(Exception):
    """Raised for any structurally invalid gateway config."""


@dataclass
class ServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)


def load_gateway_config(path: Path) -> list[ServerConfig]:
    """
    Load and validate the gateway config file.

    Raises:
        GatewayConfigError: missing file, no servers defined, or
            duplicate server names.
    """
    if not path.is_file():
        raise GatewayConfigError(f"Gateway config file not found: {path}")

    raw = yaml.safe_load(path.read_text()) or {}
    servers_raw = raw.get("servers")
    if not servers_raw:
        raise GatewayConfigError(f"No 'servers' defined in {path}")

    servers = []
    for entry in servers_raw:
        try:
            servers.append(
                ServerConfig(
                    name=entry["name"],
                    command=entry["command"],
                    args=entry.get("args", []),
                )
            )
        except KeyError as e:
            raise GatewayConfigError(
                f"Server entry missing required field {e}: {entry}"
            ) from None

    names = [s.name for s in servers]
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        raise GatewayConfigError(
            f"Duplicate server name(s) in config: {sorted(duplicates)} — "
            "names become tool-namespace prefixes and must be unique."
        )

    return servers
