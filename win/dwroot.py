"""
DocWire Root - Global launcher script (Windows)
Located at C:\\Users\\{user}\\bin\\docwire\\

Handles:
  dw setup        - Copy template/ to current folder as .dw/
  dw setup remove - Delete .dw/ folder
  dw update       - Update .dw/cor/ scripts
  dw all list     - List all registered projects
  dw all update   - Update all projects
  dw all watch    - List all running watchers
  dw all stop     - Stop all watchers
  dw <command>    - Run local .dw/cli.py
"""

import sys
import os
import shutil
import subprocess
from pathlib import Path


def get_repo_path():
    """Get docwire install path (where this script lives)"""
    return Path(__file__).parent.resolve()


def parse_dwml_registry(content):
    """Parse DWML format registry file to extract watchers list"""
    import re
    watchers = []

    # Match =x= watchers;|entry1|entry2|...|; =z=
    match = re.search(r'=x=\s*watchers;([^=]*?);\s*=z=', content)
    if match:
        raw = match.group(1).strip()
        # Split by | but first/last are empty due to format |val1|val2|...|
        parts = [p for p in raw.split('|') if p]
        # Each watcher is 3 consecutive parts: path, pid, started
        i = 0
        while i + 2 < len(parts):
            watchers.append({
                'path': parts[i],
                'pid': parts[i + 1],
                'started': parts[i + 2]
            })
            i += 3

    return watchers


def format_dwml_registry(watchers):
    """Format watchers list back to DWML format"""
    if not watchers:
        return ''
    entries = '|'.join([f'{w["path"]}|{w["pid"]}|{w["started"]}' for w in watchers])
    return f'=d=meta=w=\n=x= watchers;|{entries}|; =z=\n=q=meta=e=\n'


def get_projects_path():
    """Get path to projects registry"""
    return get_repo_path() / 'dw-projects.txt'


def read_projects():
    """Read projects registry, return list of paths"""
    projects_path = get_projects_path()
    if not projects_path.exists():
        return []

    projects = []
    for line in projects_path.read_text().strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            projects.append(line)
    return projects


def write_projects(projects):
    """Write projects registry"""
    projects_path = get_projects_path()
    content = '\n'.join(projects) + '\n' if projects else ''
    projects_path.write_text(content)


def register_project(path):
    """Add project to registry"""
    projects = read_projects()
    path_str = str(Path(path).resolve())
    if path_str not in projects:
        projects.append(path_str)
        write_projects(projects)


def unregister_project(path):
    """Remove project from registry"""
    projects = read_projects()
    path_str = str(Path(path).resolve())
    if path_str in projects:
        projects.remove(path_str)
        write_projects(projects)


def cmd_setup():
    """Copy template/ to current folder as .dw/ or update existing"""
    dw_path = Path.cwd() / '.dw'
    repo_path = get_repo_path()
    template_path = repo_path / 'template'

    if not template_path.exists():
        print(f"Error: Template not found at {template_path}")
        return

    if dw_path.exists():
        # Update existing - just refresh cor/ scripts
        print("Updating .dw/cor/ scripts...")
        cor_src = template_path / 'cor'
        cor_dest = dw_path / 'cor'

        if cor_dest.exists():
            shutil.rmtree(cor_dest)
        shutil.copytree(cor_src, cor_dest)

        # Also update config.txt if missing
        config_src = template_path / 'config.txt'
        config_dest = dw_path / 'config.txt'
        if not config_dest.exists() and config_src.exists():
            shutil.copy(config_src, config_dest)

        register_project(Path.cwd())
        print("Update complete!")
        return

    # Fresh setup
    shutil.copytree(template_path, dw_path)

    # Create data folders
    for folder in ['glb', 'snp', 'loc', 'cmp', 'acv']:
        (dw_path / folder).mkdir(exist_ok=True)

    # Reset index.txt
    index_path = dw_path / 'index.txt'
    index_path.write_text("")

    # Register project
    register_project(Path.cwd())

    print("Setup complete!")
    print("Run 'dw init' to start tracking .txt files")


