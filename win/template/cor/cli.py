"""
DocWire CLI - Main command line interface
"""

import sys
import os
import shutil
from pathlib import Path

from utils import (
    get_dw_path, get_txt_files, ensure_folders,
    read_file, write_file, read_config, read_loc, write_loc,
    read_index, write_index, read_session_log,
    get_timestamp, get_timestamp_compact, get_relative_path, get_stem
)
from head import has_header, add_header, parse_header, update_file_field, get_field
from bump import increment_r, parse_version
from watch import start_watcher, stop_watcher, is_watcher_running
from diff import calc_diff
from sync import do_sync
from fix import cmd_fix, scan_issues
from archive import cmd_archive
from compact import cmd_compact


def cmd_init():
    """Initialize tracking: add headers, create snp/, loc/ files"""
    dw_path = get_dw_path()

    if not dw_path.exists():
        print("No .dw/ folder. Run 'dw setup' first.")
        return

    ensure_folders()

    # Get config for ignore patterns
    config = read_config()
    ignore_patterns = config.get('ignore', [])

    # Get all .txt files
    txt_files = get_txt_files()

    # Filter ignored files (simple glob matching)
    def is_ignored(filepath):
        rel_path = get_relative_path(filepath)
        for pattern in ignore_patterns:
            # Simple pattern matching
            if pattern.endswith('/*'):
                folder = pattern[:-2]
                if rel_path.startswith(folder):
                    return True
            elif rel_path == pattern:
                return True
        return False

    tracked = []
    skipped = []

    for txt_file in txt_files:
        if is_ignored(txt_file):
            skipped.append(txt_file)
            continue

        # Add header if not exists
        content = read_file(txt_file)
        if not has_header(content):
            add_header(txt_file)
            print(f"[+] Added header: {txt_file.name}")

        # Read content again (with header)
        content = read_file(txt_file)
        stem = get_stem(txt_file)

        # Copy to snapshot
        snp_path = dw_path / 'snp' / txt_file.name
        write_file(snp_path, content)

        # Create loc/*.txt
        loc_path = dw_path / 'loc' / f'{stem}.txt'
        if not loc_path.exists():
            fields = parse_header(content)
            ts = get_timestamp()
            loc_data = {
                'meta': {
                    'file': get_relative_path(txt_file),
                    'version': fields.get('version', 'av1r1'),
                    'saves': 0,
                    'updated': ts
                },
                'history': [{'action': f'{ts} initialized', 'changes': []}],
                'archive': []
            }
            write_loc(loc_path, loc_data)

        tracked.append(txt_file)

    # Update index.txt
    index_data = [
        {
            'file': get_relative_path(f),
            'version': get_field(read_file(f), 'version') or 'av1r1'
        }
        for f in tracked
    ]
    write_index(index_data)

    print(f"\nInitialized {len(tracked)} files")
    if skipped:
        print(f"Skipped {len(skipped)} ignored files")


def init_file(txt_file):
    """Initialize a single file (for atomic save handling)"""
    dw_path = get_dw_path()
    txt_file = Path(txt_file)

    if not dw_path.exists():
        return False

    # Check header
    content = read_file(txt_file)
    if not has_header(content):
        return False

    stem = get_stem(txt_file)

    # Create loc/*.txt if not exists
    loc_path = dw_path / 'loc' / f'{stem}.txt'
    if not loc_path.exists():
        fields = parse_header(content)
        ts = get_timestamp()
        loc_data = {
            'meta': {
                'file': get_relative_path(txt_file),
                'version': fields.get('version', 'av1r1'),
                'saves': 0,
                'updated': ts
            },
            'history': [{'action': f'{ts} initialized', 'changes': []}],
            'archive': []
        }
        write_loc(loc_path, loc_data)

    return True


def cmd_start():
    """Start watcher daemon"""
    dw_path = get_dw_path()

    if not dw_path.exists():
        print("No .dw/ folder. Run 'dw setup' first.")
        return

    running, pid = is_watcher_running()

    if running:
        # Read start time from dw-current.txt
        log_path = dw_path / 'glb' / 'dw-current.txt'
        log_data = read_session_log(log_path)
        started = log_data.get('meta', {}).get('started', 'unknown')

        print(f"\nWatcher already running (PID: {pid})")
        print(f"Started: {started}")
        print("\n[1] Keep (continue)")
        print("[2] Restart")
        print("[3] Stop")

        choice = input("\nChoice [1/2/3]: ").strip()

        if choice == '1':
            print("Keeping existing watcher")
            return
        elif choice == '2':
            print("Restarting...")
            stop_watcher()
            # Continue to auto-bump and start
        elif choice == '3':
            stop_watcher()
            return
        else:
            print("Invalid choice")
            return

    # Init to ensure all txt files are tracked
    print("Initializing...")
    cmd_init()

    # Sync before bump
    print("Syncing...")
    synced, issues = do_sync(silent=True)

    # Auto-bump before starting
    print("Checking for unbumped saves...")
    bumped = do_bump(silent=True)
    if bumped > 0:
        print(f"Auto-bumped {bumped} files")

    # Show issues hint if any
    if issues > 0:
        print(f"[!] {issues} issue(s) found. Run 'dw fix' for details.")

    # Start watcher (check for -f flag for foreground)
    foreground = '-f' in sys.argv
    start_watcher(foreground=foreground)


