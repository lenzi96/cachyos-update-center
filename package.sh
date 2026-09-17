#!/usr/bin/env bash
# ==============================================================================
# Script to create distributable release archives (tar.gz and .pkg.tar.zst)
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="1.0.1"
DIST_DIR="$DIR/dist"
ARCHIVE_NAME="cachyos-update-center-v${VERSION}"
TARGET_TAR="$DIST_DIR/${ARCHIVE_NAME}.tar.gz"

echo "Erstelle Release-Archiv: ${TARGET_TAR}..."
mkdir -p "$DIST_DIR"

# Clean any pycache and previous build artifacts
find "$DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
rm -rf "$DIR/pkg" "$DIR/src" 2>/dev/null || true

# Create tarball from directory so files unpack cleanly
tar -czf "$TARGET_TAR" \
    --exclude='dist' \
    --exclude='.git' \
    --exclude='*.pkg.tar.zst' \
    --exclude='src' \
    --exclude='pkg' \
    --exclude='__pycache__' \
    --transform "s,^$DIR,$ARCHIVE_NAME," \
    -C "$(dirname "$DIR")" \
    "$(basename "$DIR")"

echo "✓ Erfolgreich erstellt: $TARGET_TAR ($(du -h "$TARGET_TAR" | cut -f1))"

# Build Arch Linux package (.pkg.tar.zst) if makepkg is available
if command -v makepkg >/dev/null 2>&1; then
    echo "Baue Arch Linux Paket (.pkg.tar.zst)..."
    (
        cd "$DIR"
        makepkg -d -f --nodeps
    )
    for pkg in "$DIR"/*.pkg.tar.zst; do
        if [ -f "$pkg" ]; then
            mv "$pkg" "$DIST_DIR/"
            echo "✓ Arch Paket erstellt: $DIST_DIR/$(basename "$pkg") ($(du -h "$DIST_DIR/$(basename "$pkg")" | cut -f1))"
        fi
    done
    rm -rf "$DIR/pkg" "$DIR/src" 2>/dev/null || true
fi

echo "✓ Alle Pakete erfolgreich in $DIST_DIR bereitgestellt!"
