#!/usr/bin/env python3

import shlex
import subprocess
import tarfile
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

    def test_rewrites_only_hdr_flags_in_target_section(self) -> None:
        source = (
            "[other]\n"
            "hdrui=false\n"
            "ultraHdr=false\n"
            "[vivo.hardware.display.xdr]\n"
            "hdrui=false\n"
            "ultraHdr=false\n"
            "is_support_zygote=0\n"
            "  hdrui = legacy\n"
            "  ultraHdr = legacy\n"
            "version=v2.0\n"
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
            "ultraHdr=false\n"
            "[vivo.hardware.display.xdr]\n"
            "hdrui=true\n"
            "ultraHdr=true\n"
            "is_support_zygote=1\n"
            "version=v2.0\n"
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
            "ultraHdr=true\n"
            "is_support_zygote=1\n"
            "mode=1\n",
        )

    def test_preserves_device_config_on_reinstall(self) -> None:
        for version in ("v2.0", "v3.0"):
            with self.subTest(version=version):
                source = (
                    "[vivo.hardware.display.xdr]\n"
                    f"version={version}\n"
                    "xdr_switch_time=1500\n"
                    "[vivo.hardware.display.xdr_video]\n"
                    "app_hdr=true\n"
                )
                result, output = self.install(source)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    output,
                    source.replace(
                        "[vivo.hardware.display.xdr]\n",
                        "[vivo.hardware.display.xdr]\n"
                        "hdrui=true\n"
                        "ultraHdr=true\n"
                        "is_support_zygote=1\n",
                    ),
                )
                reinstall, reinstalled = self.install(output)
                self.assertEqual(reinstall.returncode, 0, reinstall.stderr)
                self.assertEqual(reinstalled, output)

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

    def test_refreshes_configstore_on_uninstall(self) -> None:
        with tempfile.TemporaryDirectory(prefix="originhdrfix-uninstall-") as directory:
            for status in (0, 1):
                with self.subTest(setprop_status=status):
                    result = subprocess.run(
                        ["sh", "-c", 'setprop_status=$1; setprop() { printf "%s\\n" "$*"; return "$setprop_status"; }; . "$0"',
                         str(ROOT / "module/uninstall.sh"), str(status)],
                        cwd=directory,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    self.assertEqual(result.returncode, status, result.stderr)
                    self.assertEqual(result.stdout, "ctl.restart vivo-configstore-hal-1-0\n")


class ActionScriptTests(unittest.TestCase):
    def test_collects_supplemental_diagnostics_and_cleans_up(self) -> None:
        for dumpsys_status, tar_failure in ((0, False), (1, False), (0, True)):
            with self.subTest(dumpsys_status=dumpsys_status, tar_failure=tar_failure):
                with tempfile.TemporaryDirectory(prefix="originhdrfix-action-") as directory:
                    root = Path(directory)
                    module = root / "module"
                    device = root / "device"
                    downloads = root / "Download"
                    files = {
                        "vendor/etc/vivo_config.ini": b"stock HDR configuration",
                        "vendor/etc/displayconfig/display test.xml": b"<display />",
                        "sys/lcm/panel_name": b"test_panel",
                        "sys/lcm/panel_info": b"panel info",
                        "sys/lcm/error_info": b"no error",
                        "sys/lcm/bl_level": b"1200",
                        "system/etc/LcmConfig/LcmBrightnessConfig.json": b"stock panel calibration",
                        "system/etc/LcmConfig/XdrBrightnessConfig.json": b"{}",
                        "system/framework/vivo-framework.jar": b"vivo framework bytes",
                        "system/framework/vivo-services.jar": b"vivo services bytes",
                    }
                    module_files = {
                        "system.prop": b"HDR property overrides",
                        "system/vendor/etc/vivo_config.ini": b"installed HDR configuration",
                        "system/etc/LcmConfig/LcmBrightnessConfig.json": b"installed calibration",
                    }
                    for base, entries in ((device, files), (module, module_files)):
                        for name, content in entries.items():
                            path = base / name
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.write_bytes(content)
                    script = (ROOT / "module/action.sh").read_text(encoding="utf-8")
                    script = script.replace("\n  /vendor/", f"\n  {device}/vendor/")
                    script = script.replace("\n  /sys/", f"\n  {device}/sys/")
                    script = script.replace("\n  /system/", f"\n  {device}/system/")
                    script = script.replace("/sdcard/Download", str(downloads))
                    action = module / "action.sh"
                    action.write_text(script, encoding="utf-8")
                    command = 'dumpsys_status=$1; dumpsys() { printf "dumpsys %s\\n" "$*"; return "$dumpsys_status"; }; '
                    if tar_failure:
                        command += 'tar() { return 1; }; '
                    result = subprocess.run(
                        ["sh", "-c", command + '. "$0"', str(action), str(dumpsys_status)],
                        cwd=root,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    self.assertEqual(list(module.glob(".bugreport.*")), [])
                    reports = list(downloads.glob("OriginHDRFix_bugreport_*.tar.gz"))
                    if tar_failure:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertEqual(reports, [])
                        self.assertNotIn("Saved to:", result.stdout)
                        continue
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(len(reports), 1)
                    expected = {str(device / name).lstrip("/"): content for name, content in files.items()}
                    expected.update({"module/" + name: content for name, content in module_files.items()})
                    expected["display.txt"] = b"dumpsys display\n"
                    expected["surfaceflinger.txt"] = b"dumpsys SurfaceFlinger --display-id\n"
                    expected["surfaceflinger-layers.txt"] = b"dumpsys SurfaceFlinger --list\n"
                    with tarfile.open(reports[0]) as archive:
                        members = {item.name.removeprefix("./"): item for item in archive if item.isfile()}
                        self.assertEqual(set(members), set(expected))
                        for name, content in expected.items():
                            self.assertEqual(archive.extractfile(members[name]).read(), content)
                    self.assertIn(str(reports[0]), result.stdout)


if __name__ == "__main__":
    unittest.main()