def cmd_setup_remove():
    """Delete .dw/ folder after confirmation"""
    dw_path = Path.cwd() / '.dw'

    if not dw_path.exists():
        print("No .dw/ folder found.")
        return

    print("\nThis will delete .dw/ folder and all history.")
    confirm = input("Are you sure? [y/N]: ").strip().lower()

    if confirm == 'y':
        try:
            shutil.rmtree(dw_path, ignore_errors=True)
            # Double check if still exists (Windows/OneDrive lock)
            if dw_path.exists():
                print("Could not fully remove .dw/ folder")
                print("Try closing any apps using those files, or delete manually")
            else:
                unregister_project(Path.cwd())
                print("Removed .dw/ folder")
        except Exception as e:
            print(f"Error: {e}")
            print("Try deleting .dw/ folder manually")
    else:
        print("Cancelled")


def cmd_update():
    """Update .dw/cor/ scripts in current folder"""
    dw_path = Path.cwd() / '.dw'

    if not dw_path.exists():
        print("No .dw/ folder. Run 'dw setup' first.")
        return

    repo_path = get_repo_path()
    template_path = repo_path / 'template'

    if not template_path.exists():
        print(f"Error: Template not found at {template_path}")
        return

    # Update cor/ scripts
    cor_src = template_path / 'cor'
    cor_dest = dw_path / 'cor'

    if cor_dest.exists():
        shutil.rmtree(cor_dest)
    shutil.copytree(cor_src, cor_dest)

    # Register if not already
    register_project(Path.cwd())

    print("Updated .dw/cor/ scripts")


def cmd_all_list():
    """List all registered projects"""
    projects = read_projects()

    if not projects:
        print("No projects registered.")
        print("Run 'dw setup' in a folder to register it.")
        return

    print(f"Registered projects ({len(projects)}):\n")
    for i, path in enumerate(projects, 1):
        exists = Path(path).exists()
        dw_exists = (Path(path) / '.dw').exists()
        status = "OK" if dw_exists else ("no .dw/" if exists else "missing")
        print(f"  [{i}] {path} ({status})")


def cmd_all_update():
    """Update all registered projects"""
    projects = read_projects()

    if not projects:
        print("No projects registered.")
        return

    repo_path = get_repo_path()
    template_path = repo_path / 'template'
    cor_src = template_path / 'cor'

    if not cor_src.exists():
        print(f"Error: Template not found at {template_path}")
        return

    updated = 0
    skipped = 0

    for path in projects:
        dw_path = Path(path) / '.dw'
        cor_dest = dw_path / 'cor'

        if not dw_path.exists():
            print(f"  [SKIP] {path} (no .dw/)")
            skipped += 1
            continue

        if cor_dest.exists():
            shutil.rmtree(cor_dest)
        shutil.copytree(cor_src, cor_dest)
        print(f"  [OK] {path}")
        updated += 1

    print(f"\nUpdated {updated} project(s), skipped {skipped}")


def cmd_all_watch(bg_scan=False):
    """List all running watchers"""
    if bg_scan:
        # Scan for python processes that might be watchers
        print("Scanning background python processes...\n")
        try:
            result = subprocess.run(
                ['powershell', '-Command',
                 'Get-CimInstance Win32_Process | Where-Object {$_.Name -like "*python*"} | Select-Object ProcessId, CommandLine | Format-List'],
                capture_output=True, text=True
            )
            output = result.stdout.strip()
            if not output:
                print("No python processes found.")
                return

            # Parse output and filter for watcher-related
            found = []
            current = {}
            for line in output.split('\n'):
                line = line.strip()
                if line.startswith('ProcessId'):
                    current['pid'] = line.split(':', 1)[1].strip()
                elif line.startswith('CommandLine'):
                    current['cmd'] = line.split(':', 1)[1].strip() if ':' in line else ''
                    if current.get('cmd'):
                        cmd_lower = current['cmd'].lower()
                        if 'watch' in cmd_lower or 'docwire' in cmd_lower or '.dw' in cmd_lower:
                            found.append(current.copy())
                    current = {}

            if found:
                print("Possible watcher processes (may include false positives):\n")
                for p in found:
                    print(f"  PID {p['pid']}: {p['cmd']}")
            else:
                print("No python processes matching 'watch', 'docwire', or '.dw' found.")
        except Exception as e:
            print(f"Error scanning processes: {e}")
        return

    # Read watcher registry
    registry_path = get_repo_path() / 'dw-registry.txt'

    if not registry_path.exists():
        print("No watchers running.")
        return

    content = registry_path.read_text().strip()
    if not content:
        print("No watchers running.")
        return

    # Parse DWML registry format
    watchers = parse_dwml_registry(content)

    if not watchers:
        print("No watchers running.")
        return

    # Check which are still running (Windows uses tasklist)
    active = []
    for w in watchers:
        pid = w['pid']
        try:
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}'],
                capture_output=True, text=True
            )
            if pid in result.stdout:
                active.append(w)
        except Exception:
            pass

    if not active:
        print("No watchers running.")
        return

    print(f"Running watchers ({len(active)}):\n")
    for i, w in enumerate(active, 1):
        print(f"  [{i}] PID {w['pid']} - {w['path']}")
        if w['started']:
            print(f"      Started: {w['started']}")


