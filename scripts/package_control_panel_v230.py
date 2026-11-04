"""Deterministic, SHA-256-pinned complete SkyED Control Panel + Lobby ZIP."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import zipfile

VERSION='2.3.0'
NAME='SkyED-ControlPanel-Lobby-v'+VERSION
ROOT=Path(__file__).resolve().parents[1]
SOURCE_FILES=(
 'skyed_control_panel.py',
 'skyed_control/__init__.py',
 'skyed_control/registry.py',
 'skyed_control/lobby_workspace.py',
 'skyed_lobby/scripts/control_server.py',
 'skyed_lobby/scripts/preview.py',
 'skyed_lobby/site/index.html',
 'skyed_lobby/site/assets/app.js',
 'skyed_lobby/site/assets/favicon.svg',
 'skyed_lobby/site/assets/media/README.txt',
 'skyed_lobby/site/assets/styles.css',
 'skyed_lobby/site/content/lobby.json',
 'skyed_lobby/tools/edit-lobby.html',
 'skyed_lobby/tools/editor.js',
 'skyed_lobby/tools/editor.css',
 'skyed_lobby/tests/test_control_lobby.py',
 'skyed_lobby/tests/test_browser_lobby.py',
 'scripts/Install-SkyED-ControlPanel-v2.3.0.ps1',
 'docs/CONTROL-PANEL-v2.3.0.md',
)

def build(output: Path, root: Path=ROOT) -> str:
    manifest={'version':VERSION,'kind':'additive-control-panel-and-private-lobby','files':{}}
    for name in SOURCE_FILES:
        raw=(root/name).read_bytes()
        if not raw or b'\0' in raw: raise ValueError('Invalid source file '+name)
        manifest['files'][name]=hashlib.sha256(raw).hexdigest()
    raw_manifest=(json.dumps(manifest,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w') as archive:
        for name in SOURCE_FILES+('member-sha256.json',):
            data=(root/name).read_bytes() if name!='member-sha256.json' else raw_manifest
            info=zipfile.ZipInfo(NAME+'/'+name,(2026,11,3,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.create_system=3
            info.external_attr=0o644<<16
            archive.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:raise RuntimeError('ZIP_CORRUPTED')
        assert len(z.namelist())==len(SOURCE_FILES)+1
        for name,sha in manifest['files'].items():
            if hashlib.sha256(z.read(NAME+'/'+name)).hexdigest()!=sha:
                raise RuntimeError('ZIP_SOURCE_HASH_MISMATCH:'+name)
    sha=hashlib.sha256(output.read_bytes()).hexdigest()
    print('SKYED_V230_PACKAGE=PASS members='+str(len(SOURCE_FILES))+' sha256='+sha+' bytes='+str(output.stat().st_size))
    return sha

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    build(args.out)
