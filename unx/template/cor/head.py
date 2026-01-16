"""
DocWire Head - Header management using DWML format
"""

from pathlib import Path
from utils import get_dw_path, get_timestamp, get_relative_path, read_file, write_file
import dwml


BLOCK_NAME = "meta"


def has_header(content):
    """Check if content has =d=meta=w=...=q=meta=e= header block"""
    return dwml.has_block(content, BLOCK_NAME)


def parse_header(content):
    """
    Extract header fields from =d=meta=w=...=q=meta=e= block
    Returns dict of field:value pairs
    """
    if not has_header(content):
        return {}

    doc = dwml.parse(content)
    block = doc.block(BLOCK_NAME)

    if not block:
        return {}

    return dict(block.fields)


def get_field(content, field):
    """Get single field value from header"""
    return dwml.get_field(content, BLOCK_NAME, field)


def create_header(filepath):
    """
    Generate new =d=meta=w=...=q=meta=e= header block for a file
    Returns header string in DWML format
    """
    filepath = Path(filepath)
    filename = filepath.name
    stem = filepath.stem

    rel_path = get_relative_path(filepath)
    loc_path = f"./.dw/loc/{stem}.txt"
    timestamp = get_timestamp()

    fields = {
        "file": rel_path,
        "version": "av1r1",
        "log": loc_path,
        "update": timestamp,
        "refs": ""
    }

    lines = [
        f'=d={BLOCK_NAME}=w=',
        '=dw=',
        '=#= docwire tracked file | edit content below =o=',
        f'=x= file;|{rel_path}|; =z=',
        f'=x= version;|av1r1|; =z=',
        f'=x= log;|{loc_path}|; =z=',
        f'=x= update;|{timestamp}|; =z=',
        '=x= refs;||; =z=',
        '=wd=',
        f'=q={BLOCK_NAME}=e='
    ]

    return '\n'.join(lines)


def add_header(filepath):
    """
    Add =d=meta=w=...=q=meta=e= header to file if not exists
    Returns True if header was added, False if already exists
    """
    filepath = Path(filepath)
    content = read_file(filepath)

    if has_header(content):
        return False

    header = create_header(filepath)
    new_content = header + "\n\n" + content
    write_file(filepath, new_content)
    return True


def update_field(content, field, value):
    """
    Update single field in header, return new content
    If field doesn't exist, adds it before =wd=
    """
    if not has_header(content):
        return content

    # Build new field line
    new_field_line = f'=x= {field};|{value}|; =z='

    # Check if field exists
    import re
    field_pattern = rf'=x=\s*{field};\|[^|]*\|;\s*=z='

    if re.search(field_pattern, content):
        # Update existing field
        new_content = re.sub(field_pattern, new_field_line, content)
    else:
        # Add new field before =wd=
        new_content = content.replace('=wd=', f'{new_field_line}\n=wd=', 1)

    return new_content


def update_file_field(filepath, field, value):
    """Update field in file's header"""
    filepath = Path(filepath)
    content = read_file(filepath)
    new_content = update_field(content, field, value)
    if new_content != content:
        write_file(filepath, new_content)
        return True
    return False


def get_header_block(content):
    """Extract the full header block including delimiters"""
    if not has_header(content):
        return ""

    import re
    pattern = rf'=d={BLOCK_NAME}=w=\s*.*?\s*=q={BLOCK_NAME}=e='
    match = re.search(pattern, content, re.DOTALL)
    return match.group(0) if match else ""


def get_content_without_header(content):
    """Return content without the header block"""
    if not has_header(content):
        return content

    import re
    pattern = rf'=d={BLOCK_NAME}=w=\s*.*?\s*=q={BLOCK_NAME}=e=\n*'
    return re.sub(pattern, '', content, count=1)
