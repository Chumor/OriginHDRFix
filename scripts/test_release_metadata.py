#!/usr/bin/env python3

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import prepare_release_metadata
import validate_release_metadata as metadata


ROOT = Path(__file__).resolve().parent.parent


class ReleaseMetadataTests(unittest.TestCase):
    def test_version_bump_needs_no_prepared_changelog_or_update_json(self) -> None:
        with tempfile.TemporaryDirectory(prefix="originhdrfix-release-") as directory:
            root = Path(directory)
            (root / "module").mkdir()
            (root / "update").mkdir()
            module = (ROOT / "module/module.prop").read_text(encoding="utf-8")
            values = metadata.read_module_prop()
            module = module.replace(f"version={values['version']}\n", "version=v2.0.0-rc.1\n")
            module = module.replace(f"versionCode={values['versionCode']}\n", "versionCode=20\n")
            (root / "module/module.prop").write_text(module, encoding="utf-8")
            history = "## What's Changed in 1.0.0\n\n* Existing release history.\n"
            (root / "update/CHANGELOG.md").write_text("# Changelog\n\n" + history, encoding="utf-8")
            notes = "## What's Changed in 2.0.0-rc.1\n\n* New HDR support.\n"
            notes_path = root / "notes.md"
            notes_path.write_text(notes, encoding="utf-8")

            with patch.object(metadata, "ROOT", root), contextlib.redirect_stdout(io.StringIO()):
                with patch.object(sys, "argv", ["validate", "--tag", "v2.0.0-rc.1"]):
                    metadata.main()
                prepare_release_metadata.prepare_release(notes_path)
                with patch.object(sys, "argv", ["validate", "--tag", "v2.0.0-rc.1", "--check-release"]):
                    metadata.main()

            changelog = (root / "update/CHANGELOG.md").read_text(encoding="utf-8")
            self.assertEqual(changelog, f"# Changelog\n\n{notes}\n{history}")
            update = json.loads((root / "update/update.json").read_text(encoding="utf-8"))
            self.assertEqual(update["version"], "v2.0.0-rc.1")
            self.assertEqual(update["versionCode"], 20)
            self.assertTrue(update["zipUrl"].endswith("/v2.0.0-rc.1/OriginHDRFix-v2.0.0-rc.1-20.zip"))
            self.assertEqual((root / "module/module.prop").read_text(encoding="utf-8"), module)

            # A second release must retain both earlier entries without regenerating them.
            module = module.replace("version=v2.0.0-rc.1\n", "version=v2.0.0\n")
            (root / "module/module.prop").write_text(module, encoding="utf-8")
            next_notes = "## What's Changed in 2.0.0\n\n* Stable release.\n"
            notes_path.write_text(next_notes, encoding="utf-8")
            with patch.object(metadata, "ROOT", root):
                prepare_release_metadata.prepare_release(notes_path)
            self.assertEqual(
                (root / "update/CHANGELOG.md").read_text(encoding="utf-8"),
                "# Changelog\n\n" + next_notes + "\n" + changelog.removeprefix("# Changelog\n\n"),
            )

    def test_source_validation_rejects_tag_mismatch(self) -> None:
        with patch.object(sys, "argv", ["validate", "--tag", "v999.0.0"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
                metadata.main()
            self.assertEqual(result.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
