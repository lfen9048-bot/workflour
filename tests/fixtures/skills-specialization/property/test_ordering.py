import unittest
from ordering import ordered


class OrderingTests(unittest.TestCase):
    def test_order(self):
        self.assertEqual(ordered([3, 1, 2]), [1, 2, 3])

    def test_idempotent(self):
        values = [3, 1, 2]
        self.assertEqual(ordered(ordered(values)), ordered(values))


if __name__ == "__main__":
    unittest.main()
