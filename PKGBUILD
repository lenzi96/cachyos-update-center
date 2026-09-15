# Maintainer: Julian / CachyOS Community
pkgname=cachyos-update-center
pkgver=1.0.0
pkgrel=1
pkgdesc="Modernes Update Center für CachyOS mit vorheriger Spiegelserver-Bewertung"
arch=('any')
url="https://github.com/cachyos/cachyos-update-center"
license=('GPL-3.0-or-later')
depends=(
    'python'
    'python-pyqt6'
    'cachyos-rate-mirrors'
    'pacman-contrib'
)
optdepends=(
    'yay: Unterstützung für Aktualisierungen aus dem Arch User Repository (AUR)'
    'snapper: Automatische BTRFS-Wiederherstellungspunkte vor Systemupdates'
    'pacman-contrib: Bereinigung des Pacman-Paketcaches via paccache'
)
source=()
sha256sums=()

package() {
    cd "$srcdir/.."
    install -d "$pkgdir/usr/share/cachyos-update-center"
    install -d "$pkgdir/usr/bin"
    install -d "$pkgdir/usr/share/applications"
    install -d "$pkgdir/usr/share/icons/hicolor/scalable/apps"

    cp -r cachyos_update_center "$pkgdir/usr/share/cachyos-update-center/"
    cp main.py "$pkgdir/usr/share/cachyos-update-center/"
    
    install -Dm755 cachyos-update-center "$pkgdir/usr/bin/cachyos-update-center"
    install -Dm644 cachyos-update-center.desktop "$pkgdir/usr/share/applications/cachyos-update-center.desktop"
    install -Dm644 cachyos_update_center/resources/app_icon.svg "$pkgdir/usr/share/icons/hicolor/scalable/apps/cachyos-update-center.svg"

    for sz in 16 24 32 48 64 128 256 512; do
        if [ -f "cachyos_update_center/resources/app_icon_${sz}.png" ]; then
            install -Dm644 "cachyos_update_center/resources/app_icon_${sz}.png" \
                "$pkgdir/usr/share/icons/hicolor/${sz}x${sz}/apps/cachyos-update-center.png"
        fi
    done
}
