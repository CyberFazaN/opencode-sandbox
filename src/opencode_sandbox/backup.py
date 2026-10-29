"""Cold, checksummed backups with safe symlinks and recoverable restore."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tarfile
import tempfile
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath

from . import core as c

SCHEMA = 3
COMPONENTS = {'workspace.tar.gz', 'home.tar.gz', 'system-image.tar'}
HOME_SKIPPED = '.home-skipped'  # helper's list of left-out sockets/FIFOs; removed before publication

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def _max_entries():
    return int(os.getenv('OPENCODE_SANDBOX_MAX_ARCHIVE_ENTRIES','2000000'))

def _members(tf):
    names=set(); limit=_max_entries()
    for member in tf:
        if len(names) >= limit:
            raise c.SandboxError(f'Archive has more than {limit} entries (OPENCODE_SANDBOX_MAX_ARCHIVE_ENTRIES)')
        normalized=member.name.removeprefix('./')
        if member.name in ('.','./') and member.isdir(): continue
        p=PurePosixPath(normalized)
        # Reject ambiguous tar names before any extractor sees them. GNU tar
        # and Python's pathlib do not normalize all path forms identically.
        raw_parts = normalized.split('/')
        if ("\x00" in normalized or "\\" in normalized or
            any(part in ('', '.', '..') for part in raw_parts) or
            member.name.startswith('/') or
            member.name.startswith('././')):
            raise c.SandboxError(f'Unsafe non-canonical archive path: {member.name}')
        if (not member.name or p.is_absolute() or '..' in p.parts or 
            not (member.isfile() or member.isdir() or member.issym() or member.islnk()) or
            normalized in names):
            raise c.SandboxError(f'Unsafe archive member: {member.name}')
        # Member names never reach a command line (Python unpack; GNU tar extracts the whole
        # archive), so names starting with '-' are ordinary files.
        if normalized in ('.', ''):
            raise c.SandboxError(f'Unsafe archive member: {member.name}')
        names.add(normalized)
        # Symlink targets are stored verbatim, also absolute ones and ones leaving the workspace
        # (a Python venv has bin/python -> /usr/bin/python): unpack() creates links last and
        # never writes through one, and the agent can create such links in the live workspace
        # anyway (D-022).
        if member.issym() and ("\x00" in member.linkname or "\\" in member.linkname or not member.linkname):
            raise c.SandboxError(f'Unsafe symlink target: {member.name}')
        if member.islnk():
            link=PurePosixPath(member.linkname.removeprefix('./'))
            if link.is_absolute() or '..' in link.parts or str(link) in ('', '.'):
                raise c.SandboxError(f'Unsafe hardlink: {member.name}')
        yield member

def _validate_archive(archive):
    with tarfile.open(archive,'r:gz') as tf:
        members=list(_members(tf))
    # Reject archive paths descending through any symlink, independent of order.
    links={m.name.removeprefix('./') for m in members if m.issym()}
    for m in members:
        p=PurePosixPath(m.name.removeprefix('./'))
        if any(str(parent) in links for parent in p.parents if str(parent)!='.'):
            raise c.SandboxError(f'Archive path through symlink: {m.name}')
    # Reject regular files used as parent paths (not only symlinks).
    nondirs={m.name.removeprefix('./') for m in members if not m.isdir()}
    for m in members:
        p=PurePosixPath(m.name.removeprefix('./'))
        if any(str(parent) in nondirs for parent in p.parents if str(parent)!='.'):
            raise c.SandboxError(f'Archive path through non-directory: {m.name}')
    paths={m.name.removeprefix('./'):m for m in members}
    for m in members:
        if m.islnk():
            target=paths.get(m.linkname.removeprefix('./'))
            if target is None or not target.isfile():
                raise c.SandboxError(f'Invalid hardlink target: {m.name}')
    return members

def unpack(archive,destination):
    members=_validate_archive(archive)
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    if any(destination.iterdir()): raise c.SandboxError('Restore destination must be empty')
    # Extract regular files/dirs first, then symlinks. Never follow symlinks on extraction.
    with tarfile.open(archive,'r:gz') as tf:
        for m in members:
            target=destination.joinpath(*PurePosixPath(m.name.removeprefix('./')).parts)
            if m.isdir(): target.mkdir(parents=True,exist_ok=True)
            elif m.isfile():
                target.parent.mkdir(parents=True,exist_ok=True)
                with tf.extractfile(m) as src, target.open('xb') as dst: shutil.copyfileobj(src,dst)
                target.chmod(m.mode & 0o777)
                os.utime(target,(m.mtime,m.mtime))
        for m in members:
            if m.islnk():
                target=destination.joinpath(*PurePosixPath(m.name.removeprefix('./')).parts)
                source=destination.joinpath(*PurePosixPath(m.linkname.removeprefix('./')).parts)
                target.parent.mkdir(parents=True,exist_ok=True)
                os.link(source,target,follow_symlinks=False)
        for m in members:
            if m.issym():
                target=destination.joinpath(*PurePosixPath(m.name.removeprefix('./')).parts)
                target.parent.mkdir(parents=True,exist_ok=True)
                target.symlink_to(m.linkname)
                os.utime(target,(m.mtime,m.mtime),follow_symlinks=False)
        # Directories last, deepest first: creating entries in a directory changes its time.
        dirs=[m for m in members if m.isdir() and m.name.removeprefix('./') not in ('','.')]
        for m in sorted(dirs,key=lambda m:m.name.count('/'),reverse=True):
            target=destination.joinpath(*PurePosixPath(m.name.removeprefix('./')).parts)
            target.chmod((m.mode & 0o3777) | 0o700)  # never lock the owner out; no setuid
            os.utime(target,(m.mtime,m.mtime))

def shown(name):
    """A file name for messages, control characters escaped."""
    return c.printable(name)

def archive_directory(source,target):
    """Archive a workspace; return the sockets and FIFOs left out (relative paths, sorted).

    They are runtime objects that a restore could not recreate. Other files a restore would
    refuse (device files, a backslash in a name) refuse the backup, naming the file."""
    source=Path(source); skipped=[]
    def unreadable(exc): raise c.SandboxError(f'Cannot read workspace entry {exc.filename}: {exc.strerror}')
    with tarfile.open(target,'w:gz',dereference=False) as tf:
        for root, dirs, files in os.walk(source,onerror=unreadable,followlinks=False):
            for name in sorted(dirs+files):
                p=Path(root)/name
                rel=p.relative_to(source).as_posix()
                mode=p.lstat().st_mode
                if stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode):
                    skipped.append(rel); continue
                if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode) or stat.S_ISLNK(mode)):
                    raise c.SandboxError(f'Workspace entry "{shown(rel)}" is a device file; backups cannot contain '
                                         'device files. Remove it and retry.')
                if "\\" in name:
                    raise c.SandboxError(f'Workspace entry "{shown(rel)}" has a backslash in its name, which a '
                                         'restore refuses. Rename it and retry.')
                if stat.S_ISLNK(mode) and "\\" in os.readlink(p):
                    raise c.SandboxError(f'Unsupported symlink target with a backslash: {p}')  # unpack() refuses it
                try: tf.add(p,arcname=rel,recursive=False)
                except OSError as exc: raise c.SandboxError(f'Cannot read workspace entry {p}: {exc.strerror}') from exc
    return sorted(skipped)

def helper_image(m):
    """The local image that archives home volumes: the environment's own registry
    image, else any local registry image; GNU tar with ACL/xattr support is a registry tool. Never
    pulled from a registry and never an unlabelled extra image."""
    from . import distros
    options=[*( [c.env_distro(m).image] if m.get('distro') else []),*(d.image for d in distros.REGISTRY.values())]
    for image in dict.fromkeys(options):
        if not c.docker('image','inspect',image,capture=True,check=False).returncode:
            return image
    raise c.SandboxError('Backup and restore of the home volume need a local base image: opencode-sandbox build --distro '+distros.DEFAULT)

def _volume_tar(m, dest, *, restore=False):
    """GNU tar inside rootless Docker retains numeric owners, ACLs and xattrs.

    Archive is validated before extraction; the volume must be a fresh,
    manager-labelled staging volume. No host-side unpack/repack loses metadata.
    """
    image=helper_image(m)
    staging=dest.parent.resolve()
    if restore:
        _validate_archive(dest)
        command=['sh','-ec',
            ('test -z "$(ls -A /data)"; '
             'cd /data; tar --extract --gzip --file=/staging/home.tar.gz '
             '--same-owner --numeric-owner --acls --xattrs --xattrs-include="*" '
             '--same-permissions; test -d /data')]
        c.docker('run','--rm','--network','none','--security-opt','no-new-privileges:true',*c.helper_labels('backup'),
                 '--user','0:0','--entrypoint',command[0],
                 '--mount',f'type=volume,src={c.volume(m)},dst=/data',
                 '--mount',f'type=bind,src={staging},dst=/staging,readonly',
                 image,*command[1:],capture=True)
    else:
        # Sockets and FIFOs are left out (a restore refuses them) and reported by name.
        command=['sh','-ec',
            ('cd /data; '
             f'find . \\( -type p -o -type s \\) -print0 > /staging/{HOME_SKIPPED}; '
             'find . ! -type p ! -type s -print0 > /tmp/ocs-home-files; '
             'tar --create --gzip --file=/staging/home.tar.gz '
             '--numeric-owner --acls --xattrs --xattrs-include="*" '
             '--null --verbatim-files-from --no-recursion --files-from=/tmp/ocs-home-files')]
        c.docker('run','--rm','--network','none','--security-opt','no-new-privileges:true',*c.helper_labels('backup'),
                 '--user','0:0','--entrypoint',command[0],
                 '--mount',f'type=volume,src={c.volume(m)},dst=/data,readonly',
                 '--mount',f'type=bind,src={staging},dst=/staging',image,*command[1:],capture=True)
        listing=dest.parent/HOME_SKIPPED
        try: raw=listing.read_bytes()
        except OSError as exc: raise c.SandboxError(f'Home volume archive helper gave no file list: {exc.strerror}') from exc
        listing.unlink()
        try: _validate_archive(dest)
        except c.SandboxError as exc:
            raise c.SandboxError(f'The home volume contains an entry a restore would refuse ({exc}); '
                                 'no backup was written') from None
        return sorted(os.fsdecode(n).removeprefix('./') for n in raw.split(b'\0') if n)

BACKUP_TAG=re.compile(r'ocs-backup:[0-9a-f]{16}-[0-9a-f]{10}')

def _short_name(name):
    return name.removeprefix('docker.io/library/')

def _image_archive_tag(path):
    """Return the single managed tag an image archive will create, or refuse.

    `docker image load` applies whatever names the archive declares, silently
    repointing existing tags (e.g. the shared base image). Validate every name
    source Docker honours before loading.
    """
    names=set(); refs=set(); counts=[]; digests=set()
    try:
        with tarfile.open(path,'r:') as tf:
            def member(name):
                try: f=tf.extractfile(name)
                except KeyError: return None
                return json.loads(f.read(1024*1024)) if f else None
            manifest=member('manifest.json'); index=member('index.json'); repos=member('repositories')
    except (tarfile.TarError,OSError,ValueError) as exc:
        raise c.SandboxError(f'Invalid system image archive: {exc}') from exc
    if manifest is None and index is None: raise c.SandboxError('System image archive has no manifest')
    if manifest is not None:
        if not isinstance(manifest,list): raise c.SandboxError('Invalid image archive manifest')
        counts.append(len(manifest))
        for entry in manifest:
            config=str(entry.get('Config',''))
            if config.startswith('blobs/sha256/'): digests.add('sha256:'+config.rsplit('/',1)[1])
            names.update(_short_name(t) for t in (entry.get('RepoTags') or []) if isinstance(t,str))
    if index is not None:
        entries=index.get('manifests') if isinstance(index,dict) else None
        if not isinstance(entries,list): raise c.SandboxError('Invalid image archive index')
        counts.append(len(entries))
        for entry in entries:
            if isinstance(entry.get('digest'),str): digests.add(entry['digest'])
            ann=entry.get('annotations') or {}
            if 'io.containerd.image.name' in ann: names.add(_short_name(str(ann['io.containerd.image.name'])))
            if 'org.opencontainers.image.ref.name' in ann: refs.add(str(ann['org.opencontainers.image.ref.name']))
    if isinstance(repos,dict):
        for repo,tags in repos.items():
            names.update(_short_name(f'{repo}:{t}') for t in (tags or {}))
    if any(n!=1 for n in counts) or len(names)!=1:
        raise c.SandboxError(f'System image archive must contain exactly one image with one name; found {sorted(names)}')
    (tag,)=names
    if not BACKUP_TAG.fullmatch(tag) or not refs <= {tag.split(':',1)[1]}:
        raise c.SandboxError(f'System image archive declares non-backup image name {tag!r}; refusing to load it')
    return tag, digests

def _check_image_tag_free(path):
    """Refuse to repoint an existing tag unless it already holds this exact image."""
    tag,digests=_image_archive_tag(path)
    existing=c.docker('image','inspect','--format','{{.Id}}',tag,capture=True,check=False)
    if not existing.returncode and existing.stdout.strip() not in digests:
        raise c.SandboxError(f'Image tag {tag} already exists with different content; refusing to overwrite it')
    return tag

def derived_image(m):
    """The manager-made image holding the environment's system layer (snapshot, runtime, OpenCode
    checkpoint, restored backup), or None when the environment uses its base image."""
    image=m.get('image')
    return image if image and image.split(':',1)[0] in c.MANAGER_IMAGE_KINDS else None

def backup_notes(target):
    """Human-readable notes on what a finished backup left out (none if unreadable: the backup
    itself has succeeded)."""
    try: manifest=json.loads((Path(target)/'manifest.json').read_text())
    except (OSError,ValueError): return []
    notes=[]
    for part,names in (manifest.get('skipped_special_files') or {}).items():
        if names:
            listed=', '.join(shown(n) for n in names[:5])+(f' and {len(names)-5} more' if len(names)>5 else '')
            notes.append(f'Not in the backup: {len(names)} socket/FIFO file(s) in the '
                         f"{'workspace' if part=='workspace' else 'home volume'} (recreated by the programs that use them): {listed}")
    return notes

def backup(m,destination=None,*,include_system=True,stop_running=False,include_workspace=None):
    """`include_workspace` defaults to True for managed and False for direct workspaces (D-012):
    a direct workspace is the user's own directory, normally covered by the user's own backups."""
    from . import workspaces
    c.ensure_runtime(False)
    with c.lock(m['id']):
        m=c.resolve(m['id'])
        if m.get('operation') or m.get('status') in ('deleting','error'):
            raise c.SandboxError('Resolve interrupted operations before backup')
        from . import workspace_io as wio
        mode=workspaces.info(m)['mode']
        if include_workspace is None: include_workspace=mode==workspaces.MANAGED
        if mode==workspaces.MANAGED and not include_workspace:
            raise c.SandboxError('The managed workspace is always part of a backup')
        workspace=workspaces.path(m)  # read only: archived, never modified
        # Check before stopping: refusing must not leave the environment stopped.
        if include_workspace: wio.require_readable(workspace,m['name'])
        state=c.inspect_container(m)
        if state and state.get('Running'):
            if not stop_running: raise c.SandboxError('Stop container first or use --stop')
            c.docker('stop',c.cname(m),capture=True)
            c.mark(m,'stopped',operation=None)
        c.assert_volume_owned(m)
        # The system layer comes from the container, or, without one, from the derived image the
        # next container would be created from (after a reconfiguration while stopped, an OpenCode
        # rollback, a restore before its first start).
        system_source=None
        if include_system:
            if state is not None: system_source='container'
            elif derived_image(m):
                system_source='image'
                if c.docker('image','inspect',m['image'],capture=True,check=False).returncode:
                    raise c.SandboxError(f"The environment's system image {m['image']} is missing, so its installed "
                                         'packages cannot be backed up. Use --no-system to back up the files only.')
        if destination: workspaces.refuse_output_inside(destination,'a backup')
        root=Path(destination).expanduser().resolve() if destination else c.BASE/'backups'
        # Never re-permission an existing user directory (e.g. ~/Public); each backup is a 0700 dir.
        existed=root.exists()
        root.mkdir(parents=True,exist_ok=True)
        if not existed or root==c.BASE/'backups': root.chmod(0o700)
        target=root/f"{m['name']}-{m['id']}-{c.datetime.now().strftime('%Y%m%d%H%M%S')}-{c.secrets.token_hex(3)}.ocsbackup"
        # Conservative free-space check: workspace plus an allowance for the
        # compressed home archive and Docker image; override via environment.
        estimated=sum(f.stat().st_size for f in workspace.rglob('*') if f.is_file() and not f.is_symlink()) if include_workspace else 0
        reserve=int(os.getenv('OPENCODE_SANDBOX_BACKUP_RESERVE_BYTES',str(512*1024*1024)))
        if shutil.disk_usage(root).free < estimated + reserve:
            raise c.SandboxError('Insufficient free disk space for backup (estimated workspace + reserve)')
        temp=Path(tempfile.mkdtemp(prefix='.backup-',dir=root))
        try:
            files=[]; skipped={'workspace':[],'home':[]}
            if include_workspace:
                skipped['workspace']=archive_directory(workspace,temp/'workspace.tar.gz'); files.append('workspace.tar.gz')
                # Publish only what a restore accepts.
                try: _validate_archive(temp/'workspace.tar.gz')
                except c.SandboxError as exc:
                    raise c.SandboxError(f'The workspace archive cannot be restored ({exc}); no backup was written') from None
            if c.volume_state(m) is not None:
                skipped['home']=_volume_tar(m,temp/'home.tar.gz'); files.append('home.tar.gz')
            if system_source:
                tag=f'ocs-backup:{m["id"]}-{c.secrets.token_hex(5)}'
                try:
                    if system_source=='container': c.docker('commit',c.cname(m),tag,capture=True)
                    else: c.docker('tag',m['image'],tag,capture=True)
                    c.docker('image','save','-o',str(temp/'system-image.tar'),tag,capture=True)
                    files.append('system-image.tar')
                finally: c.docker('image','rm',tag,capture=True,check=False)
            from . import __version__
            manifest={'format':'opencode-sandbox-backup','schema':SCHEMA,'manager_version':__version__,'created':c.now(),
                      'environment':{**{k:m.get(k) for k in ('id','name','kind','source','base_commit','profile','opencode_policy','opencode_pin','distro','provisioning')},
                                     'custom_image':c.custom_image(m),
                                     'runtime':c.runtime_settings(m)},
                      'workspace':{'mode':mode,'included':include_workspace},
                      'files':{name:{'sha256':digest(temp/name),'size':(temp/name).stat().st_size} for name in files},
                      'system_image':'system-image.tar' in files,'system_image_source':system_source,
                      'skipped_special_files':skipped,'external_profile_secrets_included':False,
                      'workspace_and_home_may_contain_secrets':True}
            (temp/'manifest.json').write_text(json.dumps(manifest,indent=2))
            os.chmod(temp/'manifest.json',0o600)
            os.replace(temp,target)
            return target
        except BaseException:
            shutil.rmtree(temp,ignore_errors=True)
            raise

def verify(path):
    root=Path(path).expanduser().resolve()
    if not root.is_dir(): raise c.SandboxError('Backup directory not found')
    manifest_path=root/'manifest.json'
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise c.SandboxError('Missing or unsafe backup manifest')
    try: manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    except (ValueError,UnicodeError) as exc: raise c.SandboxError(f'Invalid backup manifest: {exc}') from None
    if not isinstance(manifest,dict): raise c.SandboxError('Invalid backup manifest: not a JSON object')
    if manifest.get('format')!='opencode-sandbox-backup':
        raise c.SandboxError('Unsupported backup format')
    if manifest.get('schema')!=SCHEMA:
        # Other schemas are not migrated (D-002).
        raise c.SandboxError(f"Unsupported backup schema {manifest.get('schema')!r} (expected {SCHEMA}); "
                             'this version cannot restore it')
    files=manifest.get('files',{})
    workspace=manifest.get('workspace')
    if not isinstance(workspace,dict) or workspace.get('mode') not in ('managed','direct') \
            or workspace.get('included') is not ('workspace.tar.gz' in (files if isinstance(files,dict) else {})) \
            or (workspace['mode']=='managed' and not workspace['included']):
        raise c.SandboxError('Invalid backup workspace record')
    if not isinstance(files,dict) or set(files)-COMPONENTS \
            or not all(isinstance(e,str) or (isinstance(e,dict) and isinstance(e.get('sha256'),str)) for e in files.values()):
        raise c.SandboxError('Invalid backup components')
    if not isinstance(manifest.get('environment',{}),dict) or not isinstance(manifest.get('created'),str):
        raise c.SandboxError('Invalid backup manifest: environment record or creation time')
    for name, expected in files.items():
        p=root/name
        if p.is_symlink() or not p.is_file(): raise c.SandboxError(f'Missing or unsafe component: {name}')
        checksum=expected if isinstance(expected,str) else expected.get('sha256')
        if digest(p)!=checksum: raise c.SandboxError(f'Checksum mismatch: {name}')
        if isinstance(expected,dict) and p.stat().st_size!=expected.get('size'):
            raise c.SandboxError(f'Size mismatch: {name}')
        if name.endswith('.tar.gz'):
            manifest.setdefault('_uncompressed',{})[name]=sum(m.size for m in _validate_archive(p) if m.isfile())
    return manifest

def _reserve():
    return int(os.getenv('OPENCODE_SANDBOX_BACKUP_RESERVE_BYTES',str(512*1024*1024)))

def _check_restore_space(root, manifest, restore_system):
    """Refuse before creating anything if extraction cannot fit (incl. decompression bombs)."""
    sizes=manifest.get('_uncompressed',{})
    base=c.BASE
    while not base.exists(): base=base.parent
    need={str(base):sizes.get('workspace.tar.gz',0)}
    docker_root=c.docker('info','--format','{{.DockerRootDir}}',capture=True,check=False).stdout.strip()
    target=Path(docker_root) if docker_root and Path(docker_root).exists() else None
    docker_bytes=sizes.get('home.tar.gz',0)+((root/'system-image.tar').stat().st_size if restore_system and 'system-image.tar' in manifest['files'] else 0)
    for path,bytes_ in ((base,need[str(base)]),(target,docker_bytes)):
        if path is None or not bytes_: continue
        free=shutil.disk_usage(path).free
        if bytes_ + _reserve() > free:
            raise c.SandboxError(f'Insufficient disk space to restore: needs about {bytes_/2**20:.0f} MiB + reserve on {path}, '
                                 f'{free/2**20:.0f} MiB free')

def list_backups(directory=None):
    root=Path(directory).expanduser() if directory else c.BASE/'backups'
    return sorted((p for p in root.glob('*.ocsbackup') if p.is_dir() and not p.is_symlink()),reverse=True) if root.exists() else []

def backup_info(path):
    root=Path(path).expanduser().resolve()
    m=verify(root)
    return {'path':str(root),'name':m.get('environment',{}).get('name'),
            'created':m.get('created'),'components':list(m['files']),
            'bytes':sum((root/f).stat().st_size for f in m['files'])}

def prune(directory=None,*,keep=5,dry_run=True,on_delete=None):
    """Keep the newest `keep` VERIFIED backups per environment (name and id); delete older
    verified ones. "Newest" is the manifest's creation time: directory times change when
    backups are copied. A backup without an environment id is grouped by its name.

    Returns (selected, skipped). Unverifiable backups, and backups without a readable creation
    time, are never deleted and never count toward `keep`: otherwise corrupt newer backups could
    push valid ones out.
    """
    if keep<0: raise c.SandboxError('keep must be nonnegative')
    groups={}; skipped=[]
    for p in list_backups(directory):
        try:
            manifest=verify(p)
            env=manifest.get('environment',{})
            try: created=datetime.fromisoformat(manifest['created'])
            except ValueError: raise c.SandboxError(f"Invalid creation time {manifest['created'][:40]!r}") from None
            if created.tzinfo is None: raise c.SandboxError('Creation time without a time zone')
        except (c.SandboxError,OSError) as exc:
            skipped.append((p,str(exc))); continue
        groups.setdefault((env.get('name','unknown'),env.get('id')),[]).append((created,p))
    selected=[]
    for group in groups.values():
        selected.extend(p for _,p in sorted(group,key=lambda e:e[0],reverse=True)[keep:])
    if not dry_run:
        for p in selected:
            shutil.rmtree(p)
            if on_delete: on_delete(p)
    return selected, skipped

def _restore_into(m, root, manifest, *, restore_system=True):
    """Staged restore: publish only after workspace, volume and image succeed.

    A failure leaves a journal and owned staging resources for explicit rollback.
    Resume is deliberately conservative and never overwrites partial data.
    """
    with c.lock(m['id']):
        m=c.resolve(m['id'])
        # Checked under the lock: the state seen before taking it may be stale.
        if m.get('operation')!='restore' or m.get('status') not in ('error','restoring'):
            raise c.SandboxError('Not an interrupted restore')
        try:
            return _restore_stages(m,root,manifest,restore_system)
        except BaseException as exc:
            # Lock held since the check: the journal is this restore's own.
            c.mark(c.resolve(m['id']),'error',operation='restore',last_error=f'Restore incomplete: {exc}')
            raise

def _restore_stages(m, root, manifest, restore_system):
    """The stages of _restore_into; environment lock held, restore journal checked."""
    if c.inspect_container(m) is not None:
        raise c.SandboxError('Restore target has a container; refusing to overwrite')
    from . import workspaces
    if workspaces.is_direct(m):  # restore always creates a managed environment; never a host directory
        raise c.SandboxError('Restore never writes into a direct workspace')
    base=c.env_dir(m['id'])
    workspace=workspaces.managed_path(m)
    stage=base/'.workspace-stage'
    if stage.exists() or stage.is_symlink() or workspace.is_symlink() or (workspace.exists() and any(workspace.iterdir())):
        raise c.SandboxError('Restore staging/workspace is not empty; rollback before retry')
    if c.volume_state(m) is not None:
        raise c.SandboxError('Restore volume already exists; rollback before retry')
    c.mark(m,'restoring',operation='restore',restore_stage='workspace',restored_from=str(root))
    if 'workspace.tar.gz' in manifest['files']: unpack(root/'workspace.tar.gz',stage)
    else: stage.mkdir()
    if 'home.tar.gz' in manifest['files']:
        # Persist staging volume name BEFORE creating the Docker object.
        # Core ownership checks and deletion use this same name.
        staged=f"ocs-stage-{m['id']}-{uuid.uuid4().hex[:8]}"
        m['home_volume']=staged
        c.mark(m,'restoring',operation='restore',restore_stage='home')
        c.ensure_volume(m)
        _volume_tar(m,root/'home.tar.gz',restore=True)
    if restore_system and 'system-image.tar' in manifest['files']:
        c.mark(m,'restoring',operation='restore',restore_stage='image')
        expected=_check_image_tag_free(root/'system-image.tar')
        existed=not c.docker('image','inspect',expected,capture=True,check=False).returncode
        result=c.docker('image','load','-i',str(root/'system-image.tar'),capture=True)
        tags={_short_name(t) for t in re.findall(r'Loaded image:\s*(\S+)',result.stdout)}
        if tags!={expected}: raise c.SandboxError(f'Unexpected loaded image names {sorted(tags)}; inspect Docker images')
        _adopt_image(m,expected,untag=not existed)
    # Publish workspace only after all other stages have succeeded.
    if workspace.exists(): workspace.rmdir()
    os.replace(stage,workspace)
    m.update(kind=manifest['environment'].get('kind','scratch'),source=None,
             base_commit=manifest['environment'].get('base_commit'))
    c.mark(m,'ready',operation=None,restore_stage=None,last_error=None)
    return m

def _adopt_image(m, loaded, *, untag):
    """Make a loaded system image this environment's own: the archive carries the
    labels of the container it was committed from (another environment, maybe another data
    directory or machine), and cleanup decides by those labels. A container that is created but
    never started, with the environment's own name and labels, is committed to
    ocs-backup:<id>-<hex> and removed; the loaded tag is removed when this restore created it.
    The container has the environment's name, so an interrupted restore's rollback removes it."""
    tag=f'ocs-backup:{m["id"]}-{c.secrets.token_hex(5)}'
    c.docker('create','--pull','never','--network','none','--name',c.cname(m),*c.labels(m['id']),loaded,capture=True)
    try:
        c.docker('commit',c.cname(m),tag,capture=True)
        m['image']=tag
        c.save(m)
    finally:
        c.docker('rm','-v',c.cname(m),capture=True,check=False)
    if untag: c.docker('image','rm',loaded,capture=True,check=False)
    return tag

def restore(path,name,*,restore_system=True):
    root=Path(path).expanduser().resolve(strict=True)
    manifest=verify(root)
    c.safe_name(name)
    c.ensure_runtime(False)
    env=manifest.get('environment',{})
    kind=env.get('kind','scratch')
    if kind not in ('quick','project','scratch'): raise c.SandboxError('Unknown environment kind')
    settings=_restored_settings(env)
    if manifest['workspace']['mode']=='direct':
        settings['restore_warnings'].append(
            'The backed-up environment used a direct host workspace; the restored one has a managed workspace '
            + ('with a copy of those files.' if manifest['workspace']['included'] else
               '(empty: the host directory was not part of the backup) and is not connected to that directory.'))
    _check_restore_space(root,manifest,restore_system)
    if restore_system and 'system-image.tar' in manifest['files']:
        _check_image_tag_free(root/'system-image.tar')  # before creating anything
    elif settings['custom_image'] and c.docker('image','inspect',settings['custom_image'],capture=True,check=False).returncode:
        # Like `create --image`, the first start pulls it (D-026).
        settings['restore_warnings'].append(f"Custom image {settings['custom_image']} is not present locally; the first "
                                            'start pulls it like create --image (or load or build it first).')
    from . import integrations
    runtime=settings.pop('runtime')
    conflicts=c.port_conflicts({'id':None},runtime)
    if conflicts:
        settings['restore_warnings'].append('Published ports not restored (in use by another environment): '+', '.join(conflicts))
        runtime={**runtime,'ports':[]}
    # The journal and the backup's settings are in the first save: there is no moment in which
    # the environment looks like an ordinary empty one with default settings.
    journal={**{k:v for k,v in settings.items() if k not in ('profile','distro','custom_image')},'runtime':runtime,
             'status':'restoring','operation':'restore','restored_from':str(root),'restore_system':restore_system,
             'restore_stage':'initial'}
    # The home volume carries whatever was configured; the request is history and never re-applied.
    m=c.create(name,kind='scratch',profile=settings['profile'],distro=settings['distro'],image=settings['custom_image'],
               provisioning=integrations.as_history(env.get('provisioning')),journal=journal)
    # A failure is recorded by _restore_into under the lock, only for this restore's journal; a
    # refusal before it leaves the journal as it is.
    return _restore_into(m,root,manifest,restore_system=restore_system)

def _restored_settings(env):
    """Validate settings from a (semi-trusted) manifest before creating anything.

    Network mode and limits are part of the environment's isolation: a backup of
    an offline environment must not silently come back with bridge networking.
    """
    warnings=[]
    profile=env.get('profile') or 'default'
    try: c.safe_name(profile)
    except c.SandboxError:
        warnings.append('Invalid provider profile name in backup; using default'); profile='default'
    if 'runtime' in env:
        runtime=c.validate_runtime_settings(env['runtime'])
    else:
        runtime=c.validate_runtime_settings({})
        warnings.append('Backup has no runtime settings (older format); defaults applied: network=bridge. Review with config show.')
    # The distribution decides the base image and the Agent Context; never guess it.
    if 'distro' not in env: raise c.SandboxError('Backup does not record the distribution of the environment')
    if env['distro'] is None:
        if not isinstance(env.get('custom_image'),str): raise c.SandboxError('Backup of a custom-image environment lacks the image')
    else:
        from . import distros
        distros.get(env['distro'])
    result={'profile':profile,'runtime':runtime,'restore_warnings':warnings,
            'distro':env['distro'],'custom_image':env.get('custom_image') if env['distro'] is None else None}
    policy=env.get('opencode_policy')
    if policy is not None:
        from . import opencode_versions as v
        v.policy({'opencode_policy':policy,'opencode_pin':env.get('opencode_pin')})  # validates
        result.update(opencode_policy=policy,opencode_pin=env.get('opencode_pin'))
    return result

def resume_restore(m):
    """Resume only if no workspace data or Docker volume has been written.

    Later-stage interruptions require explicit rollback and a new restore, to
    avoid silently overwriting partially restored files or volumes.
    """
    m=c.resolve(m['id'] if isinstance(m,dict) else m)
    if m.get('operation')!='restore' or m.get('status') not in ('error','restoring'):
        raise c.SandboxError('Not an interrupted restore')
    root=Path(m.get('restored_from',''))
    manifest=verify(root)
    return _restore_into(m,root,manifest,restore_system=m.get('restore_system',True))

def rollback_restore(m):
    """Explicitly remove an incomplete restore after ownership checks; never implicit."""
    m=c.resolve(m['id'] if isinstance(m,dict) else m)
    # 'restoring' covers a killed restore; a live restore holds the environment
    # lock through all its stages, so delete() (which takes it) cannot race them.
    def failed_restore(current):
        if current.get('operation')!='restore' or current.get('status') not in ('error','restoring'):
            raise c.SandboxError('Not a failed restore')
    failed_restore(m)
    c.delete(m,force=True,precondition=failed_restore)  # checked again under the lock

def check_restored(m):
    """Check container boot and workspace visibility; does not invoke LLM APIs."""
    m=c.resolve(m['id'] if isinstance(m,dict) else m)
    if m.get('status') not in ('ready','stopped','running'):
        raise c.SandboxError('Environment is not ready for validation')
    c.start(m)
    p=c.docker('exec',c.cname(m),'sh','-c','set -eu; test -d /workspace; test -d /root; test -w /workspace; test -w /root; command -v opencode >/dev/null; opencode --version >/dev/null',capture=True,check=False)
    if p.returncode: raise c.SandboxError('Restored container smoke check failed')
    return True
