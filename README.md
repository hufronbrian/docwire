# DocWire

Git for docs, but automatic.

Per-file versioning for plain .txt files. Save = auto-diff, bump = commit. Zero learning curve.

## Why DocWire?

| | Git | DocWire |
|---|---|---|
| Track changes | Manual (git add) | Auto on save |
| Commit | Manual (git commit) | dw bump |
| Message | You write it | Auto-generated diff |
| Scope | Whole repo | Per file |
| Branch | git branch + checkout | Just copy the .txt file |
| Merge | git merge (conflicts) | Paste back, delete copy |
| Learning curve | High | Almost none |

## Install

```bash
git clone https://github.com/hufronbrian/docwire
cd docwire
```

**Windows (PowerShell):**
```powershell
.\install.ps1
# Restart terminal
```

**Linux/Mac/WSL:**
```bash
chmod +x install.sh
./install.sh
# Restart terminal or: source ~/.bashrc
```

## Quick Start

```bash
cd your-docs-folder
dw setup      # Copy .dw/ template
dw start      # Init + sync + bump + start watcher
```

Now edit your .txt files normally. DocWire tracks every save.

```bash
dw bump       # Mark revision boundary (like git commit)
dw status     # Show tracked files
dw stop       # Stop watcher
```

## Commands

### Setup
| Command | Description |
|---------|-------------|
| `dw setup` | Copy .dw/ to current folder |
| `dw setup remove` | Delete .dw/ folder |
| `dw update` | Update .dw/cor/ scripts |

### Global
| Command | Description |
|---------|-------------|
| `dw all list` | List all registered projects |
| `dw all watch` | List all running watchers |
| `dw all stop` | Stop watchers (interactive) |

### Core
| Command | Description |
|---------|-------------|
| `dw start` | Init + sync + bump + start watcher |
| `dw start -f` | Start watcher (foreground) |
| `dw stop` | Stop watcher (current folder) |
| `dw bump` | Bump revision |
| `dw status` | Show status |
| `dw track <file>` | Show file history |
| `dw head -f <file>` | Add header to file |

### Fix & Maintain
| Command | Description |
|---------|-------------|
| `dw fix` | Scan for issues |
| `dw fix -y` | Auto-fix all issues |
| `dw fix -s` | Sync + repair (refresh metadata) |
| `dw fix -r` | Remove all orphans |
| `dw fix -r -f <file>` | Remove specific file |
| `dw archive` | Move history to acv/ |
| `dw compact` | Generate stats summary |

## Header Format (DWML v1.0)

DocWire tracks files with a DWML header block:

```
=d=meta=w=
=dw=
=#= docwire tracked file =o=
=x= file;|./myfile.txt|; =z=
=x= version;|av1r1|; =z=
=x= log;|./.dw/loc/myfile.txt|; =z=
=x= update;|2026-01-15T12:00:00Z|; =z=
=x= refs;||; =z=
=wd=
=q=meta=e=

Your document content here...
```

Files without the header are not tracked.

## DWML (DontWorry Markup Language) v1.0

DocWire uses DWML for all internal data files. DWML is safe, requires no escaping, and is LLM-friendly.

"DontWorry" - you don't have to worry about special characters breaking your data.

### Block Tags

Open: `=d=name=w=`
Close: `=q=name=e=`

| Block | Purpose |
|-------|---------|
| `=d=meta=w= ... =q=meta=e=` | Metadata block |
| `=d=history=w= ... =q=history=e=` | History block |
| `=d=config=w= ... =q=config=e=` | Config block |

### Inline Tags

| Tag | Purpose |
|-----|---------|
| `=dw=...=wd=` | Container/grouping |
| `=x=...=z=` | Key-value content |
| `=+=...=o=` | Added line (diff) |
| `=-=...=o=` | Removed line (diff) |
| `=#=...=o=` | Comment |

### Value Syntax

```
=x= key;|value|; =z=
=x= tags;|red|;,;|green|;,;|blue|; =z=
```

- `;|` opens value
- `|;` closes value
- `,` separates multiple values

### Example loc/*.txt

```
=d=meta=w=
=x= file;|./myfile.txt|; =z=
=x= version;|av1r2|; =z=
=x= saves;|3|; =z=
=x= updated;|2026-01-15T14:30:00Z|; =z=
=q=meta=e=

=d=history=w=
=dw=
=x= 2026-01-15T14:00:00Z;|initialized|; =z=
=wd=
=dw=
=x= 2026-01-15T14:10:00Z;|save:1|; =z=
=+= added this line =o=
=-= removed this line =o=
=wd=
=dw=
=x= 2026-01-15T14:30:00Z;|bumped av1r2|; =z=
=wd=
=q=history=e=
```

## Version Format

`avNrN` = base + major + revision

- `av1r1` - original, first revision
- `av1r5` - original, 5th revision (5 bumps)
- `av2r1` - merged from branch
- `bv1r1` - rebased (new direction)

## Uninstall

**Windows:**
```powershell
.\uninstall.ps1
```

**Linux/Mac/WSL:**
```bash
./uninstall.sh
```

## Requirements

- Python 3.10+
- watchdog (`pip install watchdog`)

## Related

- [DWML](https://github.com/hufronbrian/dwml) - DontWorry Markup Language spec and parser

## Fork This

This project may not be actively maintained. That's okay.

DocWire is a tool, not a service. If it solves your problem:
- Use it
- Fork it
- Improve it
- Make it your own

The code is yours to build on.

## License

[GPLX-XBasic](https://github.com/hufronbrian/gplx) - See LICENSE for details. 
