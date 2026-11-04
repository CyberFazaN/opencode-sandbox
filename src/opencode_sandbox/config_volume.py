"""Recoverable whole-directory replacement inside an environment's /root volume.

This module is concatenated with config_tree.py and executed by a network-none helper.
The only replacement boundary is <home>/.config/opencode. A private, same-filesystem
journal retains the old directory through the atomic exchange and durable commit.
"""
from __future__ import annotations

import fcntl
import json
import os
import shutil
import stat
import sys
import tarfile
import time

from .config_tree import (
    DIR_FLAGS,
    TreeError,
    exchange,
    snapshot,
    sync_directory,
    unpack,
    write_json,
)


def checked_directory(path, *, private=False):
    fd = os.open(path, DIR_FLAGS)
    try:
        st = os.fstat(fd)
        if st.st_uid != os.getuid() or (private and stat.S_IMODE(st.st_mode) != 0o700):
            raise TreeError("Unsafe config transaction directory ownership or permissions")
    finally:
        os.close(fd)


def inode(path):
    st = os.stat(path, follow_symlinks=False)
    if not stat.S_ISDIR(st.st_mode):
        raise TreeError("Config directory must be a real directory, not a symlink")
    return [st.st_dev, st.st_ino]


def recover(parent, binding):
    target, transaction = parent + "/opencode", parent + "/.ocs-occonfig-transaction"
    if not os.path.lexists(transaction):
        return
    checked_directory(transaction, private=True)
    marker = transaction + "/state.json"
    for name in os.listdir(transaction):
        # write_json's own temporary marker from an interrupted durable update; the previous
        # state.json (if any) still describes the transaction.
        if name.startswith(".ocs-"):
            st = os.stat(transaction + "/" + name, follow_symlinks=False)
            if stat.S_ISREG(st.st_mode) and st.st_uid == os.getuid() and st.st_nlink == 1 and st.st_size <= 8192:
                os.unlink(transaction + "/" + name)
    entries = set(os.listdir(transaction))
    if not entries:
        # The only unmarked case safe to remove: a private, empty reserved staging
        # directory left just before marker creation or just after its final unlink.
        os.rmdir(transaction)
        sync_directory(parent)
        return
    if not entries <= {"state.json", "tree"}:
        raise TreeError("Unexpected config transaction entries; preserved for manual recovery")
    fd = os.open(marker, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd) as source:
        st = os.fstat(source.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1 or st.st_size > 8192:
            raise TreeError("Unsafe config transaction marker; preserved")
        state = json.load(source)
    if state.get("binding") != binding or state.get("phase") not in ("staging", "prepared", "committed"):
        raise TreeError("Unrecognized config transaction; preserved for manual recovery")
    stage = transaction + "/tree"
    if state["phase"] in ("prepared", "committed"):
        actual = inode(target)
        staged = inode(stage) if os.path.lexists(stage) else None
        old, new = state["old"], state["new"]
        if state["phase"] == "prepared":
            if actual == new and staged == old:
                exchange(target, stage)  # Interrupted/uncommitted switch: restore the original.
                sync_directory(parent)
            elif actual != old or staged not in (None, new):
                raise TreeError("Config transaction identities changed; old copy preserved for manual recovery")
        elif actual != new or staged not in (None, old):
            raise TreeError("Committed config transaction does not match its installed tree; preserved")
    # Keep the identity/commit marker until all possibly large old/staged contents are gone.
    # Interruption during cleanup can therefore resume without losing its recovery evidence.
    if os.path.lexists(stage):
        inode(stage)  # refuse symlinks, even in the staging phase
        shutil.rmtree(stage)  # descriptor-based, never follows nested symlinks
        sync_directory(transaction)
    os.unlink(marker)
    os.rmdir(transaction)
    sync_directory(parent)


def operation(home, request, incoming, outgoing):
    """The caller's manager lock is complemented by a volume flock surviving client death."""
    checked_directory(home)
    parent = home + "/.config"
    try: os.mkdir(parent, 0o700)
    except FileExistsError: pass
    checked_directory(parent)
    fd = os.open(parent + "/.ocs-occonfig.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                 0o600)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1 \
                or stat.S_IMODE(st.st_mode) != 0o600:
            raise TreeError("Unsafe volume config lock")
        deadline = time.monotonic() + 30
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TreeError("Another config volume operation is still running; retry after it finishes")
                time.sleep(0.05)
        binding = request["binding"]
        recover(parent, binding)
        target = parent + "/opencode"
        action = request["action"]
        limits = {"max_bytes": request["max_bytes"], "max_entries": request["max_entries"]}
        if action == "recover":
            return {"recovered": True}
        if action == "export":
            return {"fingerprint": snapshot(target, outgoing, **limits)}
        if action == "fingerprint":
            return {"fingerprint": snapshot(target, None, **limits)}
        if action != "replace":
            raise TreeError("Unknown config volume action")
        # Input is fully staged and verified before sampling or modifying the destination.
        transaction = parent + "/.ocs-occonfig-transaction"
        os.mkdir(transaction, 0o700)
        state = {"binding": binding, "phase": "staging"}
        write_json(transaction + "/state.json", state)
        stage = transaction + "/tree"
        os.mkdir(stage, 0o700)
        try:
            unpack(incoming, stage, **limits)
            installed = snapshot(stage, None, allow_missing=False, **limits)
            original = snapshot(target, None, **limits)
            if request.get("fresh") and os.path.lexists(target) and os.listdir(target):
                raise TreeError("Initial OpenCode config destination is not fresh; nothing was replaced")
            expected = request.get("expected")
            if expected is not None and original != expected:
                return {"conflict": original}
            if not os.path.lexists(target):
                os.mkdir(target, 0o700)
                sync_directory(parent)
            state.update(phase="prepared", old=inode(target), new=inode(stage))
            write_json(transaction + "/state.json", state)
            # Last whole-tree comparison is inside this locked transaction. An overwrite only
            # authorizes the exact observed digest, never arbitrary future changes.
            if snapshot(target, None, **limits) != original:
                raise TreeError("Container config changed again during replacement; review again")
            exchange(target, stage)
            sync_directory(parent)
            sync_directory(transaction)
            if snapshot(stage, None, allow_missing=False, **limits) != original:
                raise TreeError("Container config changed during the switch; original restored, review again")
            actual = snapshot(target, None, allow_missing=False, **limits)
            if actual != installed:
                raise TreeError("Installed config changed during replacement; original copy retained/restored")
            state["phase"] = "committed"
            write_json(transaction + "/state.json", state)
            return {"fingerprint": actual}
        finally:
            recover(parent, binding)
    finally:
        os.close(fd)


def helper_main():
    try:
        os.umask(0o077)
        request = json.loads(sys.argv[1])
        result = operation("/root", request, sys.stdin.buffer, sys.stdout.buffer)
        print(json.dumps(result), file=sys.stderr)
    except (OSError, ValueError, TreeError, tarfile.TarError, RecursionError) as exc:
        # Fixed codec errors are safe; OS/JSON/archive messages may contain sensitive paths/data.
        message = str(exc) if isinstance(exc, TreeError) else "Config transfer failed; original config and recovery copies were preserved"
        print(json.dumps({"error": message}), file=sys.stderr)
        sys.exit(1)
