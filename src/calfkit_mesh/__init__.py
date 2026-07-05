"""calfkit-mesh: a vendored, memory-only Kafka-compatible broker binary for local calfkit development.

This package ships a statically linked, prebuilt `tansu` broker binary inside
platform-specific wheels; see the bundled NOTICE file for upstream attribution.

The only public surface is :func:`resolve_broker_bin`, which locates a usable
`tansu` executable for calfkit's ``ck dev`` to spawn. It has zero runtime
dependencies and imports only the standard library, so ``import calfkit_mesh``
stays cheap.
"""

from __future__ import annotations

import importlib.resources
import os
import shutil
import sys
from pathlib import Path

__all__ = ["TansuBinaryNotFound", "resolve_broker_bin", "__version__", "TANSU_VERSION"]

#: Own semantic version of the calfkit-mesh package (NOT the wrapped Tansu version).
__version__ = "0.1.1"  # x-release-please-version

#: The upstream Tansu build calfkit-mesh wraps. Used to key the on-disk cache
#: path so that upgrading calfkit-mesh materialises a fresh binary. The value
#: encodes both the upstream workspace version ("0.6.0") and the short SHA of
#: the exact commit built from, because the broker is currently pinned to a
#: post-v0.6.0 main commit that includes consumer-group fixes not in any tagged
#: release. Once Tansu tags a release with these fixes this can return to a
#: plain "vX.Y.Z" form.
TANSU_VERSION = "v0.6.0-510f3e2"

#: Environment variable an operator may set to point at an explicit `tansu` binary.
ENV_VAR = "CALF_TANSU_BIN"

#: Basename of the executable as staged in the wheel / expected on ``PATH``.
_IS_WINDOWS = sys.platform == "win32"
_BIN_NAME = "tansu.exe" if _IS_WINDOWS else "tansu"

#: Name used for the on-disk materialized cache file (version-pinned, stable).
_CACHE_BIN_NAME = f"tansu-{TANSU_VERSION}{'.exe' if _IS_WINDOWS else ''}"


class TansuBinaryNotFound(RuntimeError):
    """Raised when no usable Tansu broker binary can be located."""


def _is_executable_file(path: str | os.PathLike[str]) -> bool:
    """Return True if *path* points at an existing, executable regular file."""
    return os.path.isfile(path) and os.access(path, os.X_OK)


def _bundled_binary() -> importlib.resources.abc.Traversable | None:
    """Return the wheel-bundled binary resource, or ``None`` when not present.

    Source installs (no wheel) legitimately have no bundled binary; callers fall
    through to the ``PATH`` lookup in that case.
    """
    try:
        resource = importlib.resources.files(__name__).joinpath("bin", _BIN_NAME)
    except (ModuleNotFoundError, FileNotFoundError):
        return None
    return resource if resource.is_file() else None


def _cache_dir() -> Path:
    """Return the stable per-user cache directory for materialized binaries."""
    return Path.home() / ".calfkit" / "bin"


def _materialize(resource: importlib.resources.abc.Traversable) -> str:
    """Copy the bundled *resource* to a stable cache path and return that path.

    The copy is streamed to a temporary sibling file and then atomically renamed
    into place, so concurrent resolves never observe a half-written binary and a
    version-pinned file that already exists is trusted and reused. The daemon
    calfkit spawns outlives the caller, so the returned path must persist -- this
    is why the binary is copied out of the (possibly temporary) package resource
    rather than handed back as an ``importlib.resources.as_file`` temp path.
    """
    cache_dir = _cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / _CACHE_BIN_NAME

    if not (dest.is_file() and dest.stat().st_size > 0):
        tmp = cache_dir / f".{_CACHE_BIN_NAME}.{os.getpid()}.tmp"
        try:
            with resource.open("rb") as src, open(tmp, "wb") as out:
                shutil.copyfileobj(src, out)
            os.replace(tmp, dest)
        finally:
            # Clean up the temp file if the rename never happened (e.g. on error).
            if tmp.exists():
                tmp.unlink()

    # Never gate on the wheel's exec bit -- it may not survive the zip round-trip.
    os.chmod(dest, 0o755)
    return str(dest)


def resolve_broker_bin() -> str:
    """Locate a usable Tansu broker binary and return its filesystem path.

    Resolution order:

    1. ``$CALF_TANSU_BIN`` -- used verbatim. If it is set but does not point at an
       executable file, raise :class:`TansuBinaryNotFound` (an explicit override
       is never silently ignored).
    2. The wheel-bundled binary -- materialized to a stable cache path
       (``~/.calfkit/bin/tansu-<version>``) and made executable, then returned.
    3. ``tansu`` on ``PATH`` via :func:`shutil.which`.

    :raises TansuBinaryNotFound: if none of the above resolve.
    """
    override = os.environ.get(ENV_VAR)
    if override:
        if not _is_executable_file(override):
            raise TansuBinaryNotFound(
                f"{ENV_VAR}={override!r} does not point at an executable file."
            )
        return override

    resource = _bundled_binary()
    if resource is not None:
        return _materialize(resource)

    on_path = shutil.which("tansu")
    if on_path:
        return on_path

    raise TansuBinaryNotFound(
        "Could not locate a Tansu broker binary. Tried, in order: "
        f"the ${ENV_VAR} environment variable, the calfkit-mesh bundled binary "
        f"(Tansu {TANSU_VERSION}), and 'tansu' on PATH. "
        "Install a platform wheel with `pip install calfkit-mesh`, set "
        f"${ENV_VAR} to an executable Tansu binary, or put 'tansu' on your PATH."
    )
