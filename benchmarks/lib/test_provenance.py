from __future__ import annotations

import re
import unittest

from provenance import plugin_tree_hash


class ProvenanceTests(unittest.TestCase):
    def test_plugin_tree_hash_is_full_hex_object_id(self) -> None:
        self.assertRegex(plugin_tree_hash(), re.compile(r"^[0-9a-f]{40}$"))


if __name__ == "__main__":
    unittest.main()
