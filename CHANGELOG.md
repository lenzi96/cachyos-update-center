# CachyOS Update Center - Changelog

Alle wichtigen Änderungen und Neuerungen am CachyOS Update Center werden in dieser Datei dokumentiert.

## [1.0.0] - 2026-09-16

### 🌐 Prior Mirror Ranking (Garantierte vorherige Spiegelserver-Bewertung)
- **Automatische Latenz- & Durchsatzmessung:**
  - Führt vor jedem Update-Lauf automatisch `cachyos-rate-mirrors` und `rate-mirrors` aus.
  - Generiert optimierte Ranglisten für `/etc/pacman.d/cachyos-mirrorlist`, `cachyos-v3-mirrorlist`, `cachyos-v4-mirrorlist` und `mirrorlist`.
  - Dedizierte Benchmark-Zentrale zur manuellen Messung mit wählbarem Startland (DE, AT, CH, GeoIP, Global).

### 🛡️ Online-Problemprüfung & Auto-Ausschluss ("Auto-Exclude")
- **Echtzeit-Anbindung an offizielle Feeds:**
  - Live-Parsing von Arch Linux News (`https://archlinux.org/feeds/news/`) und CachyOS-Ankündigungen (`https://discuss.cachyos.org/c/announcements/5.rss`).
  - Automatische Erkennung manueller Interventionen (*"requires manual intervention"*) und bekannter Regressionen.
  - Problembehaftete Pakete werden automatisch erkannt, optisch markiert (`⚠️`), standardmäßig in der Auswahl abgewählt und beim Update via `--ignore <paket>` ausgeschlossen.

### 📸 BTRFS Snapper Snapshot-Schutz
- **Ausfallsicherung vor Paket-Upgrades:**
  - Erkennt BTRFS-Dateisysteme und Snapper-Konfigurationen (`root`).
  - Automatische Erstellung eines Systemschnappschusses vor jedem Update-Lauf.
  - Schneller Rollback über das GRUB/Systemd-Bootmenü im Fehlerfall.

### 🎨 Modernes GUI (CachyOS Emerald Dark Theme)
- **Top Header Bar & Dynamische Breadcrumbs:**
  - Schnelltasten für App-Updates und System-Neuprüfung.
  - Dynamischer Breadcrumb-Titel je nach gewähltem Reiter.
- **Smaragd-Sidebar:**
  - Marken-Header mit App-Icon und Versionsbadge.
  - Sidebar Footer Card mit Kernel-Status (`x86-64-v3/v4`) und Update-Indikator.
- **Paket-Tabelle & Systempflege:**
  - Schnelle Filterung nach CachyOS-, Arch- und AUR-Paketen.
  - Pacman-Cache-Größe & Ein-Klick-Bereinigung (`paccache`).
  - Erkennung verwaister Pakete (`pacman -Qtdq`) und Pacnew-Dateien.

### 🚀 Integrierter GitHub In-App Programm-Updater
- **Multi-Komponenten-Update-Center:**
  - Geräuschlose Hintergrundprüfung auf neue Releases via GitHub API.
  - Unterstützung für öffentliche und private GitHub-Repositories mit Personal Access Token (PAT).
  - Standalone-Installer (`--download-and-install`) und Live-Terminal-Streaming.
  - 1-Klick-Aktualisierung mit nahtlosem Neustart.
