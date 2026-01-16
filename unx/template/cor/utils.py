"""
DocWire Utils - Shared helper functions
"""

import os
import re
from pathlib import Path
from datetime import datetime, timezone


def get_dw_path():
    """Return .dw/ path relative to current working directory"""
    return Path.cwd() / ".dw"


def get_parent_path():
    """Return parent folder (where .txt files live)"""
    return Path.cwd()


# ============================================================
# DWML (DontWorry Markup Language) Functions - v1.0
# ============================================================

# Block patterns
BLOCK_OPEN_PATTERN = re.compile(r'=d=(\w+)=w=')
BLOCK_CLOSE_PATTERN = re.compile(r'=q=(\w+)=e=')

# Container patterns
CONTAINER_OPEN = '=dw='
CONTAINER_CLOSE = '=wd='

# Inline patterns
CONTENT_PATTERN = re.compile(r'=x=\s*(.*?)\s*=z=')
COMMENT_PATTERN = re.compile(r'=#=(.*?)=o=')
ADDED_PATTERN = re.compile(r'=\+=(.*?)=o=')
REMOVED_PATTERN = re.compile(r'=-=(.*?)=o=')

# Value patterns
VALUE_PATTERN = re.compile(r'(\w+);\|([^|]*)\|;')
VALUE_LIST_PATTERN = re.compile(r';\|([^|]*)\|;')


def has_dwml_block(content, name):
    """Check if content has block with name"""
    pattern = re.compile(rf'=d={name}=w=.*?=q={name}=e=', re.DOTALL)
    return bool(pattern.search(content))


def parse_dwml_block(content, name):
    """Parse =d=name=w=...=q=name=e= block into dict"""
    result = {}
    pattern = re.compile(rf'=d={name}=w=(.*?)=q={name}=e=', re.DOTALL)
    match = pattern.search(content)
    if match:
        block_content = match.group(1)
        for line in block_content.split('\n'):
            line = line.strip()
            if not line:
                continue
            # Skip comments
            if line.startswith('=#='):
                continue
            # Parse =x= key;|value|; =z= patterns
            content_match = CONTENT_PATTERN.search(line)
            if content_match:
                inner = content_match.group(1)
                # Extract key;|value|; pairs
                for val_match in VALUE_PATTERN.finditer(inner):
                    key = val_match.group(1)
                    value = val_match.group(2)
                    # Handle multiple values with ,;|
                    all_values = VALUE_LIST_PATTERN.findall(inner[inner.find(key):])
                    if len(all_values) > 1:
                        result[key] = all_values
                    else:
                        result[key] = value
    return result


def format_dwml_block(name, data, comments=None):
    """Format dict as =d=name=w=...=q=name=e= block"""
    lines = [f'=d={name}=w=']
    if comments:
        for cmt in comments:
            lines.append(f'=#= {cmt} =o=')
    for key, val in data.items():
        if isinstance(val, list):
            values_str = ','.join(f';|{v}|;' for v in val)
            lines.append(f'=x= {key}{values_str} =z=')
        else:
            lines.append(f'=x= {key};|{val}|; =z=')
    lines.append(f'=q={name}=e=')
    return '\n'.join(lines)


def parse_dwml_meta(content):
    """Parse =d=meta=w=...=q=meta=e= block into dict"""
    return parse_dwml_block(content, 'meta')


def format_dwml_meta(meta):
    """Format dict as =d=meta=w=...=q=meta=e= block"""
    return format_dwml_block('meta', meta)


