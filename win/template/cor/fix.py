"""
DocWire Fix - Scan for issues and auto-fix
"""

from pathlib import Path
from utils import (
    get_dw_path, get_txt_files, read_file, write_file, read_config,
    read_loc, write_loc, write_index, ensure_folders,
    get_timestamp, get_timestamp_compact, get_relative_path, get_stem,
    path_to_storage_name, storage_name_to_path
)
from head import has_header, add_header, parse_header
from sync import parse_refs, get_ref_versions, do_sync


def scan_issues():
    """
    Scan for all issues.
    Returns list of dicts: {type, tag, file, detail, fixable}
    """
    dw_path = get_dw_path()
    loc_folder = dw_path / 'loc'
    issues = []

    if not dw_path.exists():
        return issues

    # Get config for threshold
    config = read_config()
    threshold = config.get('archive_threshold', 100)

    # Get current ref versions for STALE detection
    current_ref_versions = get_ref_versions(dw_path)

    # Check each loc/*.txt
    for loc_path in loc_folder.glob('*.txt'):
        storage_name = loc_path.stem

        # Skip timestamped backup files (like myfile-20260115-121951.txt)
        if '-' in storage_name and len(storage_name.split('-')[-1]) == 15:
            continue

        # Convert storage name back to path for subfolder support
        txt_rel = storage_name_to_path(storage_name)
        txt_path = Path.cwd() / txt_rel.lstrip('./')
        loc_data = read_loc(loc_path)

        # Get display name from metadata or storage name
        display_name = loc_data.get('meta', {}).get('file', txt_rel)

        # [AF] ORPHAN - loc exists but txt deleted
        if not txt_path.exists():
            issues.append({
                'type': 'ORPHAN',
                'tag': 'AF',
                'file': f'{display_name} (loc)',
                'detail': 'no .txt found',
                'fixable': True,
                'loc_path': loc_path
            })
            continue

        # [AF] LARGE - history too big
        history = loc_data.get('history', [])
        if len(history) > threshold:
            issues.append({
                'type': 'LARGE',
                'tag': 'AF',
                'file': display_name,
                'detail': f'{len(history)} entries',
                'fixable': True,
                'loc_path': loc_path
            })

        # Check refs for STALE and BROKEN
        content = read_file(txt_path)
        if not has_header(content):
            continue

        fields = parse_header(content)
        refs = parse_refs(fields.get('refs', ''))
        stored_ref_versions = loc_data.get('meta', {}).get('ref_versions', {})

        stale_refs = []
        broken_refs = []

        for ref in refs:
            ref_path = Path.cwd() / ref.lstrip('./')

            # [MF] BROKEN - ref to non-existent file
            if not ref_path.exists():
                broken_refs.append(ref)
                continue

            # [MF] STALE - ref version changed since last save
            if ref in stored_ref_versions and ref in current_ref_versions:
                if stored_ref_versions[ref] != current_ref_versions[ref]:
                    stale_refs.append(ref)

        if stale_refs:
            # Get just filenames for display
            stale_names = [Path(r).name for r in stale_refs]
            issues.append({
                'type': 'STALE',
                'tag': 'MF',
                'file': display_name,
                'detail': f'refs changed: {", ".join(stale_names)}',
                'fixable': False
            })

        if broken_refs:
            broken_names = [Path(r).name for r in broken_refs]
            issues.append({
                'type': 'BROKEN',
                'tag': 'MF',
                'file': display_name,
                'detail': f'refs not found: {", ".join(broken_names)}',
                'fixable': False
            })

    return issues


def do_fix_large(issue):
    """Auto-fix LARGE: archive the file"""
    from archive import do_archive_file
    loc_path = issue.get('loc_path')
    if loc_path:
        do_archive_file(loc_path, silent=True)
        return True
    return False


def do_fix_orphan(issue):
    """Auto-fix ORPHAN: delete the loc file"""
    loc_path = issue.get('loc_path')
    if loc_path and loc_path.exists():
        loc_path.unlink()
        return True
    return False


def auto_fix(issues):
    """
    Auto-fix all fixable issues.
    Returns (fixed_count, skipped_count)
    """
    fixed = 0
    skipped = 0

    for issue in issues:
        if not issue['fixable']:
            skipped += 1
            continue

        success = False
        if issue['type'] == 'LARGE':
            success = do_fix_large(issue)
        elif issue['type'] == 'ORPHAN':
            success = do_fix_orphan(issue)

        if success:
            print(f"[FIXED] {issue['file']} - {issue['type'].lower()}")
            fixed += 1
        else:
            skipped += 1

    return fixed, skipped


