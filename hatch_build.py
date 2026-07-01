"""Hatchling build hook that produces a non-pure, platform-tagged calfkit-mesh wheel.

calfkit-mesh wheels carry a prebuilt, statically linked ``tansu`` binary that CI
stages into ``src/calfkit_mesh/bin/`` before the build. This hook:

* force-includes that binary into the wheel under ``calfkit_mesh/bin/``,
* marks the wheel non-pure (``pure_python = False``), and
* sets an explicit platform tag (``py3-none-<platform>``) taken from the
  ``CALFKIT_MESH_PLAT_TAG`` environment variable.

An explicit tag is required -- not ``infer_tag`` -- because a single statically
linked musl Linux binary is published under BOTH a ``manylinux`` and a
``musllinux`` tag (pip's tag matching is libc-specific), which the build host's
inferred tag cannot express.

The hook errors if the binary is absent: a calfkit-mesh wheel without its broker
binary is not a valid artifact. Local development and the test suite import the
package straight from ``src/`` and never trigger this hook.
"""

from __future__ import annotations

import os
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

#: Environment variable CI sets per matrix leg, e.g. ``musllinux_1_1_x86_64``.
PLAT_TAG_ENV = "CALFKIT_MESH_PLAT_TAG"

#: Directory (relative to the project root) CI stages the built binary into.
_BIN_SUBDIR = ("src", "calfkit_mesh", "bin")

#: Accepted binary basenames (the Windows leg stages ``tansu.exe``).
_BIN_NAMES = ("tansu", "tansu.exe")


class CustomBuildHook(BuildHookInterface):
    """Force-include the staged Tansu binary and platform-tag the wheel."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict) -> None:
        binary = self._staged_binary()
        plat_tag = self._platform_tag()

        # Force-include bypasses normal file selection (the bin dir is gitignored),
        # placing the binary at calfkit_mesh/bin/<name> inside the wheel.
        dest = f"calfkit_mesh/bin/{binary.name}"
        build_data["force_include"][str(binary)] = dest

        build_data["pure_python"] = False
        build_data["tag"] = f"py3-none-{plat_tag}"

    def _staged_binary(self) -> Path:
        bin_dir = Path(self.root).joinpath(*_BIN_SUBDIR)
        for name in _BIN_NAMES:
            candidate = bin_dir / name
            if candidate.is_file():
                return candidate
        raise FileNotFoundError(
            f"No Tansu binary staged in {bin_dir} (looked for {', '.join(_BIN_NAMES)}). "
            "CI must build and copy the binary there before `uv build --wheel`."
        )

    def _platform_tag(self) -> str:
        plat_tag = os.environ.get(PLAT_TAG_ENV)
        if not plat_tag:
            raise RuntimeError(
                f"{PLAT_TAG_ENV} is not set. calfkit-mesh wheels require an explicit "
                "platform tag (e.g. manylinux2014_x86_64, musllinux_1_1_x86_64, "
                "macosx_11_0_arm64, win_amd64); set it before building the wheel."
            )
        return plat_tag