def parse_dwml_history(content):
    """Parse =d=history=w=...=q=history=e= block into list of entries"""
    entries = []
    pattern = re.compile(r'=d=history=w=(.*?)=q=history=e=', re.DOTALL)
    match = pattern.search(content)
    if match:
        block_content = match.group(1)
        # Find all =dw=...=wd= containers
        containers = re.findall(r'=dw=(.*?)=wd=', block_content, re.DOTALL)
        for container in containers:
            entry = {'action': '', 'changes': [], 'comments': []}
            # Parse action line =x= key;|value|; =z=
            content_match = CONTENT_PATTERN.search(container)
            if content_match:
                inner = content_match.group(1).strip()
                # Try to extract timestamp;|action|; format
                val_match = VALUE_LIST_PATTERN.search(inner)
                if val_match:
                    # Format: timestamp;|action|;
                    key_part = inner[:inner.find(';|')].strip()
                    val_part = val_match.group(1)
                    entry['action'] = f'{key_part} {val_part}'
                else:
                    entry['action'] = inner
            # Parse added lines =+= ... =o=
            for add_match in ADDED_PATTERN.finditer(container):
                entry['changes'].append({'type': 'add', 'line': add_match.group(1)})
            # Parse removed lines =-= ... =o=
            for rem_match in REMOVED_PATTERN.finditer(container):
                entry['changes'].append({'type': 'rem', 'line': rem_match.group(1)})
            # Parse comments =#= ... =o=
            for cmt_match in COMMENT_PATTERN.finditer(container):
                entry['comments'].append(cmt_match.group(1).strip())
            entries.append(entry)
    return entries


def format_dwml_comment(text):
    """Format a comment as =#= ... =o="""
    return f'=#= {text} =o='


def format_dwml_entry(action, changes=None, comments=None):
    """Format a single history entry as =dw=...=wd= block"""
    lines = ['=dw=']
    # Parse action to extract timestamp and action text
    # Expected format: "2026-01-15T10:00:00Z some action"
    parts = action.split(' ', 1)
    if len(parts) == 2:
        timestamp, action_text = parts
        lines.append(f'=x= {timestamp};|{action_text}|; =z=')
    else:
        lines.append(f'=x= action;|{action}|; =z=')
    if changes:
        for ch in changes:
            if ch['type'] == 'add':
                lines.append(f'=+={ch["line"]}=o=')
            elif ch['type'] == 'rem':
                lines.append(f'=-={ch["line"]}=o=')
    if comments:
        for cmt in comments:
            lines.append(f'=#= {cmt} =o=')
    lines.append('=wd=')
    return '\n'.join(lines)


def format_dwml_history(entries):
    """Format list of entries as =d=history=w=...=q=history=e= block"""
    lines = ['=d=history=w=']
    for entry in entries:
        lines.append(format_dwml_entry(entry['action'], entry.get('changes'), entry.get('comments')))
    lines.append('=q=history=e=')
    return '\n'.join(lines)


def parse_dwml_config(content):
    """Parse =d=config=w=...=q=config=e= block into dict"""
    return parse_dwml_block(content, 'config')


def format_dwml_config(config):
    """Format dict as =d=config=w=...=q=config=e= block"""
    return format_dwml_block('config', config)


def read_dwml(path):
    """Read DWML file, return dict with meta, history, config sections"""
    content = read_file(path)
    if not content:
        return {'meta': {}, 'history': [], 'config': {}}
    return {
        'meta': parse_dwml_meta(content),
        'history': parse_dwml_history(content),
        'config': parse_dwml_config(content)
    }


def write_dwml(path, data):
    """Write DWML file from dict with meta, history, config sections"""
    parts = []
    if data.get('meta'):
        parts.append(format_dwml_meta(data['meta']))
    if data.get('config'):
        parts.append(format_dwml_config(data['config']))
    if data.get('history'):
        parts.append(format_dwml_history(data['history']))
    write_file(path, '\n\n'.join(parts) + '\n')


def append_dwml_entry(path, action, changes=None):
    """Append a history entry to existing DWML file"""
    data = read_dwml(path)
    entry = {'action': action, 'changes': changes or []}
    data['history'].append(entry)
    write_dwml(path, data)


# ============================================================
# Config File Helpers
# ============================================================

def read_config():
    """Read config.txt and return parsed dict"""
    dw_path = get_dw_path()
    config_path = dw_path / 'config.txt'
    content = read_file(config_path)
    if not content:
        return {'ignore': [], 'archive_threshold': 100}

    raw = parse_dwml_config(content)
    config = {}

    # Parse ignore patterns (list or pipe-separated string)
    if 'ignore' in raw:
        if isinstance(raw['ignore'], list):
            config['ignore'] = raw['ignore']
        else:
            config['ignore'] = [p.strip() for p in raw['ignore'].split(',') if p.strip()]
    else:
        config['ignore'] = []

    # Parse archive_threshold (int)
    if 'archive_threshold' in raw:
        try:
            config['archive_threshold'] = int(raw['archive_threshold'])
        except ValueError:
            config['archive_threshold'] = 100
    else:
        config['archive_threshold'] = 100

    return config