def cmd_stop():
    """Stop watcher daemon"""
    dw_path = get_dw_path()

    if not dw_path.exists():
        print("No .dw/ folder.")
        return

    stop_watcher()


def do_bump(file_path=None, silent=False):
    """
    Bump revision for files with unbumped saves
    Returns count of bumped files
    """
    dw_path = get_dw_path()
    loc_folder = dw_path / 'loc'
    bumped_count = 0

    if file_path:
        # Bump specific file
        loc_files = [loc_folder / f'{get_stem(file_path)}.txt']
    else:
        # Bump all files
        loc_files = list(loc_folder.glob('*.txt'))

    for loc_path in loc_files:
        if not loc_path.exists():
            continue

        loc_data = read_loc(loc_path)
        saves = loc_data.get('meta', {}).get('saves', 0)

        if saves > 0:
            # Get current version
            old_version = loc_data.get('meta', {}).get('version', 'av1r1')
            new_version = increment_r(old_version)

            # Update loc/*.txt
            loc_data['meta']['version'] = new_version
            loc_data['meta']['saves'] = 0

            ts = get_timestamp()
            loc_data['history'].append({
                'action': f'{ts} bumped {new_version}',
                'changes': []
            })

            write_loc(loc_path, loc_data)

            # Update .txt header
            txt_file = loc_data.get('meta', {}).get('file', '')
            if txt_file:
                txt_path = Path.cwd() / txt_file.lstrip('./')
                if txt_path.exists():
                    update_file_field(txt_path, 'version', new_version)

            if not silent:
                print(f"[BUMPED] {loc_path.stem}: {old_version} -> {new_version}")

            bumped_count += 1

    return bumped_count


def cmd_bump(args):
    """Bump revision command"""
    dw_path = get_dw_path()

    if not dw_path.exists():
        print("No .dw/ folder. Run 'dw setup' first.")
        return

    file_path = None
    if '-f' in args:
        idx = args.index('-f')
        if idx + 1 < len(args):
            file_path = args[idx + 1]

    bumped = do_bump(file_path)

    if bumped == 0:
        print("No files to bump (no unbumped saves)")
    else:
        print(f"\nBumped {bumped} file(s)")


def cmd_status():
    """Show watcher status and tracked files"""
    dw_path = get_dw_path()

    if not dw_path.exists():
        print("No .dw/ folder. Run 'dw setup' first.")
        return

    # Watcher status
    running, pid = is_watcher_running()
    if running:
        log_path = dw_path / 'glb' / 'dw-current.txt'
        log_data = read_session_log(log_path)
        started = log_data.get('meta', {}).get('started', 'unknown')
        events = len(log_data.get('events', []))
        print(f"Watcher: RUNNING (PID: {pid})")
        print(f"Started: {started}")
        print(f"Events: {events}")
    else:
        print("Watcher: STOPPED")

    print()

    # Tracked files
    loc_folder = dw_path / 'loc'
    loc_files = list(loc_folder.glob('*.txt'))

    tracked = 0
    unbumped = []

    for loc_path in loc_files:
        loc_data = read_loc(loc_path)
        if '-' in loc_path.stem:  # Skip deleted/archived files
            continue

        tracked += 1
        saves = loc_data.get('meta', {}).get('saves', 0)
        if saves > 0:
            version = loc_data.get('meta', {}).get('version', 'av1r1')
            unbumped.append((loc_path.stem, version, saves))

    print(f"Tracked files: {tracked}")

    if unbumped:
        print(f"\nUnbumped saves:")
        for name, version, saves in unbumped:
            print(f"  {name}.txt ({version}, {saves} saves)")


