"""
DocWire Poke - Touch file to trigger watchdog
Reads file content, writes it back unchanged
This triggers on_modified event in watchdog
"""

from pathlib import Path
from utils import read_file, write_file


def trigger_save(file_path):
    """
    Touch a file to trigger watchdog on_modified.
    Reads and rewrites the same content.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        return False

    # Read current content
    content = read_file(file_path)
    if content is None:
        return False

    # Write same content back (triggers on_modified)
    write_file(file_path, content)

    return True
