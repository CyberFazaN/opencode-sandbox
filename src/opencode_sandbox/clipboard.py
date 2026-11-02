"""Optional Linux clipboard transport. Never read clipboard contents or install host tools."""
import os
import shutil
import subprocess


def native_copy(text):
    """True only after an available local backend accepts the write; None means use OSC 52.

    A remote shell's DISPLAY may name a remote desktop, not the user's terminal. Let the
    terminal handle those copies. No shell, clipboard readback, or text in diagnostic output.
    """
    if os.environ.get('SSH_CONNECTION') or os.environ.get('SSH_TTY'):
        return None
    candidates = []
    if os.environ.get('WAYLAND_DISPLAY'):
        candidates.append(('wl-copy', ['--type', 'text/plain;charset=utf-8']))
    if os.environ.get('DISPLAY'):
        candidates.append(('xclip', ['-selection', 'clipboard']))
    for name, args in candidates:
        executable = shutil.which(name)
        if not executable:
            continue
        try:
            result = subprocess.run([executable, *args], input=text.encode('utf-8'), check=False,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            if result.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None
