"""Minimal console bootstrap: installation exclusion before importing the replaceable CLI."""
import sys

from . import installation_locks


def main():
    try: installation_locks.acquire_usage()
    except installation_locks.Error as exc:
        print(f'Error: {exc}', file=sys.stderr)
        raise SystemExit(2) from None
    from .cli import main as run
    return run()


if __name__ == '__main__': main()
