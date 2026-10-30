"""Standalone stdlib HTTP fetch child: the parent bounds DNS, TLS, reads and cancellation.

No credentials, host npm, package imports or persistent process. Kept separate so an isolated
interpreter can execute it from either a source checkout or an installed wheel.
"""
import sys
import urllib.error
import urllib.request


def main():
    url, timeout = sys.argv[1:]
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "opencode-sandbox-manager"})
    try:
        with urllib.request.urlopen(request, timeout=float(timeout)) as response:
            if response.status != 200: raise ValueError(f"HTTP {response.status}")
            raw = response.read(65537)
            if len(raw) > 65536: raise ValueError("npm registry response too large")
        sys.stdout.buffer.write(raw)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(str(exc)[:1000], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
