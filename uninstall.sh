#!/bin/bash
set -e

BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
SHARE_DIR="$HOME/.local/share/cachyos-update-center"
HICOLOR_DIR="$HOME/.local/share/icons/hicolor"
PIXMAPS_DIR="$HOME/.local/share/pixmaps"

DESKTOP_DIR="$HOME/Desktop"
if [ -d "$HOME/Schreibtisch" ]; then
    DESKTOP_DIR="$HOME/Schreibtisch"
fi

echo "======================================================="
echo "   Deinstallation: CachyOS Update Center              "
echo "======================================================="

rm -rf "$SHARE_DIR"
rm -f "$BIN_DIR/cachyos-update-center"
rm -f "$APP_DIR/cachyos-update-center.desktop"
rm -f "$DESKTOP_DIR/cachyos-update-center.desktop"
rm -f "$PIXMAPS_DIR/cachyos-update-center.png"
rm -f "$PIXMAPS_DIR/cachyos-update-center.svg"
rm -f "$HICOLOR_DIR/scalable/apps/cachyos-update-center.svg"

for sz in 16 24 32 48 64 128 256 512; do
    rm -f "$HICOLOR_DIR/${sz}x${sz}/apps/cachyos-update-center.png"
done

if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$APP_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$HICOLOR_DIR" 2>/dev/null || true
fi

echo "[✓] CachyOS Update Center wurde vollständig deinstalliert."
