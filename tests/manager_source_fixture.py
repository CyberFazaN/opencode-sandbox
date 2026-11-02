"""Owned loopback GitHub-API-shaped transport, NOT public GitHub/release authentication."""
import copy
import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer

from opencode_sandbox import manager_releases as r
from opencode_sandbox import manager_targets as t


def graph(*, commit='c' * 40, tags=('a' * 40,), tag='v6.2.0'):
    def obj(kind, oid): return {'type': kind, 'sha': oid, 'url': t.SOURCE_API + '/git/' + kind + 's/' + oid}
    objects = [obj('tag', oid) for oid in tags] + [obj('commit', commit)]
    release = {'id': 42, 'url': t.SOURCE_API + '/releases/42', 'tag_name': tag, 'draft': False, 'prerelease': False,
               'published_at': '2026-10-30T12:00:00Z', 'html_url': r.REPOSITORY + '/releases/tag/' + tag,
               'body': 'Release [notes]', 'target_commitish': 'not-a-commit-and-never-used'}
    routes = {'/releases/tags/' + tag: release,
              '/git/ref/tags/' + tag: {'ref': 'refs/tags/' + tag, 'url': t.SOURCE_API + '/git/refs/tags/' + tag, 'object': objects[0]},
              '/git/commits/' + commit: {'sha': commit, 'url': t.SOURCE_API + '/git/commits/' + commit},
              '/releases?per_page=100': [release]}
    for i, oid in enumerate(tags):
        routes['/git/tags/' + oid] = {'sha': oid, 'url': t.SOURCE_API + '/git/tags/' + oid,
                                    'tag': tag if i == 0 else 'inner-tag', 'object': objects[i + 1]}
    return routes


@contextmanager
def serve(routes=None):
    state = {'routes': graph() if routes is None else copy.deepcopy(routes), 'requests': [], 'status': 200,
             'headers': {}, 'delay': 0, 'before': None}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def do_GET(self):
            state['requests'].append((self.path, dict(self.headers)))
            if state['before']: state['before'](self.path, state)
            time.sleep(state['delay'])
            value = state['routes'].get(self.path)
            status = state['status'] if value is not None else 404
            self.send_response(status)
            for key, value_header in state['headers'].items(): self.send_header(key, value_header)
            self.end_headers()
            try: self.wfile.write(value if isinstance(value, bytes) else json.dumps(value).encode())
            except (BrokenPipeError, ConnectionResetError): pass  # expected only in owned timeout tests
    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    thread.start()
    try: yield f'http://127.0.0.1:{server.server_port}', state
    finally:
        server.shutdown(); thread.join(timeout=3); server.server_close()
        assert not thread.is_alive(), 'Owned source server did not stop'
