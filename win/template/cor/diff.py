"""
DocWire Diff - Calculate diff between file versions using difflib
"""

import difflib


def calc_diff(old_content, new_content):
    """
    Calculate diff between old and new content
    Returns dict with 'added' and 'removed' lists of lines
    """
    old_lines = old_content.splitlines(keepends=False)
    new_lines = new_content.splitlines(keepends=False)

    differ = difflib.Differ()
    diff = list(differ.compare(old_lines, new_lines))

    added = []
    removed = []

    for line in diff:
        if line.startswith('+ '):
            added.append(line[2:])
        elif line.startswith('- '):
            removed.append(line[2:])
        # Lines starting with '? ' are hints, ignore
        # Lines starting with '  ' are unchanged, ignore

    return {
        'added': added,
        'removed': removed
    }


def has_changes(old_content, new_content):
    """Check if there are any differences between old and new"""
    diff = calc_diff(old_content, new_content)
    return len(diff['added']) > 0 or len(diff['removed']) > 0


def diff_stats(old_content, new_content):
    """
    Get stats about changes
    Returns dict with counts
    """
    diff = calc_diff(old_content, new_content)
    return {
        'added': len(diff['added']),
        'removed': len(diff['removed'])
    }
