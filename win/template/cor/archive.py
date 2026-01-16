"""
DocWire Archive - Move history to acv/ folder
"""

from pathlib import Path
from utils import (
    get_dw_path, read_config, read_loc, write_loc,
    get_timestamp, get_timestamp_compact, get_stem
)


def do_archive_file(loc_path, silent=False):
    """
    Archive a single loc/*.txt file:
    - Move history to acv/{stem}-{timestamp}.txt
    - Reset loc/*.txt to metadata only
    - Update archive: section in loc/*.txt

    Returns True if archived, False if nothing to archive
    """
    dw_path = get_dw_path()
    acv_folder = dw_path / 'acv'
    acv_folder.mkdir(parents=True, exist_ok=True)

    loc_path = Path(loc_path)
    if not loc_path.exists():
        return False

    loc_data = read_loc(loc_path)
    history = loc_data.get('history', [])

    if not history:
        if not silent:
            print(f"No history to archive: {loc_path.stem}")
        return False

    stem = loc_path.stem
    timestamp = get_timestamp_compact()
    ts = get_timestamp()

    # Create archive file
    acv_path = acv_folder / f'{stem}-{timestamp}.txt'
    acv_data = {
        'meta': {
            'archived': ts,
            'entries': str(len(history)),
            'source': f'./.dw/loc/{stem}.txt'
        },
        'history': history,
        'archive': []
    }
    write_loc(acv_path, acv_data)

    # Update loc/*.txt - keep meta, clear history, add archive ref
    loc_data['archive'].append(f'./.dw/acv/{stem}-{timestamp}.txt')

    loc_data['history'] = [{
        'action': f'{ts} archived {len(history)} entries to acv/{stem}-{timestamp}.txt',
        'changes': []
    }]

    write_loc(loc_path, loc_data)

    if not silent:
        print(f"[ARCHIVED] {stem}.txt - {len(history)} entries -> acv/{stem}-{timestamp}.txt")

    return True


def do_archive_all(silent=False):
    """
    Archive all loc/*.txt files that exceed threshold.
    Returns count of archived files.
    """
    dw_path = get_dw_path()
    loc_folder = dw_path / 'loc'

    if not loc_folder.exists():
        return 0

    # Get config for threshold
    config = read_config()
    threshold = config.get('archive_threshold', 100)

    archived_count = 0

    for loc_path in loc_folder.glob('*.txt'):
        loc_data = read_loc(loc_path)
        history = loc_data.get('history', [])

        if len(history) > threshold:
            if do_archive_file(loc_path, silent=silent):
                archived_count += 1

    return archived_count


def cmd_archive(args):
    """
    CLI entry point for dw archive
    args: -f <file> (archive specific file)
    """
    dw_path = get_dw_path()

    if not dw_path.exists():
        print("No .dw/ folder. Run 'dw setup' first.")
        return

    # Check for -f flag
    if '-f' in args:
        idx = args.index('-f')
        if idx + 1 >= len(args):
            print("Usage: dw archive -f <file>")
            return

        file_arg = args[idx + 1]
        stem = Path(file_arg).stem
        loc_path = dw_path / 'loc' / f'{stem}.txt'

        if not loc_path.exists():
            print(f"No history found for: {file_arg}")
            return

        do_archive_file(loc_path)
        return

    # Archive all files over threshold
    archived = do_archive_all()

    if archived == 0:
        print("No files to archive (none over threshold)")
    else:
        print(f"\nArchived {archived} file(s)")
