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
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.npm.install-v1+json", "User-Agent": "opencode-sandbox-manager"})
    try:
        with urllib.request.urlopen(request, timeout=float(timeout)) as response:
            if response.status != 200: raise ValueError(f"HTTP {response.status}")
            raw = response.read(limit + 1)
            if len(raw) > limit: raise ValueError("npm registry response too large")
        sys.stdout.buffer.write(raw)
    except urllib.error.HTTPError as exc:
        print(json.dumps({"status": exc.code, "retry_after": (exc.headers.get("Retry-After") or "")[:128]}), file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(str(exc)[:1000], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
