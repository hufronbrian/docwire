"""
DocWire Watch - File watcher daemon using watchdog
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path

# Add script directory to path for imports when run directly
_script_dir = Path(__file__).parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler


def is_wsl():
    """Check if running in WSL"""
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except:
        return False


def needs_polling(path):
    """Check if path needs polling instead of inotify.

    Returns True only for WSL + Windows filesystem paths.
    - Linux native: inotify works fine
    - Mac: FSEvents works fine
    - WSL + Linux path (~/*): inotify works
    - WSL + Windows path (/mnt/*): needs polling
    """
    return is_wsl() and str(path).startswith('/mnt/')


from utils import (
    get_dw_path, get_timestamp, get_timestamp_compact,
    read_file, write_file, read_loc, write_loc,
    read_session_log, write_session_log,
    read_registry, write_registry,
    get_relative_path, get_stem, path_to_storage_name
)
from head import has_header, parse_header, update_file_field, get_field
from diff import calc_diff, has_changes
from bump import check_rebase


# Global registry path (in user home)
def get_registry_path():
    """Get path to global watcher registry"""
    if os.name == 'nt':
        return Path.home() / 'bin' / 'docwire' / 'dw-registry.txt'
    else:
        return Path.home() / '.local' / 'bin' / 'docwire' / 'dw-registry.txt'


class DWEventHandler(FileSystemEventHandler):
    """Handle file system events for .txt files"""

    def __init__(self):
        self.dw_path = get_dw_path()
        super().__init__()

    def _is_tracked_file(self, path):
        """Check if file should be tracked (is .txt and has header)"""
        path = Path(path)

        # Only .txt files
        if path.suffix.lower() != '.txt':
            return False

        # Skip files in .dw/ folder
        if '.dw' in path.parts:
            return False

        # Check for DWML header
        content = read_file(path)
        return has_header(content)

    def _log_event(self, action, file_path, extra=None):
        """Log event to glb/dw-current.txt"""
        log_path = self.dw_path / 'glb' / 'dw-current.txt'
        log_data = read_session_log(log_path)

        ts = get_timestamp()
        event_str = f'{ts} {action} {get_relative_path(file_path)}'
        if extra:
            for k, v in extra.items():
                event_str += f' {k}:{v}'

        log_data['events'].append({'action': event_str})
        write_session_log(log_path, log_data)

    def _process_save(self, file_path):
        """Process file save: calc diff, update loc/*.txt, update snp/"""
        file_path = Path(file_path)
        storage_name = path_to_storage_name(file_path)

        # Read current content
        current_content = read_file(file_path)

        # Check for header
        if not has_header(current_content):
            return

        # Parse header for version
        header_fields = parse_header(current_content)
        header_version = header_fields.get('version', 'av1r1')

        # Read snapshot (use storage name for subfolder support)
        snp_path = self.dw_path / 'snp' / f'{storage_name}.txt'
        snp_content = read_file(snp_path)

        # Check for rebase
        loc_path = self.dw_path / 'loc' / f'{storage_name}.txt'
        loc_data = read_loc(loc_path)
        loc_version = loc_data.get('meta', {}).get('version', 'av1r1')

        ts = get_timestamp()

        if check_rebase(loc_version, header_version):
            # Archive old loc/*.txt
            acv_path = self.dw_path / 'acv' / f'{stem}-{get_timestamp_compact()}.txt'
            write_loc(acv_path, loc_data)

            # Create fresh loc/*.txt
            loc_data = {
                'meta': {
                    'file': get_relative_path(file_path),
                    'version': header_version,
                    'saves': 0,
                    'updated': ts
                },
                'history': [{
                    'action': f'{ts} rebased {loc_version} -> {header_version}',
                    'changes': []
                }],
                'archive': []
            }

        # Calc diff
        if has_changes(snp_content, current_content):
            diff_result = calc_diff(snp_content, current_content)

            # Update saves count
            saves = loc_data.get('meta', {}).get('saves', 0) + 1
            if 'meta' not in loc_data:
                loc_data['meta'] = {}
            loc_data['meta']['saves'] = saves
            loc_data['meta']['updated'] = ts
            loc_data['meta']['file'] = get_relative_path(file_path)
            loc_data['meta']['version'] = header_version

            # Build changes list
            max_line_len = 200
            max_lines = 50
            changes = []
            for line in diff_result['added'][:max_lines]:
                changes.append({'type': 'add', 'line': line[:max_line_len]})
            for line in diff_result['removed'][:max_lines]:
                changes.append({'type': 'rem', 'line': line[:max_line_len]})

            loc_data['history'].append({
                'action': f'{ts} save:{saves}',
                'changes': changes
            })

            write_loc(loc_path, loc_data)

            # Update snapshot
            write_file(snp_path, current_content)

            # Note: we don't update dw:update in .txt header here
            # because it would trigger another file change event (loop)
            # timestamp is tracked in loc/*.txt instead

            # Log event
            self._log_event('saved', file_path)

    def _process_create(self, file_path):
        """Process new file: create snp/, loc/*.txt"""
        file_path = Path(file_path)
        storage_name = path_to_storage_name(file_path)

        # Copy to snapshot (use storage name for subfolder support)
        content = read_file(file_path)
        snp_path = self.dw_path / 'snp' / f'{storage_name}.txt'
        write_file(snp_path, content)

        # Create loc/*.txt
        ts = get_timestamp()
        loc_path = self.dw_path / 'loc' / f'{storage_name}.txt'
        loc_data = {
            'meta': {
                'file': get_relative_path(file_path),
                'version': 'av1r1',
                'saves': 0,
                'updated': ts
            },
            'history': [{
                'action': f'{ts} created',
                'changes': []
            }],
            'archive': []
        }
        write_loc(loc_path, loc_data)

        # Log event
        self._log_event('created', file_path)

    def _process_move(self, src_path, dest_path):
        """Process file move/rename: rename snp/, loc/, log rename"""
        src_path = Path(src_path)
        dest_path = Path(dest_path)
        src_storage = path_to_storage_name(src_path)
        dest_storage = path_to_storage_name(dest_path)

        # Rename snapshot (use storage names for subfolder support)
        snp_src = self.dw_path / 'snp' / f'{src_storage}.txt'
        snp_dest = self.dw_path / 'snp' / f'{dest_storage}.txt'
        if snp_src.exists():
            snp_src.rename(snp_dest)

        # Rename loc/*.txt
        loc_src = self.dw_path / 'loc' / f'{src_storage}.txt'
        loc_dest = self.dw_path / 'loc' / f'{dest_storage}.txt'
        if loc_src.exists():
            loc_src.rename(loc_dest)

            # Add rename entry to history
            loc_data = read_loc(loc_dest)
            ts = get_timestamp()
            loc_data['history'].append({
                'action': f'{ts} renamed {get_relative_path(src_path)} -> {get_relative_path(dest_path)}',
                'changes': []
            })
            loc_data['meta']['file'] = get_relative_path(dest_path)
            write_loc(loc_dest, loc_data)

        # Log event
        self._log_event('renamed', dest_path, {
            'from': get_relative_path(src_path),
            'to': get_relative_path(dest_path)
        })

    def on_modified(self, event):
        """Handle file modification"""
        if event.is_directory:
            return
        path = Path(event.src_path)
        # Quick skip for .dw folder before any file operations
        if '.dw' in path.parts:
            return
        if path.suffix.lower() != '.txt':
            return
        if self._is_tracked_file(event.src_path):
            self._process_save(event.src_path)

    def on_created(self, event):
        """Handle file creation"""
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() == '.txt' and '.dw' not in path.parts:
            if self._is_tracked_file(event.src_path):
                # Run init to ensure loc exists
                from cli import init_file
                init_file(path)
                self._log_event('created', path)

    def on_moved(self, event):
        """Handle file move/rename"""
        if event.is_directory:
            return
        src_path = Path(event.src_path)
        dest_path = Path(event.dest_path)
        if src_path.suffix.lower() == '.txt' and '.dw' not in src_path.parts:
            self._process_move(event.src_path, event.dest_path)


def register_watcher(watch_path, pid):
    """Add watcher to global registry"""
    registry_path = get_registry_path()

    watchers = read_registry(registry_path)
    watchers.append({
        'path': str(watch_path),
        'pid': pid,
        'started': get_timestamp()
    })

    write_registry(registry_path, watchers)


def unregister_watcher(watch_path=None, pid=None):
    """Remove watcher from global registry"""
    registry_path = get_registry_path()
    if not registry_path.exists():
        return

    watchers = read_registry(registry_path)

    # Filter out the watcher
    watchers = [
        w for w in watchers
        if not (
            (watch_path and w.get('path') == str(watch_path)) or
            (pid and w.get('pid') == pid)
        )
    ]

    write_registry(registry_path, watchers)


def is_process_alive(pid):
    """Check if a process is running"""
    if pid is None:
        return False
    try:
        if os.name == 'nt':
            # Windows: use tasklist
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}', '/NH'],
                capture_output=True, text=True
            )
            return str(pid) in result.stdout
        else:
            # Unix: use kill -0
            os.kill(pid, 0)
            return True
    except (ProcessLookupError, OSError, TypeError):
        return False


def get_all_watchers():
    """Get list of all registered watchers with status"""
    registry_path = get_registry_path()
    if not registry_path.exists():
        return []

    watchers = read_registry(registry_path)

    # Check which are still alive
    alive_watchers = []
    for w in watchers:
        pid = w.get('pid')
        if is_process_alive(pid):
            alive_watchers.append(w)

    # Update registry with only alive watchers
    if len(alive_watchers) != len(watchers):
        write_registry(registry_path, alive_watchers)

    return alive_watchers


def start_watcher_foreground():
    """Start the file watcher in foreground (blocking)"""
    dw_path = get_dw_path()
    watch_path = Path.cwd()

    # Create dw-current.txt
    log_path = dw_path / 'glb' / 'dw-current.txt'
    log_data = {
        'meta': {
            'started': get_timestamp(),
            'pid': os.getpid()
        },
        'events': []
    }
    write_session_log(log_path, log_data)

    # Write PID file
    pid_path = dw_path / 'glb' / 'dw.pid'
    write_file(pid_path, str(os.getpid()))

    # Note: registry is handled by parent process in background mode
    # Only register here if running directly in foreground (not as daemon)
    if '--daemon' not in sys.argv:
        register_watcher(watch_path, os.getpid())

    # Setup signal handler for graceful shutdown
    def signal_handler(signum, frame):
        print("\nStopping watcher...")
        observer.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start observer
    # Use PollingObserver for WSL + Windows filesystem since inotify doesn't work there
    event_handler = DWEventHandler()
    if needs_polling(watch_path):
        observer = PollingObserver(timeout=1)
        print("Using polling mode (WSL + Windows filesystem)")
    else:
        observer = Observer()
    observer.schedule(event_handler, str(watch_path), recursive=True)
    observer.start()

    # Start atomic poll for missed changes
    from atomic import start_poll
    start_poll()

    print(f"Watcher started (PID: {os.getpid()})")
    print(f"Watching: {watch_path}")
    print("Press Ctrl+C to stop")

    try:
        while observer.is_alive():
            observer.join(1)
    finally:
        # Stop atomic poll
        from atomic import stop_poll
        stop_poll()

        observer.stop()
        observer.join()

        # Rename dw-current.txt to timestamped
        ts = get_timestamp_compact()
        new_log_path = dw_path / 'glb' / f'dw-{ts}.txt'
        if log_path.exists():
            log_data = read_session_log(log_path)
            log_data['meta']['stopped'] = get_timestamp()
            write_session_log(log_path, log_data)
            log_path.rename(new_log_path)

        # Remove PID file
        if pid_path.exists():
            pid_path.unlink()

        # Unregister from global registry
        unregister_watcher(watch_path=watch_path)

        print("Watcher stopped")


def start_watcher_background():
    """Start the file watcher in background (daemon)"""
    dw_path = get_dw_path()
    watch_path = Path.cwd()

    # Get path to this script
    watch_script = dw_path / 'cor' / 'watch.py'

    # Start as background process
    if os.name == 'nt':
        # Windows: use pythonw or start /b
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        process = subprocess.Popen(
            [sys.executable, str(watch_script), '--daemon'],
            cwd=str(watch_path),
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        )
    else:
        # Unix: use nohup-like approach
        process = subprocess.Popen(
            [sys.executable, str(watch_script), '--daemon'],
            cwd=str(watch_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

    # Wait a moment for process to start
    time.sleep(0.5)

    # Check if it started successfully
    if process.poll() is None:
        # Register from parent process (child also registers, but this ensures it's there)
        register_watcher(watch_path, process.pid)

        print(f"Watcher started in background (PID: {process.pid})")
        print(f"Watching: {watch_path}")
        print("Use 'dw all watch' to see status, 'dw stop' to stop")
        return True
    else:
        print("Failed to start watcher")
        return False


def start_watcher(foreground=False):
    """Start the file watcher"""
    if foreground:
        start_watcher_foreground()
    else:
        start_watcher_background()


def stop_watcher():
    """Stop the running watcher daemon in current folder"""
    dw_path = get_dw_path()
    pid_path = dw_path / 'glb' / 'dw.pid'

    if not pid_path.exists():
        print("No watcher running in this folder")
        return False

    pid = int(read_file(pid_path).strip())

    try:
        if os.name == 'nt':
            # Windows: use taskkill
            subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                         capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)

        print(f"Stopped watcher (PID: {pid})")

        # Clean up
        if pid_path.exists():
            pid_path.unlink()
        unregister_watcher(pid=pid)

        return True
    except (ProcessLookupError, OSError):
        # Process already dead, clean up
        if pid_path.exists():
            pid_path.unlink()
        unregister_watcher(pid=pid)
        print("Watcher was not running (stale PID removed)")
        return False


def stop_watcher_by_pid(pid):
    """Stop a specific watcher by PID"""
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                         capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)

        unregister_watcher(pid=pid)
        return True
    except (ProcessLookupError, OSError):
        unregister_watcher(pid=pid)
        return False


def is_watcher_running():
    """Check if watcher is currently running in current folder"""
    dw_path = get_dw_path()
    pid_path = dw_path / 'glb' / 'dw.pid'

    if not pid_path.exists():
        return False, None

    pid = int(read_file(pid_path).strip())

    try:
        os.kill(pid, 0)  # Check if process exists
        return True, pid
    except (ProcessLookupError, OSError):
        # Stale PID file
        pid_path.unlink()
        return False, None


def cmd_watch(args):
    """Handle dw watch command"""
    if args and args[0] == 'stop':
        # Show list and choose which to stop
        watchers = get_all_watchers()

        if not watchers:
            print("No watchers running")
            return

        print("\nRunning DocWire watchers:\n")
        print("  [0] Stop ALL")
        for i, w in enumerate(watchers, 1):
            path = w.get('path', 'unknown')
            pid = w.get('pid', '?')
            # Shorten path for display
            short_path = path
            if len(path) > 50:
                short_path = '...' + path[-47:]
            print(f"  [{i}] {short_path}  (PID: {pid})")

        print()
        choice = input(f"Stop which? [0-{len(watchers)}]: ").strip()

        try:
            choice = int(choice)
            if choice == 0:
                # Stop all
                for w in watchers:
                    pid = w.get('pid')
                    path = w.get('path', 'unknown')
                    if stop_watcher_by_pid(pid):
                        print(f"Stopped: {Path(path).name} (PID: {pid})")
                print(f"\nStopped all {len(watchers)} watchers")
            elif 1 <= choice <= len(watchers):
                w = watchers[choice - 1]
                pid = w.get('pid')
                path = w.get('path', 'unknown')
                if stop_watcher_by_pid(pid):
                    print(f"Stopped: {Path(path).name} (PID: {pid})")
                else:
                    print(f"Could not stop (PID: {pid})")
            else:
                print("Invalid choice")
        except ValueError:
            print("Invalid choice")
    else:
        # List all watchers
        watchers = get_all_watchers()

        if not watchers:
            print("No watchers running")
            return

        print("\nRunning DocWire watchers:\n")
        for i, w in enumerate(watchers, 1):
            path = w.get('path', 'unknown')
            pid = w.get('pid', '?')
            started = w.get('started', '?')[:19]
            print(f"  [{i}] {path}")
            print(f"      PID: {pid}, Started: {started}")
            print()

        print(f"Total: {len(watchers)} watcher(s)")
        print("\nUse 'dw watch stop' to stop watchers")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--daemon':
        # Running as daemon, start foreground (this is the background process)
        start_watcher_foreground()
    else:
        start_watcher_foreground()
