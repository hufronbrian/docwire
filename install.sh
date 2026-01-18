#!/bin/bash
# DocWire Installer for Linux/Mac/WSL
# Run: ./install.sh
# Run: ./install.sh -y  (skip prompts, auto-install deps)

set -e

# Parse flags
AUTO_YES=0
if [ "$1" = "-y" ] || [ "$1" = "--yes" ]; then
    AUTO_YES=1
fi

echo "DocWire Installer (Linux/Mac/WSL)"
echo "========================================"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo ""
    echo "ERROR: Python3 not found"
    echo ""
    if [ "$AUTO_YES" -eq 1 ]; then
        choice="y"
    else
        read -p "Install python3 now? [y/N]: " choice
    fi
    if [ "$choice" = "y" ] || [ "$choice" = "Y" ]; then
        sudo apt install -y python3
    else
        echo ""
        echo "Install Python 3.10+ first:"
        echo "  Ubuntu/Debian: sudo apt install python3"
        echo "  Mac: brew install python3"
        echo ""
        exit 1
    fi
fi

PYTHON_VERSION=$(python3 --version)
echo "Python: $PYTHON_VERSION"

# Check pip
HAS_PIP=0
if command -v pip3 &> /dev/null; then
    HAS_PIP=1
elif command -v pip &> /dev/null; then
    HAS_PIP=1
elif python3 -m pip --version &> /dev/null; then
    HAS_PIP=1
fi

if [ "$HAS_PIP" -eq 0 ]; then
    echo ""
    echo "pip not found"
    echo ""
    if [ "$AUTO_YES" -eq 1 ]; then
        choice="y"
    else
        read -p "Install python3-pip now? [y/N]: " choice
    fi
    if [ "$choice" = "y" ] || [ "$choice" = "Y" ]; then
        sudo apt install -y python3-pip
    else
        echo ""
        echo "Install pip first:"
        echo "  Ubuntu/Debian: sudo apt install python3-pip"
        echo "  Mac: python3 -m ensurepip"
        echo ""
        exit 1
    fi
fi

echo "pip: OK"

# Check watchdog
echo "Checking dependencies..."
if ! python3 -c "import watchdog" &> /dev/null; then
    echo ""
    echo "watchdog module not found"
    echo ""
    if [ "$AUTO_YES" -eq 1 ]; then
        choice="y"
    else
        read -p "Install python3-watchdog now? [y/N]: " choice
    fi
    if [ "$choice" = "y" ] || [ "$choice" = "Y" ]; then
        sudo apt install -y python3-watchdog
    else
        echo ""
        echo "Install watchdog first:"
        echo "  pip3 install watchdog"
        echo "  or: sudo apt install python3-watchdog"
        echo ""
        exit 1
    fi
fi

echo "watchdog: OK"

# Set paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/unx"
INSTALL_DIR="$HOME/.local/bin/docwire"

# Check source exists
if [ ! -f "$SOURCE_DIR/dw" ]; then
    echo "Error: unx/dw not found"
    exit 1
fi

# Create install directory
mkdir -p "$INSTALL_DIR"
echo "Install directory: $INSTALL_DIR"

# Stop running watchers before update
WATCHER_PATHS=""
STOPPED_COUNT=0
if [ -x "$INSTALL_DIR/dw" ]; then
    echo "Checking for running watchers..."
    REGISTRY_FILE="$INSTALL_DIR/dw-registry.txt"
    if [ -f "$REGISTRY_FILE" ]; then
        # Parse DWML format and kill watchers
        CONTENT=$(cat "$REGISTRY_FILE")
        if echo "$CONTENT" | grep -q "=x= watchers;"; then
            # Extract PIDs and paths
            RAW=$(echo "$CONTENT" | grep -o '=x= watchers;[^;]*;' | sed 's/=x= watchers;//' | sed 's/;//')
            IFS='|' read -ra PARTS <<< "$RAW"
            i=0
            while [ $i -lt ${#PARTS[@]} ]; do
                if [ -n "${PARTS[$i]}" ] && [ -n "${PARTS[$((i+1))]}" ]; then
                    PATH_VAL="${PARTS[$i]}"
                    PID_VAL="${PARTS[$((i+1))]}"
                    WATCHER_PATHS="$WATCHER_PATHS$PATH_VAL|"
                    kill "$PID_VAL" 2>/dev/null && STOPPED_COUNT=$((STOPPED_COUNT+1))
                fi
                i=$((i+3))
            done
            # Clear registry
            echo "" > "$REGISTRY_FILE"
        fi
    fi
    if [ $STOPPED_COUNT -gt 0 ]; then
        echo "Stopped $STOPPED_COUNT watcher(s)"
    fi
fi

# Copy files (clean template first to remove legacy files)
echo "Copying files..."
if [ -d "$INSTALL_DIR/template" ]; then
    rm -rf "$INSTALL_DIR/template"
    echo "Cleaned old template/"
fi
cp -r "$SOURCE_DIR"/* "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/dw"

# Fix Windows line endings (CRLF -> LF)
sed -i 's/\r$//' "$INSTALL_DIR/dw"

echo "Copied unx/ to $INSTALL_DIR"

# Add to PATH
SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

PATH_LINE='export PATH="$HOME/.local/bin/docwire:$PATH"'

if [ -n "$SHELL_RC" ]; then
    if ! grep -q ".local/bin/docwire" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# DocWire" >> "$SHELL_RC"
        echo "$PATH_LINE" >> "$SHELL_RC"
        echo "Added to PATH in $SHELL_RC"
    else
        echo "Already in PATH"
    fi
else
    echo ""
    echo "WARNING: Could not find .bashrc or .zshrc"
    echo "Add this to your shell config manually:"
    echo "  $PATH_LINE"
fi

echo ""
echo "========================================"
echo "Installation complete!"

# Auto-update all registered projects
if [ -x "$INSTALL_DIR/dw" ]; then
    echo ""
    echo "Updating registered projects..."
    "$INSTALL_DIR/dw" all update
fi

# Notify user to restart watchers
if [ $STOPPED_COUNT -gt 0 ]; then
    echo ""
    echo "NOTE: $STOPPED_COUNT watcher(s) were stopped for update."
    echo "Run 'dw all start' to restart them."
fi

echo ""
echo "IMPORTANT: Restart your terminal or run:"
echo "  source $SHELL_RC"
echo ""
echo "Then test with:"
echo "  dw"
echo ""
echo "To setup a docs folder:"
echo "  cd your-docs-folder"
echo "  dw setup"
echo "  dw init"
echo "  dw start"
echo ""
