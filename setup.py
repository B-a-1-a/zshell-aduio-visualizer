from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

try:
    from setuptools.command.bdist_wheel import bdist_wheel
except ImportError:  # pragma: no cover - fallback for older build backends
    from wheel.bdist_wheel import bdist_wheel


ROOT = Path(__file__).parent.resolve()
HELPER_SOURCE_ROOT = ROOT / "termviz_helper"
HELPER_BINARY_NAME = "termviz-helper"
HELPER_APP_NAME = "termviz-helper.app"
MINIMUM_MACOS_WHEEL_TAG = "14_0"


class BuildTermvizHelper(build_py):
    description = "Build the bundled Swift helper and copy it into the package."

    def run(self) -> None:
        super().run()
        self._build_helper_bundle()

    def _build_helper_bundle(self) -> None:
        if os.environ.get("TERMVIZ_SKIP_HELPER_BUILD") == "1":
            self.announce("Skipping termviz helper build because TERMVIZ_SKIP_HELPER_BUILD=1", level=2)
            return
        if sys.platform != "darwin":
            raise RuntimeError("termviz can only be built on macOS unless TERMVIZ_SKIP_HELPER_BUILD=1 is set.")

        helper_binary = self._compile_helper_binary()
        bundle_root = Path(self.build_lib) / "termviz" / "helper" / HELPER_APP_NAME / "Contents"
        macos_dir = bundle_root / "MacOS"
        resources_dir = bundle_root / "Resources"
        macos_dir.mkdir(parents=True, exist_ok=True)
        resources_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(helper_binary, macos_dir / HELPER_BINARY_NAME)
        shutil.copy2(ROOT / "src" / "termviz" / "helper" / "Info.plist", bundle_root / "Info.plist")

        codesign = shutil.which("codesign")
        if codesign is not None:
            subprocess.run(
                [codesign, "--force", "--sign", "-", str(bundle_root.parent)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def _compile_helper_binary(self) -> Path:
        swift = shutil.which("swift")
        if swift is None:
            raise RuntimeError(
                "Swift toolchain not found. Install Xcode command line tools or set TERMVIZ_SKIP_HELPER_BUILD=1."
            )

        subprocess.run(
            [swift, "build", "-c", "release", "--package-path", str(HELPER_SOURCE_ROOT)],
            check=True,
            cwd=ROOT,
            env=os.environ.copy(),
        )

        output = HELPER_SOURCE_ROOT / ".build" / "release" / HELPER_BINARY_NAME
        if not output.exists():
            raise RuntimeError(f"Expected helper binary at {output}, but it was not built.")
        return output


class PlatformTaggedWheel(bdist_wheel):
    def finalize_options(self) -> None:
        super().finalize_options()
        self.root_is_pure = False

    def get_tag(self) -> tuple[str, str, str]:
        _, _, plat = super().get_tag()
        arch = plat.split("_")[-1]
        platform_tag = os.environ.get("TERMVIZ_WHEEL_PLAT_NAME", f"macosx_{MINIMUM_MACOS_WHEEL_TAG}_{arch}")
        return ("py3", "none", platform_tag)


setup(cmdclass={"bdist_wheel": PlatformTaggedWheel, "build_py": BuildTermvizHelper})
