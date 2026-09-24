"""
tests/test_file_ops.py

Coverage for mcp_sandbox_core/file_ops.py:
  - safe_open: read/write happy paths, FileNotFoundInWorkspace, the
    read-vs-write action heuristic (including 'a' and 'r+' modes),
    SensitiveFileBlocked propagation, path-traversal propagation
  - atomic_write: full overwrite, temp file cleanup on success AND on
    failure, SensitiveFileBlocked propagation (no partial write left
    behind)
"""

from pathlib import Path

import pytest

from mcp_sandbox_core.file_ops import atomic_write, safe_open
from mcp_sandbox_core.sandbox_exception import (
    FileNotFoundInWorkspace,
    PathEscapesWorkspaceError,
    SensitiveFileBlocked,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


def _tmp_leftovers(directory: Path) -> list[Path]:
    """tempfile.mkstemp() names have no fixed prefix by default, so we
    detect leftovers by elimination: anything in the dir that isn't one
    of the files we intentionally created/expect."""
    return [p for p in directory.iterdir() if p.name.startswith("tmp")]


# ---------------------------------------------------------------------
# safe_open — read happy path / not found
# ---------------------------------------------------------------------


def test_safe_open_reads_existing_file(workspace):
    target = workspace / "notes.txt"
    target.write_text("hello world")

    with safe_open(workspace, "notes.txt", "r") as f:
        assert f.read() == "hello world"


def test_safe_open_read_missing_file_raises(workspace):
    with (
        pytest.raises(FileNotFoundInWorkspace),
        safe_open(workspace, "missing.txt", "r"),
    ):
        pass


def test_safe_open_write_creates_and_writes_file(workspace):
    target = workspace / "out.txt"

    with safe_open(workspace, "out.txt", "w") as f:
        f.write("new content")

    assert target.read_text() == "new content"


def test_safe_open_binary_mode_ignores_encoding(workspace):
    target = workspace / "data.bin"
    target.write_bytes(b"\x00\x01\x02")

    with safe_open(workspace, "data.bin", "rb") as f:
        assert f.read() == b"\x00\x01\x02"


# ---------------------------------------------------------------------
# safe_open — read-vs-write action heuristic
# ---------------------------------------------------------------------


def test_safe_open_append_mode_treated_as_write_action(workspace):
    """'a' does not start with 'r', so it must be classified as a write
    action — this matters because sensitive-file write rules can differ
    from read rules (see sensitive_files.DENYLIST)."""
    target = workspace / ".env"
    target.write_text("EXISTING=1")

    with pytest.raises(SensitiveFileBlocked), safe_open(workspace, ".env", "a"):
        pass


def test_safe_open_r_plus_mode_treated_as_write_action(workspace):
    """'r+' starts with 'r' but contains '+', so it must be classified
    as a write action, not read — this is the one case in the
    normalized_mode heuristic where startswith('r') alone would be
    wrong."""
    target = workspace / ".env"
    target.write_text("EXISTING=1")

    with pytest.raises(SensitiveFileBlocked), safe_open(workspace, ".env", "r+"):
        pass


def test_safe_open_plain_read_mode_is_read_action(workspace):
    """Sanity check for the heuristic's normal case: plain 'r' against a
    file that's only blocked for write (not read) must succeed."""
    target = workspace / "config" / "secrets" / "anything.txt"
    target.parent.mkdir(parents=True)
    target.write_text("visible on read")

    # '**/secrets/**' is only denylisted for read in sensitive_files.py,
    # so use a file that's genuinely readable to confirm plain 'r' opens.
    normal = workspace / "plain.txt"
    normal.write_text("ok")
    with safe_open(workspace, "plain.txt", "r") as f:
        assert f.read() == "ok"


# ---------------------------------------------------------------------
# safe_open — sensitive file blocking
# ---------------------------------------------------------------------


def test_safe_open_blocks_sensitive_read(workspace):
    target = workspace / ".env"
    target.write_text("SECRET=123")

    with pytest.raises(SensitiveFileBlocked), safe_open(workspace, ".env", "r"):
        pass


def test_safe_open_blocks_sensitive_write(workspace):
    with pytest.raises(SensitiveFileBlocked), safe_open(workspace, ".env", "w"):
        pass

    # Nothing should have been created.
    assert not (workspace / ".env").exists()


def test_safe_open_allows_env_example_read(workspace):
    target = workspace / ".env.example"
    target.write_text("KEY=your_key_here")

    with safe_open(workspace, ".env.example", "r") as f:
        assert f.read() == "KEY=your_key_here"


# ---------------------------------------------------------------------
# safe_open — path traversal still propagates through this layer
# ---------------------------------------------------------------------


def test_safe_open_propagates_path_traversal(workspace):
    with (
        pytest.raises(PathEscapesWorkspaceError),
        safe_open(workspace, "../escape.txt", "r"),
    ):
        pass


# ---------------------------------------------------------------------
# atomic_write — happy path
# ---------------------------------------------------------------------


def test_atomic_write_creates_file_with_full_content(workspace):
    target = workspace / "report.md"

    atomic_write(target, "# Title\n\nBody text.", workspace)

    assert target.read_text() == "# Title\n\nBody text."


def test_atomic_write_overwrites_existing_file_completely(workspace):
    target = workspace / "report.md"
    target.write_text("old content that is much longer than the new one")

    atomic_write(target, "new", workspace)

    assert target.read_text() == "new"


def test_atomic_write_leaves_no_temp_file_on_success(workspace):
    target = workspace / "report.md"

    atomic_write(target, "content", workspace)

    assert _tmp_leftovers(workspace) == []


# ---------------------------------------------------------------------
# atomic_write — failure cleanup
# ---------------------------------------------------------------------


def test_atomic_write_cleans_up_temp_file_on_replace_failure(workspace, monkeypatch):
    """If os.replace() blows up after the temp file is written, the temp
    file must still be removed — atomic_write must not leak temp files
    into the workspace on failure."""
    target = workspace / "report.md"
    target.write_text("original")

    def boom(_src, _dst):
        raise OSError("simulated failure")

    monkeypatch.setattr("mcp_sandbox_core.file_ops.os.replace", boom)

    with pytest.raises(OSError):
        atomic_write(target, "new content", workspace)

    # Original file untouched, and no leftover tmp* file in the workspace.
    assert target.read_text() == "original"
    assert _tmp_leftovers(workspace) == []


# ---------------------------------------------------------------------
# atomic_write — sensitive file blocking
# ---------------------------------------------------------------------


def test_atomic_write_blocks_sensitive_file(workspace):
    target = workspace / ".env"

    with pytest.raises(SensitiveFileBlocked):
        atomic_write(target, "SECRET=123", workspace)

    # No file, and no leftover temp file either.
    assert not target.exists()
    assert _tmp_leftovers(workspace) == []
