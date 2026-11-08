"""Deterministic complete SkyED Control Panel v2.5.0 update distribution."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from package_control_panel_v240 import MEMBERS as OLD_MEMBERS

VERSION='2.5.0'
DIRECTORY='SkyED-ControlPanel-Bright-v2.5.0'
KIND='additive-control-panel-and-private-lobby-integration'
ADDED=(
 'skyed_lobby/site/assets/illustrations/topic-11.webp',
 'scripts/course_hub_release.py',
 'scripts/course_hub_deploy.py',
 'scripts/package_control_panel_v250.py',
 'scripts/validate_lobby_content_v250.py',
 'scripts/Start-SkyED-CourseHub-Integration-v2.5.0.ps1',
 'scripts/Deploy-SkyED-CourseHub-v2.5.0.ps1',
 'scripts/Install-SkyED-ControlPanel-v2.5.0.ps1',
 'docs/BRIGHT-COURSE-HUB-v2.5.0.md',
 'tests/test_root_release_v250.py',
 'tests/test_editor_upload_v250.py',
 'skyed_lobby/tests/test_visual_browser_v250.py',
 'tests/test_install_v250.py',
)
MEMBERS=tuple(dict.fromkeys((*OLD_MEMBERS,*ADDED)))
assert len(MEMBERS)==len(OLD_MEMBERS)+len(ADDED)

def build(repo:Path,target:Path):
    repo=repo.resolve(strict=True);target=target.resolve()
    manifest={'version':VERSION,'kind':KIND,'files':{}}
    contents={}
    for rel in MEMBERS:
        if rel.startswith('/') or '\\' in rel or '..' in Path(rel).parts:raise ValueError('Unsafe member: '+rel)
        src=repo/rel
        if not src.is_file() or src.is_symlink():raise FileNotFoundError('Required member missing: '+rel)
        data=src.read_bytes()
        if rel.endswith('.webp'):
            if not data.startswith(b'RIFF') or data[8:12]!=b'WEBP':raise ValueError('Invalid WebP '+rel)
        else:
            if b'\x00' in data:raise ValueError('Unexpected binary source: '+rel)
            data=data.replace(b'\r\n',b'\n')
        contents[rel]=data
        manifest['files'][rel]=hashlib.sha256(data).hexdigest()
    contents['member-sha256.json']=(json.dumps(manifest,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as out:
        for rel,data in sorted(contents.items()):
            info=zipfile.ZipInfo(DIRECTORY+'/'+rel,(2026,11,8,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16
            info.create_system=3
            out.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for rel in MEMBERS:
            if hashlib.sha256(z.read(DIRECTORY+'/'+rel)).hexdigest()!=manifest['files'][rel]:
                raise RuntimeError('ZIP hash mismatch '+rel)
    sha=hashlib.sha256(target.read_bytes()).hexdigest()
    print(f'SKYED_V250_PACKAGE=PASS members={len(MEMBERS)} sha256={sha} bytes={target.stat().st_size}')
    return sha

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();build(args.repo,args.out)
