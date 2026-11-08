"""Build, audit and preview a root-level Bright Course Hub candidate.

The captured site and original media are never modified. The replacement
homepage is staged with a byte-identical classic.html for intentional access
and rollback. SSH deployment is deliberately handled by a separate approval
gate, never by this staging tool.
"""
from __future__ import annotations
import argparse
import hashlib
import http.server
import json
import shutil
import sys
from pathlib import Path
import course_hub_integration as integration

RELEASE = '2.5.0'
ROOT_FILES = ('index.html', 'classic.html', 'content/lobby.json')
ALIAS_FILES = {'assets/app.js':'assets/bright/app.js',
               'assets/styles.css':'assets/bright/styles.css',
               'assets/favicon.svg':'assets/bright/favicon.svg'}

class ReleaseError(Exception):
    pass


def _hash(path: Path):
    return integration.digest(path)


def _new_file(root: Path, relative: str, data: bytes) -> None:
    target=root/relative
    if target.exists():
        raise ReleaseError('CANDIDATE_COLLISION: '+relative)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(data)


def _expected_html(raw: bytes) -> bytes:
    source=raw.decode('utf-8-sig')
    # Only static references change; the hash-route SPA remains the same.
    for old,new in ALIAS_FILES.items():
        if f'"{old}"' not in source:
            raise ReleaseError('BRIGHT_ASSET_REFERENCE_MISSING: '+old)
        source=source.replace(f'"{old}"',f'"{new}"')
    # A link from /lobby-preview/ to / used to silently enter the legacy app.
    # Both root and preview now use the same Bright hash-router.
    if 'href="/" class="back-link"' in source:
        raise ReleaseError('LEGACY_ROOT_NAVIGATION_NOT_FIXED')
    return source.encode('utf-8')


def build(source: Path,lobby: Path,output: Path,report_dir: Path, min_media: int = 400) -> dict:
    source=source.resolve(strict=True)
    lobby=lobby.resolve(strict=True)
    output=output.resolve()
    report_dir=report_dir.resolve()
    if output.exists() or report_dir.exists():
        raise ReleaseError('OUTPUT_EXISTS_NO_OVERWRITE')
    if source==output or source in output.parents or output in source.parents or lobby==output or lobby in output.parents:
        raise ReleaseError('UNSAFE_OUTPUT_LOCATION')
    # Use the existing guarded, catalog-aware stage engine. It validates 11
    # authentic lesson routes and preserves the original 433 media files.
    baseline=integration.stage(source,lobby,output,min_media=min_media)
    try:
        original_index=(output/'index.html').read_bytes()
        _new_file(output,'classic.html',original_index)
        bright=(output/'lobby-preview')
        patched_html=_expected_html((bright/'index.html').read_bytes())
        (output/'index.html').write_bytes(patched_html)
        for original,destination in ALIAS_FILES.items():
            data=(bright/original).read_bytes()
            if original=='assets/styles.css':
                # Stylesheet moves one directory deeper. Original images are
                # still adjacent to the original site's /assets/ hierarchy.
                data=data.replace(b"url('illustrations/",b"url('../illustrations/")
                data=data.replace(b'url("illustrations/',b'url("../illustrations/')
            _new_file(output,destination,data)
        for image in sorted((bright/'assets/illustrations').glob('*.webp')):
            _new_file(output,'assets/illustrations/'+image.name,image.read_bytes())
        # Editorial images are only added in the private editor workspace.
        # Place them beside the original /assets/media tree without replacing
        # any of the captured site's files.
        local_media=bright/'assets/media'
        if local_media.exists():
            for image in sorted(local_media.rglob('*')):
                if image.is_file():
                    rel=image.relative_to(bright).as_posix()
                    _new_file(output,rel,image.read_bytes())
        _new_file(output,'content/lobby.json',(bright/'content/lobby.json').read_bytes())
        originals={rel:sha for rel,sha in baseline['legacy_files'].items() if rel!='index.html'}
        new_files={p.relative_to(output).as_posix():_hash(p) for p in output.rglob('*') if p.is_file()
                   and p.relative_to(output).as_posix() not in baseline['legacy_files']
                   and not p.relative_to(output).as_posix().startswith('lobby-preview/')}
        report={'schema':'skyed.course-hub.bright-root-candidate.v2.5.0',
                'mode':'LOCAL_RELEASE_CANDIDATE_NO_REMOTE_MUTATION',
                'release':RELEASE,'original_files':baseline['legacy_files'],
                'added_root_files':new_files,'lobby_files':baseline['lobby_files'],
                'previous_index_sha256':baseline['legacy_files']['index.html'],
                'candidate_index_sha256':_hash(output/'index.html'),
                'source_catalog_sha256':baseline['source_catalog_sha256'],
                'source_content_sha256':baseline['source_content_sha256'],
                'reconciled_lesson_count':baseline['reconciled_lesson_count'],
                'media_references_checked':baseline['media_references_checked'],
                'media':baseline['media'],'required_media':min_media,'teacher_review_required':True,
                'production_authorized':False}
        report['candidate_tree_sha256']=hashlib.sha256(''.join(f'{rel} {h}\n' for rel,h in sorted({**report['original_files'], **report['added_root_files'], **{'lobby-preview/'+k:v for k,v in report['lobby_files'].items()},'index.html':report['candidate_index_sha256']}.items())).encode('utf-8')).hexdigest()
        verify(source,output,report)
        report_dir.mkdir(parents=True,exist_ok=False)
        (report_dir/'candidate-manifest.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        (report_dir/'teacher-review-template.json').write_text(json.dumps({
            'schema':'skyed.teacher-review.v1','candidate_index_sha256':report['candidate_index_sha256'],
            'source_catalog_sha256':report['source_catalog_sha256'],
            'candidate_tree_sha256':report['candidate_tree_sha256'],
            'reviewer':'','decision':'PENDING','lesson_reviews':[]},indent=2)+'\n',encoding='utf-8')
        print('SKYED_V250_ROOT_CANDIDATE=PASS files='+str(len(new_files))+' source_files='+str(len(originals)))
        print('SKYED_V250_NAVIGATION_ROOT=BRIGHT classic=/classic.html')
        print('SKYED_V250_REMOTE_WRITES=0')
        return report
    except BaseException:
        shutil.rmtree(output,ignore_errors=True)
        if report_dir.exists():shutil.rmtree(report_dir,ignore_errors=True)
        raise


