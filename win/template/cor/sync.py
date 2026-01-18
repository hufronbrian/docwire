"""
DocWire Sync - Re-scan headers and update metadata
"""

from pathlib import Path
from utils import (
    get_dw_path, get_txt_files, read_file, read_config,
    read_loc, write_loc, write_index,
    get_timestamp, get_relative_path, get_stem,
    path_to_storage_name, storage_name_to_path
)
from head import has_header, parse_header


def get_ref_versions(dw_path):
    """
    Build dict of file -> version from all loc/*.txt
    Used to detect STALE refs
    """
    ref_versions = {}
    loc_folder = dw_path / 'loc'

    for loc_path in loc_folder.glob('*.txt'):
        loc_data = read_loc(loc_path)
        meta = loc_data.get('meta', {})
        file_path = meta.get('file', '')
        version = meta.get('version', 'av1r1')
        if file_path:
            ref_versions[file_path] = version

    return ref_versions


def parse_refs(refs_string):
    """
    Parse dw:refs field value into list of paths
    Format: ./file1.txt|./file2.txt|
    """
    if not refs_string:
        return []
    return [r.strip() for r in refs_string.split('|') if r.strip()]


def do_sync(silent=False):
    """
    Sync all tracked .txt files:
    - Parse headers
    - Update loc/*.txt metadata
    - Store ref versions for STALE detection
    - Rebuild index.txt

    Returns: (synced_count, issues_count)
    """
    dw_path = get_dw_path()
    loc_folder = dw_path / 'loc'

    if not dw_path.exists():
        if not silent:
            print("No .dw/ folder. Run 'dw setup' first.")
        return 0, 0

    # Get all .txt files with headers
    txt_files = get_txt_files()
    tracked = []
    issues = 0

    # Get config for threshold
    config = read_config()
    threshold = config.get('archive_threshold', 100)

    for txt_file in txt_files:
        content = read_file(txt_file)

        if not has_header(content):
            continue

        fields = parse_header(content)
        storage_name = path_to_storage_name(txt_file)
        loc_path = loc_folder / f'{storage_name}.txt'

        if not loc_path.exists():
            # File has header but no loc/*.txt - skip (needs dw init)
            continue

        # Read current loc data
        loc_data = read_loc(loc_path)

        # Update metadata from header
        loc_data['meta']['file'] = get_relative_path(txt_file)
        loc_data['meta']['version'] = fields.get('version', loc_data['meta'].get('version', 'av1r1'))

        # Store current ref versions for STALE detection
        refs = parse_refs(fields.get('refs', ''))
        if refs:
            ref_versions = get_ref_versions(dw_path)
            loc_data['meta']['ref_versions'] = {
                ref: ref_versions.get(ref, 'unknown')
                for ref in refs
            }

        # Check for issues (for [!] count)
        history = loc_data.get('history', [])
        if len(history) > threshold:
            issues += 1

        write_loc(loc_path, loc_data)
        tracked.append({
            'file': get_relative_path(txt_file),
            'version': fields.get('version', 'av1r1')
        })

    # Check for orphan loc files
    for loc_path in loc_folder.glob('*.txt'):
        storage_name = loc_path.stem
        # Skip archived files (contain timestamp suffix)
        if '-' in storage_name and len(storage_name.split('-')[-1]) == 15:
            continue
        # Convert storage name back to path
        txt_rel = storage_name_to_path(storage_name)
        txt_path = Path.cwd() / txt_rel.lstrip('./')
        if not txt_path.exists():
            issues += 1

    # Check for STALE and BROKEN refs
    for txt_file in txt_files:
        content = read_file(txt_file)
        if not has_header(content):
            continue

        fields = parse_header(content)
        storage_name = path_to_storage_name(txt_file)
        loc_path = loc_folder / f'{storage_name}.txt'

        if not loc_path.exists():
            continue

        loc_data = read_loc(loc_path)
        refs = parse_refs(fields.get('refs', ''))
        stored_ref_versions = loc_data.get('meta', {}).get('ref_versions', {})
        current_ref_versions = get_ref_versions(dw_path)

        for ref in refs:
            ref_path = Path.cwd() / ref.lstrip('./')
            if not ref_path.exists():
                # BROKEN
                issues += 1
            elif ref in stored_ref_versions and ref in current_ref_versions:
                if stored_ref_versions[ref] != current_ref_versions[ref]:
                    # STALE
                    issues += 1

    # Rebuild index.txt
    write_index(tracked)

    if not silent:
        print(f"Synced {len(tracked)} files")

    return len(tracked), issues


def cmd_sync():
    """CLI entry point for dw sync"""
    do_sync(silent=False)
