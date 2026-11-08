"""Guarded SSH release pipeline for the static Course Hub site.

preflight: verifies every deployed source file against an immutable capture.
deploy: requires eleven explicit teacher reviews plus typed release consent,
        uploads a new versioned release, swaps a symlink atomically, and
        rolls back immediately if HTTPS smoke checks fail.
rollback: rolls back only an identified release using a deployment receipt.

No Wordpress/database/other domains are touched. OpenSSH must already trust
this server's host key; new keys are never automatically accepted.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

HOST_BASE='/var/www/course.skyed.org'
CURRENT=HOST_BASE+'/current'
RELEASES=HOST_BASE+'/releases'
SAFE_IP=re.compile(r'^\d{1,3}(?:\.\d{1,3}){3}$')
SAFE_PATH=re.compile(r'^[a-zA-Z0-9_./-]+$')
SAFE_HASH=re.compile(r'^[a-f0-9]{64}$')
APPROVAL_SENTENCE='I approve all 11 captured SkyED lessons and authorize publication of the specified Bright release candidate.'

class DeployError(Exception):pass


def hash_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def load_manifest(report:Path,candidate:Path)->dict:
    manifest=json.loads((report/'candidate-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema')!='skyed.course-hub.bright-root-candidate.v2.5.0':raise DeployError('INVALID_CANDIDATE_MANIFEST')
    files={**manifest['original_files'],**manifest['added_root_files']}
    files['index.html']=manifest['candidate_index_sha256']
    files.update({'lobby-preview/'+rel:sha for rel,sha in manifest['lobby_files'].items()})
    seen={p.relative_to(candidate).as_posix() for p in candidate.rglob('*') if p.is_file()}
    if set(files)!=seen:raise DeployError('CANDIDATE_FILE_SET_DRIFT')
    for rel,sha in files.items():
        if not SAFE_PATH.fullmatch(rel) or '..' in Path(rel).parts or not SAFE_HASH.fullmatch(sha):
            raise DeployError('UNSAFE_CANDIDATE_MEMBER: '+rel)
        if not (candidate/rel).is_file() or (candidate/rel).is_symlink() or hash_file(candidate/rel)!=sha:
            raise DeployError('CANDIDATE_FILE_CHANGED: '+rel)
    candidate_digest=hashlib.sha256(''.join(f'{rel} {h}\n' for rel,h in sorted(files.items())).encode('utf-8')).hexdigest()
    if candidate_digest!=manifest.get('candidate_tree_sha256'):raise DeployError('CANDIDATE_TREE_HASH_CHANGED')
    if manifest.get('reconciled_lesson_count')!=11 or manifest.get('media',{}).get('total_media',0)<400:
        raise DeployError('CONTENT_GATE_NOT_PASSED')
    return manifest


def check_approval(file:Path,manifest:dict,catalog:dict)->None:
    doc=json.loads(file.read_text(encoding='utf-8'))
    if doc.get('schema')!='skyed.teacher-review.v1' or doc.get('decision')!='APPROVED':
        raise DeployError('TEACHER_REVIEW_PENDING')
    if doc.get('candidate_tree_sha256')!=manifest.get('candidate_tree_sha256') or doc.get('source_catalog_sha256')!=manifest['source_catalog_sha256']:
        raise DeployError('TEACHER_REVIEW_WRONG_CANDIDATE')
    if len(str(doc.get('reviewer','')).strip())<3 or doc.get('attestation')!=APPROVAL_SENTENCE:
        raise DeployError('TEACHER_REVIEW_ATTESTATION_MISSING')
    reviews=doc.get('lesson_reviews')
    if not isinstance(reviews,list) or len(reviews)!=11:
        raise DeployError('ALL_11_LESSONS_REQUIRE_REVIEW')
    source_slugs={x['slug'] for x in catalog.get('lessons',[])}
    actual={x.get('slug') for x in reviews if isinstance(x,dict) and x.get('status')=='APPROVED'}
    if len(source_slugs)!=11 or source_slugs!=actual or len(actual)!=len(reviews):
        raise DeployError('LESSON_APPROVALS_INCOMPLETE_OR_DUPLICATED')


def process(cmd:list[str],data:str|None=None)->str:
    result=subprocess.run(cmd,input=data,text=True,capture_output=False if data is None else True,check=False)
    if result.returncode:raise DeployError('COMMAND_FAILED: '+cmd[0]+' exit='+str(result.returncode))
    return result.stdout or ''


def connection(ip:str):
    from ipaddress import IPv4Address
    try:IPv4Address(ip)
    except ValueError as error:raise DeployError('SERVER_MUST_BE_IPV4') from error
    return ['ssh','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15','root@'+ip]


def remote(ip:str,command:str,stdin:str|None=None)->str:
    return process(connection(ip)+[command],data=stdin)


def preflight(ip:str,manifest:dict):
    files=manifest['original_files']
    for rel in files:
        if not SAFE_PATH.fullmatch(rel) or '..' in Path(rel).parts:raise DeployError('UNSAFE_LEGACY_PATH')
    script=f'''set -eu
      test -L {CURRENT} || {{ echo CURRENT_NOT_SYMLINK; exit 2; }}
      test -d {RELEASES} || {{ echo RELEASE_DIRECTORY_MISSING; exit 2; }}
      readlink -f {CURRENT}
      cd {CURRENT}
      sha256sum --status -c - || {{ echo REMOTE_SOURCE_DRIFT; exit 3; }}
      printf 'SKYED_V250_REMOTE_SOURCE_HASHES=PASS\\n' '''
    checks=''.join(f'{sha}  {rel}\n' for rel,sha in sorted(files.items()))
    return remote(ip,script,checks)


def build_archive(candidate:Path,manifest:dict,archive:Path,checks:Path):
    files={**manifest['original_files'],**manifest['added_root_files']}
    files['index.html']=manifest['candidate_index_sha256']
    files.update({'lobby-preview/'+r:h for r,h in manifest['lobby_files'].items()})
    # Archive members are add-only relative to a version-specific release root.
    with tarfile.open(archive,'w:gz') as tar:
        for rel in sorted(files):tar.add(candidate/rel,arcname=rel,recursive=False)
    checks.write_text(''.join(f'{sha}  {rel}\n' for rel,sha in sorted(files.items())),encoding='ascii')


def smoke():
    with urllib.request.urlopen('https://course.skyed.org/',timeout=20) as response:
        raw=response.read(700_000)
        if b'assets/bright/app.js' not in raw:raise DeployError('PUBLIC_ROOT_NOT_BRIGHT')
    with urllib.request.urlopen('https://course.skyed.org/assets/bright/app.js',timeout=20) as response:
        raw=response.read(500_000)
        if b"const VERSION='2.5.0'" not in raw:raise DeployError('PUBLIC_BRIGHT_SCRIPT_MISSING')


def deploy(ip:str,candidate:Path,manifest:dict,receipt:Path):
    if receipt.exists():raise DeployError('RECEIPT_EXISTS_NO_OVERWRITE')
    previous=preflight(ip,manifest).strip().splitlines()[0]
    if (not SAFE_PATH.fullmatch(previous) or '\'' in previous or
            (not previous.startswith(RELEASES+'/') and not previous.startswith(HOST_BASE+'/'))):
        raise DeployError('UNEXPECTED_PREVIOUS_SYMLINK_TARGET')
    runid=secrets.token_hex(8)
    release=RELEASES+'/skyed-v2.5.0-'+runid
    archive=f'/tmp/skyed-v250-{runid}.tgz'
    checks=f'/tmp/skyed-v250-{runid}.sha256'
    with tempfile.TemporaryDirectory(prefix='skyed-publish-') as folder:
        tar=Path(folder)/'site.tgz';check=Path(folder)/'sha256sums.txt'
        build_archive(candidate,manifest,tar,check)
        scp=['scp','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15']
        process(scp+[str(tar),'root@'+ip+':'+archive])
        process(scp+[str(check),'root@'+ip+':'+checks])
        # Create the release; do not overwrite a previous candidate.
        remote(ip,f'''set -eu; test ! -e {release}; mkdir {release};
          tar -xzf {archive} -C {release}; cd {release};
          sha256sum --status -c {checks} || exit 3;
          rm -f {archive} {checks}; printf 'RELEASE_FILES_VERIFIED=PASS\\n' ''')
        # Pre-existing site must be unchanged between preflight and swap.
        # The old symlink is retained in the local receipt for rollback.
        remote(ip,f'''set -eu; test -L {CURRENT};
          test "$(readlink -f {CURRENT})" = '{previous}';
          ln -s '{release}' '{HOST_BASE}/.next-{runid}';
          mv -Tf '{HOST_BASE}/.next-{runid}' '{CURRENT}' ''')
    try:smoke()
    except Exception as error:
        try:
            remote(ip,f'''set -eu; test "$(readlink -f {CURRENT})" = '{release}';
              ln -s '{previous}' '{HOST_BASE}/.rollback-{runid}';
              mv -Tf '{HOST_BASE}/.rollback-{runid}' '{CURRENT}' ''')
        except Exception as rollback_error:
            raise DeployError('HTTP_SMOKE_FAILED_AND_ROLLBACK_UNCONFIRMED: '+str(rollback_error)) from error
        raise DeployError('HTTP_SMOKE_FAILED_ROLLBACK_COMPLETED: '+str(error)) from error
    receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps({'schema':'skyed.course-hub.deployment-receipt.v1','server_ip':ip,
       'previous_target':previous,'new_target':release,'candidate_index_sha256':manifest['candidate_index_sha256'],
       'status':'DEPLOYED_SMOKE_PASSED'},indent=2)+'\n',encoding='utf-8')
    print('SKYED_V250_PUBLICATION=SUCCESS_WITH_ROLLBACK_RECEIPT')


def rollback(ip:str,receipt:Path,phrase:str):
    if phrase!='ROLLBACK SKYED COURSE HUB':raise DeployError('EXPLICIT_ROLLBACK_CONFIRMATION_REQUIRED')
    doc=json.loads(receipt.read_text(encoding='utf-8'))
    if doc.get('schema')!='skyed.course-hub.deployment-receipt.v1' or doc.get('server_ip')!=ip:raise DeployError('WRONG_ROLLBACK_RECEIPT')
    previous=doc['previous_target'];current=doc['new_target']
    if not all(p.startswith(HOST_BASE+'/') and SAFE_PATH.fullmatch(p) for p in (previous,current)):
        raise DeployError('UNSAFE_ROLLBACK_TARGET')
    runid=secrets.token_hex(8)
    remote(ip,f'''set -eu; test -L {CURRENT};
       test "$(readlink -f {CURRENT})" = '{current}';
       test -d '{previous}';
       ln -s '{previous}' '{HOST_BASE}/.rollback-{runid}';
       mv -Tf '{HOST_BASE}/.rollback-{runid}' '{CURRENT}' ''')
    print('SKYED_V250_ROLLBACK=PASS')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=('preflight','deploy','rollback'))
    p.add_argument('--server-ip',required=True)
    p.add_argument('--candidate',type=Path)
    p.add_argument('--report',type=Path)
    p.add_argument('--source',type=Path)
    p.add_argument('--approval',type=Path)
    p.add_argument('--receipt',type=Path)
    p.add_argument('--confirm',default='')
    args=p.parse_args(argv)
    try:
        if args.mode=='rollback':
            if args.receipt is None:raise DeployError('RECEIPT_REQUIRED')
            rollback(args.server_ip,args.receipt,args.confirm);return 0
        if not args.candidate or not args.report or not args.source:raise DeployError('CANDIDATE_REPORT_SOURCE_REQUIRED')
        manifest=load_manifest(args.report,args.candidate)
        if args.mode=='preflight':preflight(args.server_ip,manifest);print('SKYED_V250_REMOTE_PREFLIGHT=PASS_READ_ONLY');return 0
        if args.confirm!='PUBLISH SKYED BRIGHT 2.5.0':raise DeployError('EXPLICIT_PUBLICATION_PHRASE_REQUIRED')
        if not args.approval or not args.receipt:raise DeployError('TEACHER_APPROVAL_AND_RECEIPT_REQUIRED')
        catalog=json.loads((args.source/'data/catalog.v1.json').read_text(encoding='utf-8-sig'))
        if hash_file(args.source/'data/catalog.v1.json')!=manifest['source_catalog_sha256']:
            raise DeployError('SOURCE_CATALOG_HASH_CHANGED')
        check_approval(args.approval,manifest,catalog)
        deploy(args.server_ip,args.candidate,manifest,args.receipt)
    except (DeployError,OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as error:
        print('SKYED_V250_DEPLOY=BLOCKED '+str(error),file=sys.stderr);return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
