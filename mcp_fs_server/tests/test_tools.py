"""
mcp_fs_server/tests/test_tools.py

Coverage for mcp_fs_server/tools.py. These test the pure functions
directly — no MCP protocol involved. server.py's wiring (the @mcp.tool
decorators, stdio transport) is deliberately NOT unit tested here;
that's verified manually via MCP Inspector per the project roadmap.
"""

from pathlib import Path

import pytest

from mcp_fs_server.tools import (
    EditNotUniqueError,
    FileTooLargeError,
    edit_file,
    list_directory,
    read_file,
    write_file,
)
from mcp_sandbox_core import (
    FileNotFoundInWorkspace,
    PathEscapesWorkspaceError,
    SensitiveFileBlocked,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------
# list_directory
# ---------------------------------------------------------------------


def test_list_directory_basic(workspace):
    (workspace / "b.txt").write_text("b")
    (workspace / "a.txt").write_text("a")
    (workspace / "sub").mkdir()

    result = list_directory(workspace, ".")

    # Directories first, then alphabetical.
    assert [e["name"] for e in result] == ["sub", "a.txt", "b.txt"]
    assert result[0]["type"] == "directory"
    assert result[0]["size"] is None
    assert result[1]["type"] == "file"
    assert result[1]["size"] == 1


def test_list_directory_hides_dotfiles_by_default(workspace):
    (workspace / ".hidden").write_text("secret-ish name, not content")
    (workspace / "visible.txt").write_text("x")

    result = list_directory(workspace, ".")

    assert [e["name"] for e in result] == ["visible.txt"]


def test_list_directory_shows_dotfiles_when_requested(workspace):
    (workspace / ".hidden").write_text("x")

    result = list_directory(workspace, ".", show_hidden=True)

    assert [e["name"] for e in result] == [".hidden"]


def test_list_directory_rejects_traversal(workspace):
    with pytest.raises(PathEscapesWorkspaceError):
        list_directory(workspace, "../")


def test_list_directory_on_file_raises(workspace):
    (workspace / "notadir.txt").write_text("x")

    with pytest.raises(NotADirectoryError):
        list_directory(workspace, "notadir.txt")


# ---------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------


def test_read_file_returns_content(workspace):
    (workspace / "notes.txt").write_text("hello")

    assert read_file(workspace, "notes.txt") == "hello"


def test_read_file_missing_raises(workspace):
    with pytest.raises(FileNotFoundInWorkspace):
        read_file(workspace, "missing.txt")


def test_read_file_sensitive_blocked(workspace):
    (workspace / ".env").write_text("SECRET=1")

    with pytest.raises(SensitiveFileBlocked):
        read_file(workspace, ".env")


def test_read_file_too_large_raises(workspace, monkeypatch):
    monkeypatch.setattr("mcp_fs_server.tools.MAX_READ_CHARS", 5)
    (workspace / "big.txt").write_text("this is more than 5 chars")

    with pytest.raises(FileTooLargeError):
        read_file(workspace, "big.txt")


# ---------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------


def test_write_file_creates_new_file(workspace):
    result = write_file(workspace, "out.txt", "hello world")

    assert (workspace / "out.txt").read_text() == "hello world"
    assert result["created_directories"] is False
    assert result["bytes_written"] == len(b"hello world")


def test_write_file_overwrites_existing(workspace):
    (workspace / "out.txt").write_text("old, much longer than new")

    write_file(workspace, "out.txt", "new")

    assert (workspace / "out.txt").read_text() == "new"


def test_write_file_creates_missing_parent_dirs(workspace):
    result = write_file(workspace, "a/b/c.txt", "nested")

    assert (workspace / "a" / "b" / "c.txt").read_text() == "nested"
    assert result["created_directories"] is True


def test_write_file_does_not_report_created_dirs_when_parent_exists(workspace):
    (workspace / "sub").mkdir()

    result = write_file(workspace, "sub/file.txt", "x")

    assert result["created_directories"] is False


def test_write_file_blocks_sensitive_file(workspace):
    with pytest.raises(SensitiveFileBlocked):
        write_file(workspace, ".env", "SECRET=1")

    assert not (workspace / ".env").exists()


# ---------------------------------------------------------------------
# edit_file
# ---------------------------------------------------------------------


def test_edit_file_replaces_unique_match(workspace):
    (workspace / "code.py").write_text("x = 1\ny = 2\n")

    result = edit_file(workspace, "code.py", "x = 1", "x = 100")

    assert (workspace / "code.py").read_text() == "x = 100\ny = 2\n"
    assert result["replacements"] == 1


def test_edit_file_zero_matches_raises(workspace):
    (workspace / "code.py").write_text("x = 1\n")

    with pytest.raises(EditNotUniqueError):
        edit_file(workspace, "code.py", "not_present", "y = 2")

    # File must be untouched.
    assert (workspace / "code.py").read_text() == "x = 1\n"


def test_edit_file_multiple_matches_raises(workspace):
    (workspace / "code.py").write_text("x = 1\nx = 1\n")

    with pytest.raises(EditNotUniqueError):
        edit_file(workspace, "code.py", "x = 1", "x = 2")

    # File must be untouched — ambiguous edit must not apply partially.
    assert (workspace / "code.py").read_text() == "x = 1\nx = 1\n"


def test_edit_file_missing_file_raises(workspace):
    with pytest.raises(FileNotFoundInWorkspace):
        edit_file(workspace, "missing.py", "a", "b")


def test_edit_file_sensitive_file_blocked(workspace):
    (workspace / ".env").write_text("SECRET=1")

    with pytest.raises(SensitiveFileBlocked):
        edit_file(workspace, ".env", "SECRET=1", "SECRET=2")