def do_sync_repair(silent=False):
    """
    Sync + repair: refresh metadata and create missing snp/loc.
    This is like init but without adding headers to files.
    """
    dw_path = get_dw_path()

    if not dw_path.exists():
        if not silent:
            print("No .dw/ folder. Run 'dw setup' first.")
        return 0

    ensure_folders()

    txt_files = get_txt_files()
    repaired = 0

    for txt_file in txt_files:
        content = read_file(txt_file)

        if not has_header(content):
            continue

        storage_name = path_to_storage_name(txt_file)
        rel_path = get_relative_path(txt_file)

        # Create snp if missing (use storage name for subfolder support)
        snp_path = dw_path / 'snp' / f'{storage_name}.txt'
        if not snp_path.exists():
            write_file(snp_path, content)
            if not silent:
                print(f"[+] Created snp: {rel_path}")
            repaired += 1

        # Create loc if missing
        loc_path = dw_path / 'loc' / f'{storage_name}.txt'
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
            if not silent:
                print(f"[+] Created loc: {rel_path}")
            repaired += 1

    # Run sync to update metadata
    synced, _ = do_sync(silent=True)

    if not silent:
        if repaired > 0:
            print(f"\nRepaired {repaired} missing files")
        print(f"Synced {synced} files")

    return repaired


def do_remove_orphans(silent=False):
    """Remove all orphan loc files (loc without matching .txt)
    Note: /snp is kept for potential file recovery
    """
    dw_path = get_dw_path()
    loc_folder = dw_path / 'loc'
    removed = 0

    for loc_path in loc_folder.glob('*.txt'):
        storage_name = loc_path.stem
        # Skip already-removed files (have timestamp in name)
        if '-' in storage_name and len(storage_name.split('-')[-1]) == 15:
            continue

        # Convert storage name to path for subfolder support
        txt_rel = storage_name_to_path(storage_name)
        txt_path = Path.cwd() / txt_rel.lstrip('./')
        if not txt_path.exists():
            # Only remove loc, keep snp for recovery
            loc_path.unlink()
            if not silent:
                print(f"[-] Removed orphan: {txt_rel}")
            removed += 1

    if not silent and removed > 0:
        print(f"\nRemoved {removed} orphan(s)")
        print("Note: /snp files kept for recovery")

    return removed


def do_remove_file(file_arg, silent=False):
    """Remove specific file from tracking"""
    dw_path = get_dw_path()
    file_path = Path(file_arg)
    ts = get_timestamp_compact()

    # Get storage name - support both direct path and storage name
    if file_path.exists():
        storage_name = path_to_storage_name(file_path)
    else:
        storage_name = file_path.stem

    removed = False

    # Rename snapshot (keep as backup)
    snp_path = dw_path / 'snp' / f'{storage_name}.txt'
    if snp_path.exists():
        snp_new = dw_path / 'snp' / f'{storage_name}-{ts}.txt'
        snp_path.rename(snp_new)
        removed = True

    # Rename loc (keep as backup)
    loc_path = dw_path / 'loc' / f'{storage_name}.txt'
    if loc_path.exists():
        loc_new = dw_path / 'loc' / f'{storage_name}-{ts}.txt'
        loc_path.rename(loc_new)
        removed = True

    if not silent:
        if removed:
            print(f"Removed from tracking: {file_arg}")
        else:
            print(f"Not tracked: {file_arg}")

    return removed


def cmd_fix(args):
    """
    CLI entry point for dw fix
    Flags:
      -y        Auto-fix all issues
      -n        Report only (no prompt)
      -s        Sync + repair (refresh metadata, create missing snp/loc)
      -r        Remove all orphans
      -r -f <file>  Remove specific file from tracking
    """
    dw_path = get_dw_path()

    if not dw_path.exists():
        print("No .dw/ folder. Run 'dw setup' first.")
        return

    # Handle -s (sync + repair)
    if '-s' in args:
        do_sync_repair(silent=False)
        return

    # Handle -r (remove)
    if '-r' in args:
        if '-f' in args:
            # Remove specific file
            idx = args.index('-f')
            if idx + 1 < len(args):
                file_arg = args[idx + 1]
                do_remove_file(file_arg, silent=False)
            else:
                print("Usage: dw fix -r -f <file>")
        else:
            # Remove all orphans
            do_remove_orphans(silent=False)
        return

    # Default: scan and report issues
    issues = scan_issues()

    if not issues:
        print("No issues found.")
        return

    # Separate AF and MF
    af_issues = [i for i in issues if i['tag'] == 'AF']
    mf_issues = [i for i in issues if i['tag'] == 'MF']

    # Print scan results
    print("\n=== SCAN RESULTS\n")

    for issue in issues:
        print(f"[{issue['tag']}] {issue['type']} {issue['file']} - {issue['detail']}")

    print(f"\n---")
    print(f"Auto-fixable [AF]: {len(af_issues)}")
    print(f"Manual fix [MF]: {len(mf_issues)}")

    # Handle flags
    if '-n' in args:
        # Report only
        return

    if '-y' in args:
        # Auto-fix without prompt
        if af_issues:
            print()
            fixed, skipped = auto_fix(issues)
            print(f"\nDone. {fixed} fixed, {skipped} need manual attention.")
        return

    # Interactive prompt
    if af_issues:
        print()
        choice = input("Auto-fix now? [y/n]: ").strip().lower()

        if choice == 'y':
            print()
            fixed, skipped = auto_fix(issues)
            print(f"\nDone. {fixed} fixed, {skipped} need manual attention.")
        else:
            print("\nRun 'dw fix' again when ready.")
    else:
        print("\nNo auto-fixable issues. Manual fixes needed.")
