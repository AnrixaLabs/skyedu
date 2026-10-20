"""Existing production asset database is an interim source, never replace it."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from skyed.asset_library import make_record, save_index
from skyed.cards import _resolve_existing_library_picture, _materialize_local_asset_png
from unittest.mock import patch


class ExistingAssetDatabaseTests(unittest.TestCase):
    def test_approved_exact_index_record_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "assets"
            rec = make_record(root=root, asset_type="vocabulary", visual_class="single_object",
                              target="cat", pos="noun", theme="sky_tiles")
            path = root / rec.image_relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (300, 240), (100, 200, 140)).save(path)
            save_index(root, [rec])
            self.assertEqual(_resolve_existing_library_picture(root, "cat"), path)
            # Real existing image materializer uses the indexed database too.
            dest = Path(temp) / "reused.png"
            with patch("skyed.cards._local_asset_library_root", return_value=root):
                selected = _materialize_local_asset_png("cat", dest)
            self.assertEqual(selected, path)
            with Image.open(dest) as img:
                self.assertEqual(img.size, (300, 240))

    def test_unapproved_or_wrong_target_not_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "assets"
            rec = make_record(root=root, asset_type="vocabulary", visual_class="single_object",
                              target="dog", pos="noun")
            path = root / rec.image_relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (200, 200)).save(path)
            rec.approved = False
            save_index(root, [rec])
            self.assertIsNone(_resolve_existing_library_picture(root, "dog"))
            self.assertIsNone(_resolve_existing_library_picture(root, "cat"))

    def test_legacy_pictures_continues_to_work_without_an_index(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "assets"
            folder = root / "Pictures"
            folder.mkdir(parents=True)
            source = folder / "living_room.png"
            Image.new("RGB", (240, 240)).save(source)
            self.assertEqual(_resolve_existing_library_picture(root, "living room"), source)

    def test_index_path_traversal_cannot_escape_library(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            root = parent / "assets"
            outside = parent / "outside.png"
            Image.new("RGB", (200, 200)).save(outside)
            rec = make_record(root=root, asset_type="vocabulary", visual_class="single_object",
                              target="apple", pos="noun")
            rec.image_relpath = "../outside.png"
            save_index(root, [rec])
            self.assertIsNone(_resolve_existing_library_picture(root, "apple"))

    def test_ambiguous_index_retains_existing_loose_asset_behavior(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "assets"
            indexed = []
            for theme in ("sky", "fun_mission"):
                rec = make_record(root=root, asset_type="vocabulary", visual_class="single_object",
                                  target="ball", pos="noun", theme=theme)
                p = root / rec.image_relpath
                p.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (200, 200)).save(p)
                indexed.append(rec)
            save_index(root, indexed)
            legacy = root / "Pictures/ball.png"
            legacy.parent.mkdir(exist_ok=True)
            Image.new("RGB", (200, 200)).save(legacy)
            self.assertEqual(_resolve_existing_library_picture(root, "ball"), legacy)

if __name__ == "__main__":
    unittest.main()