# ============================================================
# Loc File Helpers (loc/*.txt history files)
# ============================================================

def read_loc(path):
    """
    Read loc/*.txt file into structured dict.
    Returns: {meta: {file, version, saves, updated, ref_versions}, history: [...], archive: [...]}
    """
    content = read_file(path)
    if not content:
        return {'meta': {}, 'history': [], 'archive': []}

    data = {'meta': {}, 'history': [], 'archive': []}

    # Parse meta block
    raw_meta = parse_dwml_meta(content)
    data['meta'] = {
        'file': raw_meta.get('file', ''),
        'version': raw_meta.get('version', 'av1r1'),
        'saves': int(raw_meta.get('saves', 0)) if raw_meta.get('saves') else 0,
        'updated': raw_meta.get('updated', '')
    }

    # Parse ref_versions if present (list format)
    if 'ref_versions' in raw_meta:
        ref_versions = {}
        rv = raw_meta['ref_versions']
        if isinstance(rv, list):
            for pair in rv:
                if '=' in pair:
                    ref, ver = pair.split('=', 1)
                    ref_versions[ref.strip()] = ver.strip()
        elif isinstance(rv, str) and '=' in rv:
            for pair in rv.split(','):
                if '=' in pair:
                    ref, ver = pair.split('=', 1)
                    ref_versions[ref.strip()] = ver.strip()
        data['meta']['ref_versions'] = ref_versions

    # Parse archive refs if present (list format)
    if 'archive' in raw_meta:
        arch = raw_meta['archive']
        if isinstance(arch, list):
            data['archive'] = arch
        else:
            data['archive'] = [a.strip() for a in arch.split(',') if a.strip()]

    # Parse history block
    data['history'] = parse_dwml_history(content)

    return data


def write_loc(path, data):
    """
    Write loc/*.txt file from structured dict.
    Expects: {meta: {...}, history: [...], archive: [...]}
    """
    meta = data.get('meta', {})
    history = data.get('history', [])
    archive = data.get('archive', [])

    # Build meta dict for output
    out_meta = {
        'file': meta.get('file', ''),
        'version': meta.get('version', 'av1r1'),
        'saves': str(meta.get('saves', 0)),
        'updated': meta.get('updated', '')
    }

    # Add ref_versions if present
    if 'ref_versions' in meta and meta['ref_versions']:
        pairs = [f'{k}={v}' for k, v in meta['ref_versions'].items()]
        out_meta['ref_versions'] = pairs  # Store as list

    # Add archive refs if present
    if archive:
        out_meta['archive'] = archive  # Store as list

    # Build content
    parts = [format_dwml_meta(out_meta)]
    if history:
        parts.append(format_dwml_history(history))

    write_file(path, '\n\n'.join(parts) + '\n')


def loc_add_history(data, action, changes=None, extra=None):
    """
    Add a history entry to loc data dict.
    action: string like "2026-01-15T10:00:00Z save:1" or "2026-01-15T10:00:00Z bumped av1r2"
    changes: list of {type: 'add'|'rem', line: '...'}
    extra: dict of extra fields to include in action string
    """
    entry = {'action': action, 'changes': changes or []}
    data['history'].append(entry)
    return data


# ============================================================
# Index File Helpers (index.txt)
# ============================================================

def read_index():
    """Read index.txt and return list of tracked files"""
    dw_path = get_dw_path()
    index_path = dw_path / 'index.txt'
    content = read_file(index_path)
    if not content:
        return []

    # Parse meta which contains tracked files
    meta = parse_dwml_meta(content)
    tracked = []

    # Format: tracked as list of file=version pairs
    if 'tracked' in meta:
        tr = meta['tracked']
        if isinstance(tr, list):
            for pair in tr:
                if '=' in pair:
                    file_path, version = pair.split('=', 1)
                    tracked.append({'file': file_path.strip(), 'version': version.strip()})
        elif isinstance(tr, str):
            for pair in tr.split(','):
                if '=' in pair:
                    file_path, version = pair.split('=', 1)
                    tracked.append({'file': file_path.strip(), 'version': version.strip()})

    return tracked


