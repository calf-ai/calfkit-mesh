"""Unit tests for calfkit_mesh.resolve_broker_bin() and package hygiene.

These run without a real Tansu binary: the bundled-binary branch is exercised
with a fake executable fixture, and the on-disk cache is redirected at $HOME so
the real ~/.calfkit is never touched.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import calfkit_mesh
from calfkit_mesh import ENV_VAR, TANSU_VERSION, TansuBinaryNotFound, resolve_broker_bin


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    """Isolate every test: no override env var, HOME redirected, no real PATH tansu."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # Also cover Windows' home resolution, harmless on POSIX.
    monkeypatch.setenv("USERPROFILE", str(home))
    # Empty PATH so shutil.which("tansu") finds nothing unless a test opts in.
    monkeypatch.setenv("PATH", "")
    return home


def _make_fake_exec(path: Path, mode: int = 0o755) -> Path:
    """Create a fake executable file at *path* and chmod it to *mode*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"#!/bin/sh\nexit 0\n")
    path.chmod(mode)
    return path


# --------------------------------------------------------------------------- #
# (1) $CALF_TANSU_BIN override
# --------------------------------------------------------------------------- #


def test_env_override_wins(monkeypatch, tmp_path):
    exe = _make_fake_exec(tmp_path / "custom" / "tansu")
    monkeypatch.setenv(ENV_VAR, str(exe))
    assert resolve_broker_bin() == str(exe)


def test_env_override_returned_verbatim(monkeypatch, tmp_path):
    exe = _make_fake_exec(tmp_path / "custom" / "tansu")
    # A non-normalized path must come back exactly as provided.
    given = f"{exe.parent}{os.sep}.{os.sep}{exe.name}"
    monkeypatch.setenv(ENV_VAR, given)
    assert resolve_broker_bin() == given


def test_env_override_takes_precedence_over_bundled(monkeypatch, tmp_path):
    exe = _make_fake_exec(tmp_path / "custom" / "tansu")
    monkeypatch.setenv(ENV_VAR, str(exe))
    # Even with a bundled binary available, the explicit override must win.
    bundled = _make_fake_exec(tmp_path / "bundled" / "tansu")
    monkeypatch.setattr(calfkit_mesh, "_bundled_binary", lambda: bundled)
    assert resolve_broker_bin() == str(exe)


def test_env_override_missing_raises(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_VAR, str(tmp_path / "nope" / "tansu"))
    with pytest.raises(TansuBinaryNotFound, match=ENV_VAR):
        resolve_broker_bin()


def test_env_override_not_executable_raises(monkeypatch, tmp_path):
    plain = tmp_path / "plain" / "tansu"
    plain.parent.mkdir(parents=True)
    plain.write_bytes(b"not exec")
    plain.chmod(0o644)
    monkeypatch.setenv(ENV_VAR, str(plain))
    with pytest.raises(TansuBinaryNotFound):
        resolve_broker_bin()


def test_empty_env_override_falls_through(monkeypatch, tmp_path):
    # An empty string is treated as unset, so resolution continues.
    monkeypatch.setenv(ENV_VAR, "")
    on_path = _make_fake_exec(tmp_path / "pathdir" / "tansu")
    monkeypatch.setenv("PATH", str(on_path.parent))
    assert resolve_broker_bin() == str(on_path)


# --------------------------------------------------------------------------- #
# (2) bundled binary -> materialize to stable cache + chmod
# --------------------------------------------------------------------------- #


def test_bundled_materializes_to_cache(monkeypatch, tmp_path, _clean_env):
    bundled = _make_fake_exec(tmp_path / "wheel" / "bin" / "tansu")
    monkeypatch.setattr(calfkit_mesh, "_bundled_binary", lambda: bundled)

    resolved = resolve_broker_bin()

    expected = _clean_env / ".calfkit" / "bin" / f"tansu-{TANSU_VERSION}"
    assert resolved == str(expected)
    assert expected.is_file()
    assert expected.read_bytes() == bundled.read_bytes()


def test_bundled_resolved_is_executable(monkeypatch, tmp_path):
    # Simulate the wheel round-trip stripping the exec bit: source is mode 0o644.
    bundled = _make_fake_exec(tmp_path / "wheel" / "bin" / "tansu", mode=0o644)
    monkeypatch.setattr(calfkit_mesh, "_bundled_binary", lambda: bundled)

    resolved = Path(resolve_broker_bin())

    mode = resolved.stat().st_mode
    assert mode & stat.S_IXUSR
    assert mode & stat.S_IRUSR
    assert os.access(resolved, os.X_OK)


def test_bundled_reused_when_already_cached(monkeypatch, tmp_path, _clean_env):
    bundled = _make_fake_exec(tmp_path / "wheel" / "bin" / "tansu")
    monkeypatch.setattr(calfkit_mesh, "_bundled_binary", lambda: bundled)

    first = resolve_broker_bin()

    # Pre-existing, version-pinned cache file is trusted: a later source with
    # different bytes must NOT clobber it.
    changed = _make_fake_exec(tmp_path / "wheel2" / "bin" / "tansu")
    changed.write_bytes(b"#!/bin/sh\necho changed\n")
    monkeypatch.setattr(calfkit_mesh, "_bundled_binary", lambda: changed)

    second = resolve_broker_bin()
    assert first == second
    assert Path(second).read_bytes() != changed.read_bytes()


def test_bundled_leaves_no_temp_files(monkeypatch, tmp_path, _clean_env):
    bundled = _make_fake_exec(tmp_path / "wheel" / "bin" / "tansu")
    monkeypatch.setattr(calfkit_mesh, "_bundled_binary", lambda: bundled)

    resolve_broker_bin()

    cache_dir = _clean_env / ".calfkit" / "bin"
    leftovers = [p.name for p in cache_dir.iterdir() if p.name.startswith(".")]
    assert leftovers == []


# --------------------------------------------------------------------------- #
# (3) PATH fallback
# --------------------------------------------------------------------------- #


def test_path_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(calfkit_mesh, "_bundled_binary", lambda: None)
    on_path = _make_fake_exec(tmp_path / "pathdir" / "tansu")
    monkeypatch.setenv("PATH", str(on_path.parent))
    assert resolve_broker_bin() == str(on_path)


def test_bundled_preferred_over_path(monkeypatch, tmp_path, _clean_env):
    bundled = _make_fake_exec(tmp_path / "wheel" / "bin" / "tansu")
    monkeypatch.setattr(calfkit_mesh, "_bundled_binary", lambda: bundled)
    on_path = _make_fake_exec(tmp_path / "pathdir" / "tansu")
    monkeypatch.setenv("PATH", str(on_path.parent))

    resolved = resolve_broker_bin()
    assert resolved.startswith(str(_clean_env / ".calfkit" / "bin"))


# --------------------------------------------------------------------------- #
# (4) nothing resolves
# --------------------------------------------------------------------------- #


def test_all_absent_raises(monkeypatch):
    monkeypatch.setattr(calfkit_mesh, "_bundled_binary", lambda: None)
    with pytest.raises(TansuBinaryNotFound) as excinfo:
        resolve_broker_bin()
    message = str(excinfo.value)
    assert ENV_VAR in message
    assert TANSU_VERSION in message


# --------------------------------------------------------------------------- #
# package hygiene
# --------------------------------------------------------------------------- #


def test_version_metadata():
    assert calfkit_mesh.__version__ == "0.1.1"
    assert TANSU_VERSION == "v0.6.0-510f3e2"


def test_import_pulls_no_heavy_deps():
    """`import calfkit_mesh` must only pull in standard-library modules."""
    src_dir = str(Path(calfkit_mesh.__file__).resolve().parents[1])
    script = (
        "import sys\n"
        f"sys.path.insert(0, {src_dir!r})\n"
        "before = set(sys.modules)\n"
        "import calfkit_mesh\n"
        "added = {m.split('.')[0] for m in set(sys.modules) - before}\n"
        "added.discard('calfkit_mesh')\n"
        "leaked = sorted(m for m in added if m not in sys.stdlib_module_names)\n"
        "assert not leaked, leaked\n"
    )
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
