#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
echo "   Installation: CachyOS Update Center                "
echo "======================================================="

mkdir -p "$BIN_DIR" "$APP_DIR" "$SHARE_DIR" "$PIXMAPS_DIR"

# 1. Anwendungsdateien nach ~/.local/share/cachyos-update-center kopieren
echo "→ Kopiere Anwendungsdateien nach $SHARE_DIR..."
rm -rf "$SHARE_DIR/cachyos_update_center"
cp -r "$DIR/cachyos_update_center" "$SHARE_DIR/"
cp "$DIR/main.py" "$SHARE_DIR/"
echo "[✓] Anwendungsdateien installiert"

# 2. Standalone-Launcher nach ~/.local/bin/cachyos-update-center installieren
echo "→ Installiere Launcher nach $BIN_DIR/cachyos-update-center..."
cp "$DIR/cachyos-update-center" "$BIN_DIR/cachyos-update-center"
chmod 755 "$BIN_DIR/cachyos-update-center"
echo "[✓] Standalone-Binary installiert"

# 3. Icons installieren (Multi-Resolution PNGs + SVG)
echo "→ Installiere Icons..."
mkdir -p "$HICOLOR_DIR/scalable/apps"
cp "$DIR/cachyos_update_center/resources/app_icon.svg" "$HICOLOR_DIR/scalable/apps/cachyos-update-center.svg"
cp "$DIR/cachyos_update_center/resources/app_icon.svg" "$PIXMAPS_DIR/cachyos-update-center.svg"

for sz in 16 24 32 48 64 128 256 512; do
    if [ -f "$DIR/cachyos_update_center/resources/app_icon_${sz}.png" ]; then
        mkdir -p "$HICOLOR_DIR/${sz}x${sz}/apps"
        cp "$DIR/cachyos_update_center/resources/app_icon_${sz}.png" "$HICOLOR_DIR/${sz}x${sz}/apps/cachyos-update-center.png"
    fi
done
cp "$DIR/cachyos_update_center/resources/app_icon_256.png" "$PIXMAPS_DIR/cachyos-update-center.png"
echo "[✓] Icons erfolgreich installiert"

# 4. Desktop-Eintrag installieren
echo "→ Installiere Menü-Eintrag..."
cp "$DIR/cachyos-update-center.desktop" "$APP_DIR/cachyos-update-center.desktop"
chmod 644 "$APP_DIR/cachyos-update-center.desktop"

# Optional: Verknüpfung auf Desktop/Schreibtisch
if [ -d "$DESKTOP_DIR" ]; then
    cp "$DIR/cachyos-update-center.desktop" "$DESKTOP_DIR/cachyos-update-center.desktop"
    chmod +x "$DESKTOP_DIR/cachyos-update-center.desktop" 2>/dev/null || true
    echo "[✓] Desktop-Verknüpfung erstellt auf $DESKTOP_DIR"
fi

# Caches aktualisieren
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$APP_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$HICOLOR_DIR" 2>/dev/null || true
fi

echo "======================================================="
echo "   ✓ CachyOS Update Center erfolgreich installiert!   "
echo "======================================================="
echo "Starten über das Anwendungsmenü oder im Terminal via:"
echo "   cachyos-update-center"
echo "======================================================="
