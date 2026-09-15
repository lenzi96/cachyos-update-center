# ⚡ CachyOS Update Center

> **Modernes Update Center für CachyOS – immer mit vorheriger Spiegelserver-Bewertung.**

Ein leistungsstarkes, elegantes Desktop-Update-Center für **CachyOS**, entwickelt in Python 3 & PyQt6 im unverwechselbaren CachyOS-Emerald-Design.

---

## 🌟 Hauptmerkmale

### 1. Immer mit vorheriger Spiegelserver-Bewertung ("Prior Mirror Ranking")
- **Geschwindigkeits-Garantie**: Vor jedem System-Update werden automatisch die schnellsten und latenzärmsten Spiegelserver für CachyOS (inkl. x86-64-v3 und v4 Repositorien) sowie Arch Linux via `rate-mirrors` und `cachyos-rate-mirrors` ermittelt.
- **Live-Benchmark-Dashboard**: Detaillierte Übersicht über Ping (Latenz in ms), Durchsatz (MB/s), Server-Standort (`[DE]`, `[AT]`, `[CH]`, etc.) und Rangliste.
- **Einfache Konfiguration**: Wähle dein bevorzugtes Startland (z. B. Deutschland, DACH, Europa, GeoIP-Auto-Erkennung).

### 2. Online-Problemprüfung & Automatischer Schutz ("Auto-Exclude")
- **Echtzeit-Sicherheitsanalyse**: Fragt vor jeder Aktualisierung live die Arch Linux News (`archlinux.org/feeds/news/`) und CachyOS-Ankündigungen (`discuss.cachyos.org`) ab.
- **Automatischer Ausschluss**: Erkennt Pakete mit manueller Eingriffserfordernis (z. B. *"requires manual intervention"*), bekannten Regressionen oder Sicherheitsvorfällen.
- **Schutz beim Update**: Problembehaftete Pakete werden in der Übersicht optisch hervorgehoben (`⚠️`), standardmäßig **automatisch abgewählt** und im Pacman-/Yay-Befehl über `--ignore <paket>` ausgeschlossen, um Systeminkonsistenzen zu verhindern.

### 3. 4-Phasen Update-Pipeline
1. ⚡ **Spiegelserver bewerten & anwenden**: Optimiert `/etc/pacman.d/*mirrorlist` vor dem Paketdownload.
2. 📸 **BTRFS Snapper-Snapshot**: Automatischer System-Wiederherstellungspunkt als Ausfallsicherung vor dem Upgrade.
3. 📦 **Online-Problemprüfung & Paket-Synchronisierung**: Schließt gemeldete Problem-Pakete via `--ignore` aus und aktualisiert System & AUR.
4. 🧹 **Post-Update Systempflege**: Bereinigt alte Cache-Versionen (`paccache`), prüft auf `.pacnew`-Dateien und erkennt, ob ein Kernel-Neustart ansteht.

### 4. Ausführliche Paket-Übersicht
- Tabelle mit allen ausstehenden Aktualisierungen (Versionssprung, Repositorium, Download-Größe, Beschreibung).
- Filter nach CachyOS-Optimierungen, System-Paketen und AUR.
- Selektive Auswahl: Ganze Updates ausführen oder einzelne Pakete abwählen.

### 5. Integrierte Systemwartung

- **Pacman-Cache**: Schnelle Bereinigung älterer Paketversionen.
- **Verwaiste Pakete (Orphans)**: Erkennung und Entfernung nicht mehr benötigter Abhängigkeiten (`pacman -Qtdq`).
- **Snapper-Wiederherstellungspunkte**: Übersicht und manuelle Erstellung von System-Snapshots.

---

## 🚀 Installation

### Option A: Grafischer Installations-Assistent (Empfohlen)
```bash
cd /run/media/julian/HDD/Linux/cachyos-update-center
./install-gui.sh
```

### Option B: Schnelle Terminal-Installation
```bash
cd /run/media/julian/HDD/Linux/cachyos-update-center
./install.sh
```

### Option C: Arch / CachyOS Paketbau via PKGBUILD
```bash
cd /run/media/julian/HDD/Linux/cachyos-update-center
makepkg -si
```

---

## 🖥️ Starten

Nach der Installation findest du das Update Center in deinem Anwendungsmenü unter **System ➔ CachyOS Update Center** oder kannst es direkt im Terminal starten:

```bash
cachyos-update-center
```

Entwicklungsmodus ohne Installation:
```bash
python3 main.py
```

---

## 🗑️ Deinstallation

Zum sauberen Entfernen aller installierten Dateien:
```bash
cd /run/media/julian/HDD/Linux/cachyos-update-center
./uninstall.sh
```

---

## 📜 Lizenz
GPL-3.0-or-later – CachyOS Community & Julian.
