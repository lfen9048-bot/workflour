import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("prepare_workbench", Path(__file__).parents[1] / "scripts/prepare-workbench.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class WorkbenchPreparationTests(unittest.TestCase):
    def fixture(self, root):
        source = Path(root).resolve() / "source"
        values = {"package.json": '{"name":"openmausbot","version":"0.1.143","type":"module"}',
                  "cli.js": 'import "./dist-server/openmausbot.js";',
                  "dist-server/openmausbot.js": "// native CLI", "dist-server/index.js": "// native server",
                  "dist/index.html": '<html><head><script src="/assets/app.js"></script></head><body><div id="root"></div></body></html>',
                  "dist/assets/app.js": "// original app", "skills/example/SKILL.md": "original skill"}
        for name, value in values.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
        lock = {"package": "openmausbot", "version": "0.1.143", "sha256": {name: MOD.sha(source / name) for name in values}}
        return source, lock

    def test_prepare_keeps_source_and_native_assets_unchanged(self):
        with tempfile.TemporaryDirectory() as root:
            source, lock = self.fixture(root)
            output = Path(root) / "runtime"
            result = MOD.prepare(source, output, lock)
            self.assertFalse(result["deployed"])
            self.assertFalse((output / "cli.js").is_symlink())
            self.assertFalse((output / "dist-server/openmausbot.js").is_symlink())
            self.assertEqual((output / "dist-server/index.js").resolve(), source / "dist-server/index.js")
            self.assertEqual((output / "dist/assets").resolve(), source / "dist/assets")
            self.assertEqual((output / "skills").resolve(), source / "skills")
            self.assertEqual(MOD.verify_source(source, lock), source)
            index = (output / "dist/index.html").read_text()
            self.assertIn('<script src="/assets/app.js"></script>', index)
            self.assertIn('/workflour-workbench.css?v=', index)
            self.assertIn('/workflour-workbench.js?v=', index)
            self.assertNotIn('fetch(', index)
            self.assertEqual(MOD.prepare(source, output, lock), result)

    def test_refuses_changed_upstream_without_creating_runtime(self):
        with tempfile.TemporaryDirectory() as root:
            source, lock = self.fixture(root)
            (source / "dist-server/index.js").write_text("changed")
            output = Path(root) / "runtime"
            with self.assertRaises(ValueError):
                MOD.prepare(source, output, lock)
            self.assertFalse(output.exists())

    def test_existing_unmanaged_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            source, lock = self.fixture(root)
            output = Path(root) / "runtime"
            output.mkdir()
            sentinel = output / "keep.txt"
            sentinel.write_text("keep")
            with self.assertRaises(FileNotFoundError):
                MOD.prepare(source, output, lock)
            self.assertEqual(sentinel.read_text(), "keep")

    def test_runtime_copied_file_tamper_is_detected(self):
        with tempfile.TemporaryDirectory() as root:
            source, lock = self.fixture(root)
            output = Path(root) / "runtime"
            MOD.prepare(source, output, lock)
            (output / "dist/workflour-workbench.js").write_text("changed")
            with self.assertRaises(ValueError):
                MOD.verify_runtime(output, source, lock)

    def test_index_structure_is_checked(self):
        with self.assertRaises(ValueError):
            MOD.injected_index("<html></html>", "a", "b")
        with self.assertRaises(ValueError):
            MOD.injected_index("<head>workflour-workbench</head>", "a", "b")


if __name__ == "__main__":
    unittest.main()