def cmd_track(args):
    """Show file history"""
    dw_path = get_dw_path()

    if not dw_path.exists():
        print("No .dw/ folder. Run 'dw setup' first.")
        return

    if len(args) < 1:
        print("Usage: dw track <file> [-l] [-t] [-a]")
        return

    # Parse args
    file_arg = None
    show_loc = '-l' in args
    show_txt = '-t' in args
    show_all = '-a' in args

    for arg in args:
        if not arg.startswith('-'):
            file_arg = arg
            break

    if not file_arg:
        print("Please specify a file")
        return

    # Find the file
    stem = Path(file_arg).stem
    loc_path = dw_path / 'loc' / f'{stem}.txt'

    if not loc_path.exists():
        print(f"No history found for: {file_arg}")
        return

    loc_data = read_loc(loc_path)

    if show_all:
        # Show all paths
        txt_path = Path.cwd() / f'{stem}.txt'
        snp_path = dw_path / 'snp' / f'{stem}.txt'
        print(f"txt: {txt_path}")
        print(f"loc: {loc_path}")
        print(f"snp: {snp_path}")
        return

    if show_loc:
        # Show full loc file
        print(read_file(loc_path))
        return

    if show_txt:
        # Show txt content
        txt_path = Path.cwd() / f'{stem}.txt'
        if txt_path.exists():
            print(read_file(txt_path))
        else:
            print(f"File not found: {txt_path}")
        return

    # Default: show history summary
    meta = loc_data.get('meta', {})
    print(f"File: {meta.get('file', stem + '.txt')}")
    print(f"Version: {meta.get('version', 'unknown')}")
    print(f"Saves: {meta.get('saves', 0)}")
    print(f"Updated: {meta.get('updated', 'unknown')}")
    print()

    history = loc_data.get('history', [])
    print(f"History ({len(history)} entries):")
    for entry in history[-10:]:  # Show last 10
        action = entry.get('action', '')
        changes = entry.get('changes', [])
        added = len([c for c in changes if c.get('type') == 'add'])
        removed = len([c for c in changes if c.get('type') == 'rem'])
        if added or removed:
            print(f"  {action} +{added} -{removed}")
        else:
            print(f"  {action}")


def cmd_head(args):
    """Add header to specific file"""
    if '-f' not in args:
        print("Usage: dw head -f <file>")
        return

    idx = args.index('-f')
    if idx + 1 >= len(args):
        print("Please specify a file")
        return

    file_path = Path(args[idx + 1])

    if not file_path.exists():
        print(f"File not found: {file_path}")
        return

    if add_header(file_path):
        print(f"Added header to: {file_path}")
    else:
        print(f"Header already exists: {file_path}")


def cmd_remove(args):
    """Remove file from tracking"""
    dw_path = get_dw_path()

    if not dw_path.exists():
        print("No .dw/ folder. Run 'dw setup' first.")
        return

    if '-f' not in args:
        print("Usage: dw remove -f <file>")
        return

    idx = args.index('-f')
    if idx + 1 >= len(args):
        print("Please specify a file")
        return

    file_arg = args[idx + 1]
    stem = Path(file_arg).stem
    ts = get_timestamp_compact()

    # Rename snapshot
    snp_path = dw_path / 'snp' / f'{stem}.txt'
    if snp_path.exists():
        snp_new = dw_path / 'snp' / f'{stem}-{ts}.txt'
        snp_path.rename(snp_new)

    # Rename loc/*.txt
    loc_path = dw_path / 'loc' / f'{stem}.txt'
    if loc_path.exists():
        loc_new = dw_path / 'loc' / f'{stem}-{ts}.txt'
        loc_path.rename(loc_new)
        print(f"Removed from tracking: {file_arg}")
    else:
        print(f"Not tracked: {file_arg}")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("DocWire - Git for docs, but automatic")
        print("\nUsage: dw <command>")
        print("\nCore:")
        print("  start     Start watcher (init + sync + bump + watch)")
        print("  start -f  Start watcher (foreground)")
        print("  stop      Stop watcher (current folder)")
        print("  bump      Bump revision")
        print("  status    Show status")
        print("  track     Show file history")
        print("  head      Add header to file")
        print("\nFix & Maintain:")
        print("  fix           Scan for issues")
        print("  fix -y        Auto-fix all issues")
        print("  fix -s        Sync + repair (refresh metadata)")
        print("  fix -r        Remove all orphans")
        print("  fix -r -f <file>  Remove specific file")
        print("  archive       Move history to acv/")
        print("  compact       Generate stats summary")
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == 'init':
        # Hidden but still works
        cmd_init()
    elif cmd == 'start':
        cmd_start()
    elif cmd == 'stop':
        cmd_stop()
    elif cmd == 'bump':
        cmd_bump(args)
    elif cmd == 'status':
        cmd_status()
    elif cmd == 'track':
        cmd_track(args)
    elif cmd == 'head':
        cmd_head(args)
    elif cmd == 'fix':
        cmd_fix(args)
    elif cmd == 'archive':
        cmd_archive(args)
    elif cmd == 'compact':
        cmd_compact(args)
    else:
        print(f"Unknown command: {cmd}")
        print("Run 'dw' for help")


if __name__ == '__main__':
    main()
