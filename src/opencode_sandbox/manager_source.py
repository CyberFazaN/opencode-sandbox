"""Stdlib published-source graph semantics shared by origin and frozen execution checks.

The caller supplies a bounded HTTPS reader, never authority URLs from a response. No cache,
application import, installation mutation or credential lookup lives here.
"""
import hashlib
import re
import time
from datetime import datetime

REPOSITORY = 'https://github.com/CyberFazaN/opencode-sandbox'
API = 'https://api.github.com/repos/CyberFazaN/opencode-sandbox'
MAX_TAGS = 4


def version(tag):
    if not isinstance(tag, str) or len(tag) >= 80 or not re.fullmatch(r'v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', tag):
        raise ValueError('Expected a full release tag vX.Y.Z (no prerelease, prefix or command)')
    return tag[1:]


def release(item):
    if not isinstance(item, dict) or item.get('draft') is not False or item.get('prerelease') is not False:
        raise ValueError('not a full release')
    tag = item.get('tag_name')
    value = version(tag)
    published = item.get('published_at')
    if not isinstance(published, str) or not published.endswith('Z') or len(published) > 40:
        raise ValueError('not published')
    if not 0 < datetime.fromisoformat(published).timestamp() <= time.time(): raise ValueError('invalid publication date')
    url = REPOSITORY + '/releases/tag/' + tag
    if item.get('html_url') != url: raise ValueError('foreign release URL')
    body = item.get('body')
    if body is None: body = ''
    if not isinstance(body, str): raise TypeError('invalid release notes')
    notes = ''.join(ch if ch.isprintable() or ch in '\n\t' else ch.encode('unicode_escape').decode() for ch in body[:8192])
    return {'version': value, 'tag': tag, 'url': url, 'published_at': published,
            'notes': notes, 'notes_truncated': len(body) > 8192}


def _oid(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{40}', value): raise ValueError('Invalid Git object identity')
    return value


def _object(value):
    if not isinstance(value, dict) or value.get('type') not in ('tag', 'commit'): raise ValueError('Unsupported Git reference type')
    oid, kind = _oid(value.get('sha')), value['type']
    if value.get('url') != API + '/git/' + kind + 's/' + oid: raise ValueError('Foreign Git object URL')
    return kind, oid


def resolve(tag, get):
    """Bracket an exact release/ref/tag-chain/commit graph with fresh release/ref reads."""
    version(tag)
    def published():
        item = get('/releases/tags/' + tag)
        value, rid = release(item), item.get('id')
        if value['tag'] != tag or type(rid) is not int or not 0 < rid < 2**63 or item.get('url') != API + '/releases/' + str(rid):
            raise ValueError('Invalid exact published release identity')
        return value, rid, hashlib.sha256((item.get('body') or '').encode()).hexdigest()
    def ref():
        item = get('/git/ref/tags/' + tag)
        if item.get('ref') != 'refs/tags/' + tag or item.get('url') != API + '/git/refs/tags/' + tag:
            raise ValueError('Invalid exact Git tag reference')
        return _object(item.get('object'))
    publication = published()
    root = kind, oid = ref()
    objects = []
    while kind == 'tag':
        if oid in objects or len(objects) >= MAX_TAGS: raise ValueError('Cyclic or excessive annotated tags')
        item = get('/git/tags/' + oid)
        if _oid(item.get('sha')) != oid or item.get('url') != API + '/git/tags/' + oid or (not objects and item.get('tag') != tag):
            raise ValueError('Annotated tag identity disagrees')
        objects.append(oid)
        kind, oid = _object(item.get('object'))
    if oid in objects: raise ValueError('One Git object cannot be both annotated tag and commit')
    item = get('/git/commits/' + oid)
    if _oid(item.get('sha')) != oid or item.get('url') != API + '/git/commits/' + oid: raise ValueError('Commit identity disagrees')
    objects.append(oid)
    if ref() != root or published() != publication: raise ValueError('Published manager source changed during resolution; review the target again')
    value, rid, notes_hash = publication
    return {'tag': tag, 'version': value['version'], 'release_id': rid, 'published_at': value['published_at'],
            'notes': value['notes'], 'notes_truncated': value['notes_truncated'], 'notes_sha256': notes_hash,
            'objects': objects}
