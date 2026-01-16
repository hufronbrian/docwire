"""
DocWire Compact - Generate stats summary for loc/*.txt
"""

from pathlib import Path
from utils import (
    get_dw_path, read_loc, write_file, format_dwml_meta,
    get_timestamp, get_stem
)


def calc_stats(loc_data):
    """
    Calculate stats from loc/*.txt data.
    Returns dict with stats.
    """
    history = loc_data.get('history', [])
    meta = loc_data.get('meta', {})

    total_saves = 0
    total_bumps = 0
    total_added = 0
    total_removed = 0
    first_ts = None
    last_ts = None

    for entry in history:
        action = entry.get('action', '')
        changes = entry.get('changes', [])

        # Extract timestamp from action (format: "2026-01-15T10:00:00Z ...")
        if action and len(action) >= 20:
            ts = action[:20]
            if first_ts is None:
                first_ts = ts
            last_ts = ts

        # Count saves and bumps from action string
        if 'save:' in action or 'initialized' in action or 'created' in action:
            total_saves += 1
            total_added += len([c for c in changes if c.get('type') == 'add'])
            total_removed += len([c for c in changes if c.get('type') == 'rem'])
        elif 'bumped' in action:
            total_bumps += 1

    return {
        'version': meta.get('version', 'av1r1'),
        'total_saves': total_saves,
        'total_bumps': total_bumps,
        'lines_added': total_added,
        'lines_removed': total_removed,
        'first_entry': first_ts[:10] if first_ts else None,
        'last_entry': last_ts[:10] if last_ts else None,
        'history_entries': len(history)
    }


def do_compact_file(loc_path, silent=False):
    """
    Generate compact stats for a single loc/*.txt file.
    Writes to cmp/{stem}.txt
    Returns True if generated.
    """
    dw_path = get_dw_path()
    cmp_folder = dw_path / 'cmp'
    cmp_folder.mkdir(parents=True, exist_ok=True)

    loc_path = Path(loc_path)
    if not loc_path.exists():
        return False

    loc_data = read_loc(loc_path)
    stem = loc_path.stem

    stats = calc_stats(loc_data)
    stats['file'] = loc_data.get('meta', {}).get('file', f'./{stem}.txt')
    stats['generated'] = get_timestamp()

    # Write as simple DWML meta block
    cmp_path = cmp_folder / f'{stem}.txt'
    cmp_meta = {
        'file': stats['file'],
        'version': stats['version'],
        'generated': stats['generated'],
        'total_saves': str(stats['total_saves']),
        'total_bumps': str(stats['total_bumps']),
        'lines_added': str(stats['lines_added']),
        'lines_removed': str(stats['lines_removed']),
        'history_entries': str(stats['history_entries'])
    }
    if stats['first_entry']:
        cmp_meta['first_entry'] = stats['first_entry']
    if stats['last_entry']:
        cmp_meta['last_entry'] = stats['last_entry']

    write_file(cmp_path, format_dwml_meta(cmp_meta) + '\n')

    if not silent:
        print(f"[COMPACT] {stem}.txt")
        print(f"  Version: {stats['version']}")
        print(f"  Saves: {stats['total_saves']}, Bumps: {stats['total_bumps']}")
        print(f"  Lines: +{stats['lines_added']} -{stats['lines_removed']}")
        if stats['first_entry'] and stats['last_entry']:
            print(f"  Range: {stats['first_entry']} to {stats['last_entry']}")

    return True


def do_compact_all(silent=False):
    """
    Generate compact stats for all loc/*.txt files.
    Returns count of compacted files.
    """
    dw_path = get_dw_path()
    loc_folder = dw_path / 'loc'

    if not loc_folder.exists():
        return 0

    compacted_count = 0

    for loc_path in loc_folder.glob('*.txt'):
        if do_compact_file(loc_path, silent=silent):
            compacted_count += 1
        if not silent:
            print()

    return compacted_count


def cmd_compact(args):
    """
    CLI entry point for dw compact
    args: -f <file> (compact specific file)
    """
    dw_path = get_dw_path()

    if not dw_path.exists():
        print("No .dw/ folder. Run 'dw setup' first.")
        return

    # Check for -f flag
    if '-f' in args:
        idx = args.index('-f')
        if idx + 1 >= len(args):
            print("Usage: dw compact -f <file>")
            return

        file_arg = args[idx + 1]
        stem = Path(file_arg).stem
        loc_path = dw_path / 'loc' / f'{stem}.txt'

        if not loc_path.exists():
            print(f"No history found for: {file_arg}")
            return

        do_compact_file(loc_path)
        return

    # Compact all files
    compacted = do_compact_all()

    if compacted == 0:
        print("No files to compact")
    else:
        print(f"Generated stats for {compacted} file(s)")
