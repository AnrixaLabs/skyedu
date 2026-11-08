"""Image uploader is restricted to immutable, high-DPI local PNG/WebP."""
from __future__ import annotations
import io
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from zlib import compress,crc32
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skyed_lobby/scripts'))
import control_server

def png(width=800,height=600):
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',crc32(kind+data)&0xffffffff)
    ihdr=struct.pack('>IIBBBBB',width,height,8,2,0,0,0)
    pixels=b''.join(b'\x00'+b'\xff\xf2\xd7'*width for _ in range(height))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',ihdr)+chunk(b'IDAT',compress(pixels,9))+chunk(b'IEND',b'')

class LocalImageUploads(unittest.TestCase):
    def test_png_minimum_and_store_no_overwrite(self):
        data=png()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            a=control_server.store_image(data,'image/png',root)
            b=control_server.store_image(data,'image/png',root)
            self.assertEqual(a,b)
            self.assertEqual(a['width'],800)
            self.assertEqual(a['height'],600)
            self.assertEqual((root/'site'/a['path'].replace('assets/','assets/')).read_bytes(),data)

    def test_short_png_rejected(self):
        with self.assertRaisesRegex(ValueError,'at least 800x500'):
            control_server.inspect_image(png(200,200),'image/png')

    def test_html_and_forged_types_rejected(self):
        with self.assertRaises(ValueError):control_server.inspect_image(b'<svg onload=alert(1)>'*100,'image/png')
        with self.assertRaises(ValueError):control_server.inspect_image(png(),'image/svg+xml')

    def test_corrupt_png_crc_rejected(self):
        bad=bytearray(png());bad[29]^=0xff
        with self.assertRaisesRegex(ValueError,'CRC'):
            control_server.inspect_image(bytes(bad),'image/png')

    def test_symlink_upload_directory_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            try:(root/'site').symlink_to(Path(td),target_is_directory=True)
            except (OSError,NotImplementedError):self.skipTest('Windows runner cannot create symlinks without privilege')
            with self.assertRaisesRegex(ValueError,'Unsafe upload directory'):
                control_server.store_image(png(),'image/png',root)

if __name__=='__main__': unittest.main()
