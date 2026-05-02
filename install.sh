#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  Wine Game Installer — install.sh
#  Copies the app to ~/Applications and adds a KDE menu entry
# ─────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_SRC="$SCRIPT_DIR/wine-game-installer.py"
APP_DEST="$HOME/Applications/wine-game-installer.py"
DESKTOP_FILE="$HOME/.local/share/applications/WineInstaller.desktop"

# ── Checks ────────────────────────────────────────────────────
if [ ! -f "$APP_SRC" ]; then
    echo "✗  Error: wine-game-installer.py not found next to install.sh"
    echo "   Make sure both files are in the same folder."
    read -p "Press Enter to close..."
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "✗  Error: python3 not found."
    read -p "Press Enter to close..."
    exit 1
fi

# ── Install ───────────────────────────────────────────────────
echo "── Installing Wine Game Installer..."

mkdir -p "$HOME/Applications"
cp "$APP_SRC" "$APP_DEST"
chmod +x "$APP_DEST"
echo "✓  Copied to $APP_DEST"

mkdir -p "$HOME/.local/share/applications"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=Wine Game Installer
Comment=Install Windows games on Steam Deck using Wine
Exec=python3 $APP_DEST
Icon=wine
Terminal=false
Type=Application
Categories=Game;
StartupNotify=true
EOF
echo "✓  Menu shortcut created"

# Refresh KDE application menu
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi
if command -v kbuildsycoca5 &>/dev/null; then
    kbuildsycoca5 --noincremental 2>/dev/null || true
fi

# ── Success ───────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓  Wine Game Installer installed successfully!"
echo ""
echo "   Launch it from:"
echo "   → Applications menu → Games → Wine Game Installer"
echo "   → Or run: python3 ~/Applications/wine-game-installer.py"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -p "Press Enter to close..."

# ── Cleanup ───────────────────────────────────────────────────
rm -f "$SCRIPT_DIR/wine-game-installer.py"
rm -f "$SCRIPT_DIR/install.sh"
rm -f "$SCRIPT_DIR/README.md"
rmdir "$SCRIPT_DIR" 2>/dev/null || true
