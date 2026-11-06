#!/usr/bin/env python3

import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = "/vendor/etc/vivo_config.ini"
CONFIG_INPUT = f"' {CONFIG_PATH} >"
INSTALL_SCRIPT = r"""
ui_print() { :; }
abort() { printf '%s\n' "$*" >&2; exit 1; }
set_perm_recursive() { :; }
set_perm() { :; }
MODPATH=$1
. "$2"
"""


class CustomizeScriptTests(unittest.TestCase):
    """Exercise customize.sh with a temporary vendor-config path and KSU stubs."""

    def install(self, config: str | None) -> tuple[subprocess.CompletedProcess, str | None]:
        with tempfile.TemporaryDirectory(prefix="originhdrfix-") as directory:
            root = Path(directory)
            config_path = root / "vendor_config.ini"
            if config is not None:
                config_path.write_text(config, encoding="utf-8")

            module_path = root / "module"
            module_path.mkdir()
            customize_path = root / "customize.sh"
            customize = (ROOT / "module/customize.sh").read_text(encoding="utf-8")
            self.assertEqual(customize.count(CONFIG_INPUT), 1)
            customize = customize.replace(
                CONFIG_INPUT,
                f"' {shlex.quote(str(config_path))} >",
                1,
            )
            customize_path.write_text(customize, encoding="utf-8")

            result = subprocess.run(
                ["sh", "-c", INSTALL_SCRIPT, "customize-test", str(module_path), str(customize_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            output_path = module_path / "system/vendor/etc/vivo_config.ini"
            output = output_path.read_text(encoding="utf-8") if output_path.exists() else None
            return result, output

    def test_rewrites_only_hdrui_in_target_section(self) -> None:
        source = (
            "[other]\n"
            "hdrui=false\n"
            "[vivo.hardware.display.xdr]\n"
            "hdrui=false\n"
            "is_support_zygote=0\n"
            "  hdrui = legacy\n"
            "mode=1\n"
            "[last]\n"
            "hdrui=false\n"
        )
        result, output = self.install(source)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            output,
            "[other]\n"
            "hdrui=false\n"
            "[vivo.hardware.display.xdr]\n"
            "hdrui=true\n"
            "is_support_zygote=1\n"
            "mode=1\n"
            "[last]\n"
            "hdrui=false\n",
        )

    def test_inserts_hdrui_when_missing(self) -> None:
        result, output = self.install("[vivo.hardware.display.xdr]\nmode=1\n")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            output,
            "[vivo.hardware.display.xdr]\n"
            "hdrui=true\n"
            "is_support_zygote=1\n"
            "mode=1\n",
        )

    def test_fails_when_target_section_is_missing(self) -> None:
        result, _ = self.install("[other]\nvalue=1\n")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Required vivo HDR configuration", result.stderr)

    def test_fails_when_source_config_is_missing(self) -> None:
        result, _ = self.install(None)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Required vivo HDR configuration", result.stderr)

    def test_refreshes_configstore_after_mount(self) -> None:
        script = (ROOT / "module/post-mount.sh").read_text(encoding="utf-8")

        self.assertEqual(script, "#!/system/bin/sh\n\nsetprop ctl.restart vivo-configstore-hal-1-0\n")


if __name__ == "__main__":
    unittest.main()