def write_index(tracked):
    """Write index.txt from list of tracked files"""
    dw_path = get_dw_path()
    index_path = dw_path / 'index.txt'

    # Format: tracked as list of file=version pairs
    pairs = [f'{t["file"]}={t["version"]}' for t in tracked]
    meta = {'tracked': pairs}  # Store as list

    write_file(index_path, format_dwml_meta(meta) + '\n')


# ============================================================
# Session Log Helpers (glb/*.txt)
# ============================================================

def read_session_log(path):
    """Read session log file (glb/dw-current.txt or similar)"""
    content = read_file(path)
    if not content:
        return {'meta': {}, 'events': []}

    meta = parse_dwml_meta(content)

    # Parse events from history block
    events = []
    history = parse_dwml_history(content)
    for entry in history:
        # Action format: "2026-01-15T10:00:00Z saved ./file.txt"
        events.append({'action': entry['action']})

    return {
        'meta': {
            'started': meta.get('started', ''),
            'pid': int(meta.get('pid', 0)) if meta.get('pid') else None,
            'stopped': meta.get('stopped', '')
        },
        'events': events
    }


def write_session_log(path, data):
    """Write session log file"""
    meta = data.get('meta', {})
    events = data.get('events', [])

    out_meta = {}
    if meta.get('started'):
        out_meta['started'] = meta['started']
    if meta.get('pid'):
        out_meta['pid'] = str(meta['pid'])
    if meta.get('stopped'):
        out_meta['stopped'] = meta['stopped']

    # Convert events to history format
    history = [{'action': e.get('action', ''), 'changes': []} for e in events]

    parts = [format_dwml_meta(out_meta)]
    if history:
        parts.append(format_dwml_history(history))

    write_file(path, '\n\n'.join(parts) + '\n')


# ============================================================
# Registry Helpers (dw-registry.txt)
# ============================================================

def read_registry(path):
    """Read global watcher registry"""
    content = read_file(path)
    if not content:
        return []

    meta = parse_dwml_meta(content)
    watchers = []

    # Format: watchers as list of path|pid|started entries
    if 'watchers' in meta:
        wl = meta['watchers']
        if isinstance(wl, list):
            for entry in wl:
                parts = entry.split('|')
                if len(parts) >= 3:
                    watchers.append({
                        'path': parts[0],
                        'pid': int(parts[1]) if parts[1].isdigit() else 0,
                        'started': parts[2]
                    })

    return watchers


def write_registry(path, watchers):
    """Write global watcher registry"""
    # Format: watchers as list of path|pid|started entries
    entries = [f'{w["path"]}|{w["pid"]}|{w["started"]}' for w in watchers]
    meta = {'watchers': entries}  # Store as list

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    write_file(path, format_dwml_meta(meta) + '\n')


# ============================================================
# Basic File Functions
# ============================================================

def get_timestamp():
    """Return current timestamp in ISO format with Z suffix"""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def get_timestamp_compact():
    """Return compact timestamp for filenames (YYYYMMDD-HHMMSS)"""
    return datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')


def get_txt_files(folder=None):
    """List all .txt files in folder (default: current directory)"""
    folder = Path(folder) if folder else Path.cwd()
    return [f for f in folder.glob("*.txt") if f.is_file()]


def read_file(path):
    """Read text file, return content"""
    path = Path(path)
    if not path.exists():
        return ""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write_file(path, content):
    """Write content to text file"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def file_exists(path):
    """Check if file exists"""
    return Path(path).exists()


def ensure_folders():
    """Ensure all .dw/ subfolders exist"""
    dw = get_dw_path()
    for folder in ['glb', 'snp', 'loc', 'cmp', 'acv']:
        (dw / folder).mkdir(parents=True, exist_ok=True)


def get_relative_path(path):
    """Convert absolute path to ./relative format"""
    path = Path(path)
    try:
        rel = path.relative_to(Path.cwd())
        return f"./{rel}"
    except ValueError:
        return str(path)


def get_filename(path):
    """Get filename without path"""
    return Path(path).name


def get_stem(path):
    """Get filename without extension"""
    return Path(path).stem