def cmd_all_stop():
    """Stop watchers with interactive choice"""
    registry_path = get_repo_path() / 'dw-registry.txt'

    if not registry_path.exists():
        print("No watchers running.")
        return

    content = registry_path.read_text().strip()
    if not content:
        print("No watchers running.")
        return

    # Parse DWML registry
    watchers = parse_dwml_registry(content)

    # Filter active watchers (Windows: use tasklist)
    active = []
    for w in watchers:
        try:
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {w["pid"]}', '/NH'],
                capture_output=True, text=True
            )
            if w['pid'] in result.stdout:
                active.append(w)
        except Exception:
            pass

    if not active:
        print("No watchers running.")
        registry_path.write_text('')
        return

    # Show list
    print("\nRunning DocWire watchers:\n")
    print("  [0] Stop ALL")
    for i, w in enumerate(active, 1):
        path = w['path']
        pid = w['pid']
        # Shorten path for display
        short_path = path
        if len(path) > 50:
            short_path = '...' + path[-47:]
        print(f"  [{i}] {short_path}  (PID: {pid})")

    print()
    try:
        choice = input(f"Stop which? [0-{len(active)}]: ").strip()
    except EOFError:
        print("No input, cancelled.")
        return

    try:
        choice = int(choice)
        stopped = 0

        if choice == 0:
            # Stop all
            for w in active:
                try:
                    subprocess.run(['taskkill', '/PID', w['pid'], '/F'], capture_output=True)
                    print(f"  Stopped: {Path(w['path']).name} (PID: {w['pid']})")
                    stopped += 1
                except Exception:
                    pass
            registry_path.write_text('')
            print(f"\nStopped {stopped} watcher(s)")

        elif 1 <= choice <= len(active):
            w = active[choice - 1]
            try:
                subprocess.run(['taskkill', '/PID', w['pid'], '/F'], capture_output=True)
                print(f"Stopped: {Path(w['path']).name} (PID: {w['pid']})")
                # Update registry - remove this one
                remaining = [x for x in active if x['pid'] != w['pid']]
                registry_path.write_text(format_dwml_registry(remaining))
            except Exception:
                print(f"Could not stop (PID: {w['pid']})")
        else:
            print("Invalid choice")

    except ValueError:
        print("Invalid choice")


def cmd_all_start():
    """Start watchers with interactive choice"""
    projects = read_projects()

    if not projects:
        print("No projects registered.")
        print("Run 'dw setup' in a folder to register it.")
        return

    # Filter to projects that have .dw/ folder
    available = []
    for path in projects:
        dw_path = Path(path) / '.dw'
        if dw_path.exists():
            available.append(path)

    if not available:
        print("No projects with .dw/ folder found.")
        return

    # Check which already have watchers running
    registry_path = get_repo_path() / 'dw-registry.txt'
    running_paths = set()
    if registry_path.exists():
        content = registry_path.read_text().strip()
        if content:
            watchers = parse_dwml_registry(content)
            for w in watchers:
                # Check if PID still alive
                try:
                    result = subprocess.run(
                        ['tasklist', '/FI', f'PID eq {w["pid"]}', '/NH'],
                        capture_output=True, text=True
                    )
                    if w['pid'] in result.stdout:
                        running_paths.add(w['path'])
                except Exception:
                    pass

    # Show list
    print("\nRegistered projects:\n")
    print("  [0] Start ALL (skip already running)")
    for i, path in enumerate(available, 1):
        status = "(running)" if path in running_paths else ""
        short_path = path
        if len(path) > 50:
            short_path = '...' + path[-47:]
        print(f"  [{i}] {short_path} {status}")

    print()
    try:
        choice = input(f"Start which? [0-{len(available)}]: ").strip()
    except EOFError:
        print("No input, cancelled.")
        return

    try:
        choice = int(choice)
        started = 0

        if choice == 0:
            # Start all (skip running)
            for path in available:
                if path in running_paths:
                    print(f"  [SKIP] {Path(path).name} (already running)")
                    continue
                try:
                    os.chdir(path)
                    # Run dw start directly (it spawns background daemon)
                    result = subprocess.run(
                        [sys.executable, str(Path(__file__).resolve()), 'start'],
                        capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        print(f"  [OK] {Path(path).name}")
                        started += 1
                    else:
                        print(f"  [FAIL] {Path(path).name}: {result.stderr or result.stdout}")
                except Exception as e:
                    print(f"  [FAIL] {Path(path).name}: {e}")
            print(f"\nStarted {started} watcher(s)")

        elif 1 <= choice <= len(available):
            path = available[choice - 1]
            if path in running_paths:
                print(f"Already running: {Path(path).name}")
                return
            try:
                os.chdir(path)
                # Run dw start directly (it spawns background daemon)
                result = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), 'start'],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    print(f"Started: {Path(path).name}")
                else:
                    print(f"Could not start: {result.stderr or result.stdout}")
            except Exception as e:
                print(f"Could not start: {e}")
        else:
            print("Invalid choice")

    except ValueError:
        print("Invalid choice")


