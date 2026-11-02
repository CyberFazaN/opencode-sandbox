"""Standalone stdlib HTTP fetch child: the parent bounds DNS, TLS, reads and cancellation.

No credentials, host npm, package imports or persistent process. Kept separate so an isolated
interpreter can execute it from either a source checkout or an installed wheel.
"""
import json
import sys
import urllib.error
import urllib.request


def main():
    url, timeout, *options = sys.argv[1:]
    limit = int(options[0]) if options else 65536
    github = options[1:] == ['github']
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json" if github else "application/vnd.npm.install-v1+json",
                                                  "User-Agent": "opencode-sandbox-manager"})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs): return None
    open_url = urllib.request.build_opener(NoRedirect()).open if github else urllib.request.urlopen
    try:
        with open_url(request, timeout=float(timeout)) as response:
            if response.status != 200: raise ValueError(f"HTTP {response.status}")
            raw = response.read(limit + 1)
            if len(raw) > limit: raise ValueError("GitHub response too large" if github else "npm registry response too large")
        sys.stdout.buffer.write(raw)
    except urllib.error.HTTPError as exc:
        print(json.dumps({"status": exc.code, "retry_after": (exc.headers.get("Retry-After") or "")[:128],
                          **({"rate_reset": (exc.headers.get("X-RateLimit-Reset") or "")[:128]} if github else {})}), file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(str(exc)[:1000], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
