"""Deterministic complete v2.4.0 SkyED Control Panel / Bright Course Hub update.

Only manifest-allowlisted files enter the archive; unrelated local settings,
site media, server files, credentials and teacher records are never included.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

VERSION = '2.4.0'
DIRECTORY = 'SkyED-ControlPanel-Bright-v2.4.0'
KIND = 'additive-control-panel-and-private-lobby-integration'
BASE_MEMBERS = (
    'docs/CONTROL-PANEL-v2.3.3.md',
    'docs/RELEASE-CHECKPOINT.json',
    'scripts/Install-SkyED-ControlPanel-v2.3.3.ps1',
    'scripts/Start-SkyED-CourseHub-Integration-v2.3.3.ps1',
    'scripts/course_hub_integration.py',
    'scripts/package_control_panel_v233.py',
    'scripts/validate_lobby_content_v233.py',
    'skyed_control/__init__.py',
    'skyed_control/integration_workspace.py',
    'skyed_control/lobby_workspace.py',
    'skyed_control/registry.py',
    'skyed_control_panel.py',
    'skyed_lobby/scripts/control_server.py',
    'skyed_lobby/scripts/preview.py',
    'skyed_lobby/site/assets/app.js',
    'skyed_lobby/site/assets/favicon.svg',
    'skyed_lobby/site/assets/media/README.txt',
    'skyed_lobby/site/assets/styles.css',
    'skyed_lobby/site/content/lobby.json',
    'skyed_lobby/site/index.html',
    'skyed_lobby/tests/test_browser_lobby.py',
    'skyed_lobby/tests/test_control_lobby.py',
    'skyed_lobby/tools/edit-lobby.html',
    'skyed_lobby/tools/editor.css',
    'skyed_lobby/tools/editor.js',
    'tests/test_course_hub_integration.py',
    'tests/test_course_hub_integration_qt.py',
    'tests/test_install_v233.py',
    'tests/test_pilot_route_reconciliation.py',
)
ILLUSTRATIONS = (
    'hero-art', 'program-art', 'lesson-art',
    *(f'path-{i}' for i in range(1, 6)),
    *(f'topic-{i:02d}' for i in range(1, 11)),
)
NEW_MEMBERS = (
    'docs/VISUAL-IDENTITY-v2.4.0.md',
    'scripts/Install-SkyED-ControlPanel-v2.4.0.ps1',
    'scripts/Start-SkyED-CourseHub-Integration-v2.4.0.ps1',
    'scripts/package_control_panel_v240.py',
    'scripts/validate_lobby_content_v240.py',
    'tests/test_visual_v240.py',
    'tests/test_install_v240.py',
    'skyed_lobby/tests/test_visual_browser_v240.py',
)
MEMBERS = BASE_MEMBERS + tuple(f'skyed_lobby/site/assets/illustrations/{name}.webp' for name in ILLUSTRATIONS) + NEW_MEMBERS
assert len(MEMBERS) == len(set(MEMBERS)) == 55


def build(repo: Path, target: Path) -> str:
    repo = repo.resolve(strict=True)
    target = target.resolve()
    content: dict[str, bytes] = {}
    manifest: dict = {'version': VERSION, 'kind': KIND, 'files': {}}
    for rel in MEMBERS:
        if rel.startswith('/') or '\\' in rel or '..' in Path(rel).parts:
            raise ValueError('Invalid allowlisted member: ' + rel)
        source = repo / rel
        if source.is_symlink() or not source.is_file():
            raise FileNotFoundError('Required release member unavailable or unsafe: ' + rel)
        data = source.read_bytes()
        if rel.endswith('.webp'):
            if not (data.startswith(b'RIFF') and data[8:12] == b'WEBP'):
                raise ValueError('Invalid artwork bytes: ' + rel)
        else:
            if b'\0' in data:
                raise ValueError('Unexpected binary executable in text member: ' + rel)
            data = data.replace(b'\r\n', b'\n')
        content[rel] = data
        manifest['files'][rel] = hashlib.sha256(data).hexdigest()
    content['member-sha256.json'] = (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)+'\n').encode('utf-8')
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for rel, payload in sorted(content.items()):
            info = zipfile.ZipInfo(DIRECTORY+'/'+rel, (2026,11,8,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 3
            output.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(target) as check:
        if check.testzip() is not None:
            raise RuntimeError('ZIP CRC mismatch')
        for rel in MEMBERS:
            if hashlib.sha256(check.read(DIRECTORY+'/'+rel)).hexdigest() != manifest['files'][rel]:
                raise RuntimeError('ZIP member SHA drift: '+rel)
    value = hashlib.sha256(target.read_bytes()).hexdigest()
    print(f'SKYED_V240_PACKAGE=PASS members={len(MEMBERS)} sha256={value} bytes={target.stat().st_size}')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.repo,args.out)
