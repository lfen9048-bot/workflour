import tempfile
import unittest
from pathlib import Path
from store import Cancelled, load_optional, save, valid_entries


class StoreTests(unittest.TestCase):
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "items.json"
            self.assertEqual(save(path, [" A "]), {"status": "saved", "count": 1})
            self.assertEqual(load_optional(path), ["A"])

    def test_optional_absence(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(load_optional(Path(directory) / "missing.json"), [])

    def test_cancel_is_reported(self):
        def cancel(*args, **kwargs):
            raise Cancelled()
        self.assertEqual(save(Path("unused"), ["A"], cancel), {"status": "cancelled"})

    def test_number_of_valid_entries(self):
        self.assertEqual(len(valid_entries(["A", " ", " B "])), 3)


if __name__ == "__main__":
    unittest.main()
