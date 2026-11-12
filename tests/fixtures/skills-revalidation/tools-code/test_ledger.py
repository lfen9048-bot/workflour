import unittest

from ledger import canonical_label, preview


class PreviewTests(unittest.TestCase):
    def make_accounts(self):
        return {"a": {"balance": 7, "label": "A"}, "b": {"balance": 1, "label": "B"}}

    def test_preview_totals(self):
        result = preview(self.make_accounts(), [("a", "b", 2)])
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["accounts"]["a"]["balance"], 5)
        self.assertEqual(result["accounts"]["b"]["balance"], 3)

    def test_cancel(self):
        accounts = self.make_accounts()
        self.assertEqual(preview(accounts, [("a", "b", 2)], cancelled=True)["state"], "cancelled")
        self.assertEqual(accounts["a"]["balance"], 7)

    def test_unavailable_first(self):
        accounts = self.make_accounts()
        self.assertEqual(preview(accounts, [("b", "a", 2)])["state"], "unavailable")
        self.assertEqual(accounts["b"]["balance"], 1)

    def test_label(self):
        for raw, expected in [(" A  B ", "a b"), ("a b", "a b"), ("\tA\n", "a")]:
            self.assertEqual(canonical_label(raw), expected)
            self.assertEqual(canonical_label(canonical_label(raw)), canonical_label(raw))


if __name__ == "__main__":
    unittest.main(verbosity=2)
