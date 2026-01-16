#!/bin/bash
# DocWire Uninstaller for Linux/Mac/WSL
# Run: ./uninstall.sh

echo "DocWire Uninstaller (Linux/Mac/WSL)"
echo "========================================"

INSTALL_DIR="$HOME/.local/bin/docwire"

# Remove files
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "Removed: $INSTALL_DIR"
else
    echo "Not installed: $INSTALL_DIR not found"
fi

# Remove PATH entry from shell config
SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ]; then
    if grep -q ".local/bin/docwire" "$SHELL_RC" 2>/dev/null; then
        # Remove the DocWire lines
        sed -i '/# DocWire/d' "$SHELL_RC"
        sed -i '/.local\/bin\/docwire/d' "$SHELL_RC"
        echo "Removed PATH entry from $SHELL_RC"
    else
        echo "No PATH entry found in $SHELL_RC"
    fi
fi

echo ""
echo "========================================"
echo "Uninstall complete!"
echo ""
echo "Note: .dw/ folders in your project folders are NOT removed."
echo "Delete them manually with: rm -rf .dw/"
echo ""
