"""
DocWire Atomic - Detect missed file changes via polling
Checks most recently modified file every 0.5s
If mtime/lines differ from snp, triggers poke.py
"""

import os
import time
import threading
from pathlib import Path
from utils import get_dw_path, read_file, get_txt_files, get_stem
from head import has_header


_poll_thread = None
_poll_stop = False


def get_file_stats(file_path):
    """Get mtime and line count for a file"""
    file_path = Path(file_path)
    if not file_path.exists():
        return None, None

    mtime = os.path.getmtime(file_path)
    content = read_file(file_path)
    lines = len(content.split('\n')) if content else 0

    return mtime, lines


def get_most_recent_file():
    """Get the most recently modified tracked .txt file"""
    dw_path = get_dw_path()
    if not dw_path.exists():
        return None

    most_recent = None
    most_recent_mtime = 0

    for txt_path in get_txt_files():
        content = read_file(txt_path)
        if has_header(content):
            mtime = os.path.getmtime(txt_path)
            if mtime > most_recent_mtime:
                most_recent_mtime = mtime
                most_recent = txt_path

    return most_recent


def check_file(txt_path):
    """
    Check if file changed but watchdog missed it.
    Returns True if change detected.
    """
    dw_path = get_dw_path()
    txt_path = Path(txt_path)

    snp_path = dw_path / 'snp' / txt_path.name

    if not snp_path.exists():
        return False

    # Get stats
    txt_mtime, txt_lines = get_file_stats(txt_path)
    snp_mtime, snp_lines = get_file_stats(snp_path)

    if txt_mtime is None or snp_mtime is None:
        return False

    # Check if txt is newer or line count different
    if txt_mtime > snp_mtime or txt_lines != snp_lines:
        return True

    return False


def poke_file(txt_path):
    """Trigger poke.py to touch the file"""
    from poke import trigger_save
    trigger_save(txt_path)


def poll_loop():
    """Background poll loop - checks most recent file every 0.5s"""
    global _poll_stop

    while not _poll_stop:
        try:
            recent_file = get_most_recent_file()
            if recent_file and check_file(recent_file):
                poke_file(recent_file)
        except Exception:
            pass  # Ignore errors in poll loop

        time.sleep(0.5)


def start_poll():
    """Start the atomic poll thread"""
    global _poll_thread, _poll_stop

    if _poll_thread is not None and _poll_thread.is_alive():
        return  # Already running

    _poll_stop = False
    _poll_thread = threading.Thread(target=poll_loop, daemon=True)
    _poll_thread.start()


def stop_poll():
    """Stop the atomic poll thread"""
    global _poll_stop
    _poll_stop = True
