"""
DocWire Bump - Version parsing and bumping logic
"""

import re


def parse_version(version_str):
    """
    Parse avNrN format into dict
    Returns {'base': 'a', 'major': 1, 'revision': 1} or None if invalid
    """
    if not version_str:
        return None

    pattern = r'^([a-z])v(\d+)r(\d+)$'
    match = re.match(pattern, version_str.strip())

    if not match:
        return None

    return {
        'base': match.group(1),
        'major': int(match.group(2)),
        'revision': int(match.group(3))
    }


def format_version(parsed):
    """Convert parsed version dict back to string"""
    if not parsed:
        return "av1r1"
    return f"{parsed['base']}v{parsed['major']}r{parsed['revision']}"


def increment_r(version_str):
    """
    Increment revision: av1r1 -> av1r2
    Returns new version string
    """
    parsed = parse_version(version_str)
    if not parsed:
        return "av1r1"

    parsed['revision'] += 1
    return format_version(parsed)


def increment_v(version_str):
    """
    Increment major (for merge): av1r5 -> av2r1
    Returns new version string
    """
    parsed = parse_version(version_str)
    if not parsed:
        return "av1r1"

    parsed['major'] += 1
    parsed['revision'] = 1
    return format_version(parsed)


def check_rebase(old_version, new_version):
    """
    Check if base letter changed (rebase detected)
    Returns True if rebased (e.g., av3r5 -> bv1r1)
    """
    old_parsed = parse_version(old_version)
    new_parsed = parse_version(new_version)

    if not old_parsed or not new_parsed:
        return False

    return old_parsed['base'] != new_parsed['base']


def get_base(version_str):
    """Get base letter from version string"""
    parsed = parse_version(version_str)
    return parsed['base'] if parsed else 'a'


def is_valid_version(version_str):
    """Check if version string is valid format"""
    return parse_version(version_str) is not None
