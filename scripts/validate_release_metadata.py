#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent.parent
NUMBER = r"(?:0|[1-9][0-9]*)"
PRERELEASE_ID = rf"(?:{NUMBER}|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
VERSION_PATTERN = (
    rf"{NUMBER}\.{NUMBER}\.{NUMBER}"
    rf"(?:-{PRERELEASE_ID}(?:\.{PRERELEASE_ID})*)?"
)
MODULE_VERSION_PATTERN = re.compile(rf"(?P<base>v{VERSION_PATTERN})")
TAG_PATTERN = re.compile(r"v" + VERSION_PATTERN)
REPOSITORY = "Chumor/OriginHDRFix"


def fail(message: str) -> None:
    print(f"Release metadata error: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_module_prop() -> dict[str, str]:
    values = {}
    for line in (ROOT / "module/module.prop").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator:
            fail(f"invalid module.prop line: {line}")
        values[key.strip()] = value.strip()
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag")
    parser.add_argument("--check-release", action="store_true")
    args = parser.parse_args()

    module = read_module_prop()
    version = module.get("version", "")
    module_id = module.get("id", "")
    module_name = module.get("name", "")
    raw_version_code = module.get("versionCode", "")
    module_version = MODULE_VERSION_PATTERN.fullmatch(version)
    if module_version is None:
        fail(
            "module.prop version must use vMAJOR.MINOR.PATCH[-PRERELEASE]: "
            f"{version!r}"
        )
    base_version = module_version.group("base")
    semver = base_version

    if not module_id:
        fail("module.prop has no id")
    if not module_name:
        fail("module.prop has no name")
    expected_update_url = (
        f"https://raw.githubusercontent.com/{REPOSITORY}/main/update/update.json"
    )
    if module.get("updateJson") != expected_update_url:
        fail(f"module.prop updateJson must be {expected_update_url}")
    if not raw_version_code.isdecimal() or int(raw_version_code) < 1:
        fail(
            f"module.prop versionCode must be a positive integer: {raw_version_code!r}"
        )
    changelog = (ROOT / "update/CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    heading = f"## {semver}"
    if heading not in changelog:
        fail(f"update/CHANGELOG.md must include a heading for version {version}")
    heading_index = changelog.index(heading)
    version_notes = []
    for line in changelog[heading_index + 1 :]:
        if line.startswith("## "):
            break
        version_notes.append(line)
    if not any(line.lstrip().startswith(("- ", "* ")) for line in version_notes):
        fail(f"update/CHANGELOG.md must include at least one list item under {heading}")

    if args.tag:
        if not TAG_PATTERN.fullmatch(args.tag):
            fail(f"release tag must use vMAJOR.MINOR.PATCH[-PRERELEASE]: {args.tag!r}")
        if args.tag != base_version:
            fail(
                f"release tag {args.tag!r} does not match module.prop version "
                f"{base_version!r}"
            )

    if args.check_release:
        update = json.loads((ROOT / "update/update.json").read_text(encoding="utf-8"))
        update_version = update.get("version", "")
        update_module_version = MODULE_VERSION_PATTERN.fullmatch(update_version)
        if update_module_version is None:
            fail(
                "update/update.json version must use vMAJOR.MINOR.PATCH[-PRERELEASE]: "
                f"{update_version!r}"
            )
        update_version_code = update.get("versionCode")
        if type(update_version_code) is not int or update_version_code < 1:
            fail("update/update.json versionCode must be a positive integer")
        if update_version != version or update_version_code != int(raw_version_code):
            fail("update/update.json version metadata does not match module/module.prop")

        zip_url_prefix = (
            f"https://github.com/{REPOSITORY}/releases/download/"
            f"{update_module_version.group('base')}/"
        )
        zip_url = update.get("zipUrl", "")
        asset_name = unquote(zip_url.removeprefix(zip_url_prefix))
        expected_asset_name = f"{module_name}-{base_version}-{raw_version_code}.zip"
        if not zip_url.startswith(zip_url_prefix) or asset_name != expected_asset_name:
            fail(f"update/update.json zipUrl must reference {zip_url_prefix}{expected_asset_name}")

        changelog_url = f"https://raw.githubusercontent.com/{REPOSITORY}/main/update/CHANGELOG.md"
        if update.get("changelog") != changelog_url:
            fail(f"update/update.json changelog must be {changelog_url}")

    if args.check_release:
        print("Stable release metadata is valid.")
    else:
        print("Release source metadata is valid.")


if __name__ == "__main__":
    main()
