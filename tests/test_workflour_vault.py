import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from workflour_paths import vault_path
spec = importlib.util.spec_from_file_location('vault_init', ROOT / 'scripts/init-workflour-vault.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class VaultTests(unittest.TestCase):
    def test_new_host_has_local_default_and_explicit_override(self):
        with patch.object(Path, 'home', return_value=Path('/home/demo')), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(vault_path(), Path('/home/demo/Documents/Obsidian/Workflour'))
            with patch.dict(os.environ, {'WORKFLOUR_OBSIDIAN_VAULT':'/tmp/my vault'}):
                self.assertEqual(vault_path(), Path('/tmp/my vault'))
            with patch.dict(os.environ, {'WORKFLOUR_OBSIDIAN_VAULT':'relative'}):
                with self.assertRaises(ValueError): vault_path()

    def test_initialization_preserves_existing_notes_and_has_real_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = Path(temp) / 'vault'
            first = module.initialize(vault)
            self.assertEqual(len(first['created']),4)
            home = vault / '首页.md'
            home.write_text('user progress\n')
            again = module.initialize(vault)
            self.assertEqual(again['created'],[])
            self.assertEqual(home.read_text(),'user progress\n')
            self.assertTrue((vault / '07-自动记录').is_dir())

    def test_existing_note_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = Path(temp) / 'vault'
            vault.mkdir()
            original = Path(temp) / 'user.md'
            original.write_text('unchanged')
            (vault / '首页.md').symlink_to(original)
            with self.assertRaises(ValueError): module.initialize(vault)
            self.assertEqual(original.read_text(),'unchanged')


if __name__ == '__main__': unittest.main()