def verify(source: Path,candidate: Path, report: dict)->None:
    source=source.resolve(strict=True);candidate=candidate.resolve(strict=True)
    if report.get('schema')!='skyed.course-hub.bright-root-candidate.v2.5.0':
        raise ReleaseError('UNSUPPORTED_CANDIDATE_MANIFEST')
    original=report['original_files'];root_new=report['added_root_files'];lobby=report['lobby_files']
    if original.get('index.html')!=_hash(source/'index.html') or _hash(candidate/'classic.html')!=original['index.html']:
        raise ReleaseError('CLASSIC_ROLLBACK_ORIGINAL_CHANGED')
    for rel,sha in original.items():
        if not (source/rel).is_file() or _hash(source/rel)!=sha:
            raise ReleaseError('SOURCE_FILE_CHANGED: '+rel)
        if rel!='index.html' and (not (candidate/rel).is_file() or _hash(candidate/rel)!=sha):
            raise ReleaseError('SOURCE_MEDIA_OR_FILE_MODIFIED: '+rel)
    for rel,sha in root_new.items():
        if not (candidate/rel).is_file() or _hash(candidate/rel)!=sha:
            raise ReleaseError('BRIGHT_ROOT_CHANGED: '+rel)
    if _hash(candidate/'index.html')!=report['candidate_index_sha256']:
        raise ReleaseError('BRIGHT_ROOT_INDEX_CHANGED')
    for rel,sha in lobby.items():
        if not (candidate/'lobby-preview'/rel).is_file() or _hash(candidate/'lobby-preview'/rel)!=sha:
            raise ReleaseError('PREVIEW_MEMBER_CHANGED: '+rel)
    actual={p.relative_to(candidate).as_posix() for p in candidate.rglob('*') if p.is_file()}
    expected=set(original)|set(root_new)|{'lobby-preview/'+p for p in lobby}
    if actual!=expected:
        raise ReleaseError('UNEXPECTED_OR_MISSING_CANDIDATE_FILES')
    root=(candidate/'index.html').read_text(encoding='utf-8')
    if 'assets/bright/app.js' not in root or '/classic.html' in root or 'href="/" class="back-link"' in root:
        raise ReleaseError('NAVIGATION_ENTRYPOINT_IS_NOT_BRIGHT')
    src=(candidate/'assets/bright/app.js').read_text(encoding='utf-8')
    if 'const VERSION=\'2.5.0\'' not in src or '#/lesson/' not in src:
        raise ReleaseError('BRIGHT_LESSON_ROUTER_MISSING')
    if report['media']['total_media']<report.get('required_media',400) or report['reconciled_lesson_count']!=11:
        raise ReleaseError('CONTENT_PROVENANCE_GATE_NOT_MET')
    print('SKYED_V250_RELEASE_VERIFY=PASS root=Bright original_media=preserved classic=available')


def preview(candidate: Path,port:int):
    candidate=candidate.resolve(strict=True)
    if not (candidate/'classic.html').is_file() or not (candidate/'assets/bright/app.js').is_file():
        raise ReleaseError('INCOMPLETE_ROOT_CANDIDATE')
    if not 0<=port<=65535:raise ReleaseError('INVALID_PORT')
    class ReadOnly(http.server.SimpleHTTPRequestHandler):
        def __init__(self,*args,**kw):super().__init__(*args,directory=str(candidate),**kw)
        def do_POST(self):self.send_error(405,'Read-only candidate preview')
        def list_directory(self,path):self.send_error(404);return None
        def end_headers(self):
            self.send_header('Cache-Control','no-store, max-age=0')
            self.send_header('X-Content-Type-Options','nosniff')
            super().end_headers()
    with http.server.ThreadingHTTPServer(('127.0.0.1',port),ReadOnly) as server:
        print(f'SKYED_V250_ROOT_PREVIEW=http://127.0.0.1:{server.server_address[1]}/',flush=True)
        server.serve_forever()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_subparsers(dest='mode',required=True)
    build_=modes.add_parser('build')
    for flag in ('source','lobby','output','report'):build_.add_argument('--'+flag,type=Path,required=True)
    build_.add_argument('--min-media',type=int,default=400)
    check=modes.add_parser('verify')
    for flag in ('source','candidate','report'):check.add_argument('--'+flag,type=Path,required=True)
    serve=modes.add_parser('preview');serve.add_argument('--candidate',type=Path,required=True);serve.add_argument('--port',type=int,default=0)
    args=parser.parse_args(argv)
    try:
        if args.mode=='build':build(args.source,args.lobby,args.output,args.report,args.min_media)
        elif args.mode=='verify':verify(args.source,args.candidate,json.loads((args.report/'candidate-manifest.json').read_text(encoding='utf-8')))
        else:preview(args.candidate,args.port)
        return 0
    except (ReleaseError,integration.GateError,ValueError,OSError,KeyError,TypeError) as error:
        print('SKYED_V250_RELEASE=BLOCKED '+str(error),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
