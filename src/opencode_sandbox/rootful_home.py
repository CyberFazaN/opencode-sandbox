"""Container-side setup for managed rootful images."""
BOOTSTRAP = r"""
import grp
import shutil
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile

name, uid, gid, home = sys.argv[1:]
uid, gid = int(uid), int(gid)

def run(*args):
    subprocess.run(args, check=True)

if not any(line.split()[4] == home for line in Path("/proc/self/mountinfo").read_text().splitlines()):
    sys.exit("expected the persistent home volume mount")
if not shutil.which("sudo") or not Path("/etc/sudoers.d").is_dir():
    sys.exit("managed image lacks sudo support; rebuild the rootful base image")
try:
    group = grp.getgrgid(gid).gr_name
except KeyError:
    group = f"ocs-{gid}"
    run("groupadd", "-g", str(gid), group)

try:
    account = pwd.getpwnam(name)
except KeyError:
    account = None
if account is None or (account.pw_uid, account.pw_gid, account.pw_dir) != (uid, gid, home):
    try:
        existing = pwd.getpwuid(uid)
    except KeyError:
        existing = None
    if account is not None and account.pw_name != "node":
        sys.exit("host username collides with a container account")
    if existing is not None and existing.pw_name != "node":
        sys.exit("host UID collides with a container account")
    if existing is not None or account is not None:
        def replace_entry(path, update):
            attrs = path.stat()
            with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as file:
                os.fchown(file.fileno(), attrs.st_uid, attrs.st_gid)
                os.fchmod(file.fileno(), attrs.st_mode & 0o777)
                for line in path.read_text().splitlines():
                    file.write((update(line) if line.startswith("node:") else line) + "\n")
                pending = file.name
            os.replace(pending, path)
        # Official Node images already reserve UID 1000. Keep the shadow account
        # record when renaming, since sudo's PAM account phase still consults it.
        replace_entry(Path("/etc/shadow"), lambda line: name + line[4:])
        replace_entry(Path("/etc/passwd"), lambda line: f"{name}:x:{uid}:{gid}::{home}:/bin/bash")
    else:
        run("useradd", "-M", "-u", str(uid), "-g", group, "-d", home, "-s", "/bin/bash", "--", name)
os.chown(home, uid, gid)
sudoers = Path("/etc/sudoers.d/90-ocs-runtime")
content = f"#{uid} ALL=(ALL:ALL) NOPASSWD: ALL\n"
if not sudoers.is_file() or sudoers.read_text() != content:
    with tempfile.NamedTemporaryFile(dir=sudoers.parent, delete=False) as file:
        os.fchmod(file.fileno(), 0o440)
        file.write(content.encode())
        path = file.name
    os.replace(path, sudoers)
"""
