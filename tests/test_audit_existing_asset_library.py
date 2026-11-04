"""Read-only existing production asset inventory regressions."""
from __future__ import annotations
import importlib.util
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from skyed.asset_library import make_record, save_index

SCRIPT=Path(__file__).resolve().parents[1]/"scripts/audit_existing_asset_library.py"
spec=importlib.util.spec_from_file_location("audit_existing_asset_library", SCRIPT)
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class AuditAssetLibraryTests(unittest.TestCase):
    def test_indexed_production_asset_is_found_without_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"asset_library"
            rec=make_record(root=root,asset_type="vocabulary",visual_class="single_object",
                            target="cat",pos="noun")
            p=root/rec.image_relpath
            p.parent.mkdir(parents=True,exist_ok=True)
            Image.new("RGB",(200,180),(10,60,80)).save(p)
            save_index(root,[rec])
            before=p.read_bytes()
            result=audit.inspect(root,["cat"])
            self.assertEqual(result["overall"],"PASS")
            self.assertEqual(result["statuses"][0]["selected_source"],"indexed")
            self.assertEqual(p.read_bytes(), before)
            self.assertEqual(result["statuses"][0]["dimensions"],[200,180])

    def test_missing_or_invalid_asset_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"asset_library"
            folder=root/"Pictures"
            folder.mkdir(parents=True)
            (folder/"cat.png").write_bytes(b"not an image")
            result=audit.inspect(root,["cat","dog"])
            self.assertEqual(result["overall"],"REVIEW_REQUIRED")
            self.assertEqual([x["status"] for x in result["statuses"]],
                             ["INVALID_IMAGE","MISSING"])

if __name__=="__main__":
    unittest.main()