def run_local_cli(args):
    """Run local .dw/cor/cli.py with given args"""
    dw_path = Path.cwd() / '.dw'
    cor_path = dw_path / 'cor'
    cli_path = cor_path / 'cli.py'

    if not cli_path.exists():
        print("No .dw/ folder. Run 'dw setup' first.")
        return

    # Add .dw/cor/ to path so imports work
    sys.path.insert(0, str(cor_path))

    # Set argv for cli.py
    original_argv = sys.argv
    sys.argv = ['dw'] + args

    try:
        # Execute cli.py
        exec(compile(cli_path.read_text(encoding='utf-8'), cli_path, 'exec'), {
            '__name__': '__main__',
            '__file__': str(cli_path)
        })
    finally:
        sys.argv = original_argv


def main():
    if len(sys.argv) < 2:
        print("DocWire - Git for docs, but automatic")
        print("\nUsage: dw <command>")
        print("\nSetup:")
        print("  setup         Setup .dw/ (or update if exists)")
        print("  setup remove  Delete .dw/ folder")
        print("  update        Update .dw/cor/ scripts")
        print("\nGlobal:")
        print("  all list      List all registered projects")
        print("  all update    Update all projects")
        print("  all start     Start watchers (interactive)")
        print("  all watch     List all running watchers")
        print("  all watch -bg Scan background processes")
        print("  all stop      Stop all watchers")
        print("\nCore:")
        print("  start     Start watcher (init + sync + bump + watch)")
        print("  start -f  Start watcher (foreground)")
        print("  stop      Stop watcher (current folder)")
        print("  bump      Bump revision")
        print("  status    Show status")
        print("  track     Show file history")
        print("  head      Add header to file")
        print("\nFix & Maintain:")
        print("  fix           Scan for issues")
        print("  fix -y        Auto-fix all issues")
        print("  fix -s        Sync + repair (refresh metadata)")
        print("  fix -r        Remove all orphans")
        print("  fix -r -f <file>  Remove specific file")
        print("  archive       Move history to acv/")
        print("  compact       Generate stats summary")
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == 'setup':
        if args and args[0] == 'remove':
            cmd_setup_remove()
        else:
            cmd_setup()
    elif cmd == 'update':
        cmd_update()
    elif cmd == 'all':
        if not args:
            print("Usage: dw all <list|update|watch|start|stop>")
            return
        subcmd = args[0]
        if subcmd == 'list':
            cmd_all_list()
        elif subcmd == 'update':
            cmd_all_update()
        elif subcmd == 'watch':
            bg_scan = '-bg' in args[1:] if len(args) > 1 else False
            cmd_all_watch(bg_scan=bg_scan)
        elif subcmd == 'start':
            cmd_all_start()
        elif subcmd == 'stop':
            cmd_all_stop()
        else:
            print(f"Unknown: dw all {subcmd}")
            print("Usage: dw all <list|update|watch|stop>")
    else:
        run_local_cli([cmd] + args)


if __name__ == '__main__':
    main()
