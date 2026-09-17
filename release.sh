#!/usr/bin/env bash
# ==============================================================================
# CachyOS Update Center - Automatisches Release & Upload Skript
# ==============================================================================
# Dieses Skript automatisiert den gesamten Veröffentlichungsprozess:
#  1. Versionsabgleich in allen Projektdateien
#  2. Synchronisation von CHANGELOG.md
#  3. Erstellung der Release-Archive (.tar.gz & .pkg.tar.zst)
#  4. Git Commit & Tagging (vX.Y.Z)
#  5. Git Push zum GitHub Remote (origin main + tags)
#  6. Automatisches Anlegen des GitHub Releases inkl. Asset-Upload
#  7. Lokale Reinstallation für den aktuellen Benutzer
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 1. Ermittle Argumente & Version
NO_INSTALL=0
TARGET_VER=""

for arg in "$@"; do
    if [ "$arg" == "--no-install" ]; then
        NO_INSTALL=1
    elif [[ "$arg" != -* ]] && [ -z "$TARGET_VER" ]; then
        TARGET_VER="$arg"
    fi
done

if [ -z "$TARGET_VER" ]; then
    CURRENT_VER=$(grep -E "^__version__" cachyos_update_center/__init__.py | cut -d'"' -f2)
    echo "===================================================="
    echo "  CachyOS Update Center - Release & GitHub Uploader "
    echo "===================================================="
    echo "Aktuelle Version: $CURRENT_VER"
    read -rp "Neue Version eingeben (oder Enter für '$CURRENT_VER'): " INPUT_VER
    TARGET_VER="${INPUT_VER:-$CURRENT_VER}"
fi

# Entferne führendes 'v', falls eingegeben
TARGET_VER="${TARGET_VER#v}"

echo ">> Bereite Release v$TARGET_VER vor..."

# 2. Aktualisiere Versionsnummern in Projektdateien
sed -i "s/__version__ = .*/__version__ = \"$TARGET_VER\"/" cachyos_update_center/__init__.py
sed -i "s/version=\".*\"/version=\"$TARGET_VER\"/" setup.py
sed -i "s/^version = .*/version = \"$TARGET_VER\"/" pyproject.toml
sed -i "s/^pkgver=.*/pkgver=$TARGET_VER/" PKGBUILD
sed -i "s/^VERSION=.*/VERSION=\"$TARGET_VER\"/" package.sh
sed -i "s|url=\"https://github.com/cachyos/cachyos-update-center\"|url=\"https://github.com/lenzi96/cachyos-update-center\"|" PKGBUILD

# 3. Erstelle Archive (.tar.gz und .pkg.tar.zst)
echo ">> Erstelle Release-Pakete..."
./package.sh

TARBALL="$DIR/dist/cachyos-update-center-v${TARGET_VER}.tar.gz"
if [ ! -f "$TARBALL" ]; then
    echo "FEHLER: Tarball nicht gefunden: $TARBALL"
    exit 1
fi

# 4. Git Commit & Tag
echo ">> Erfasse Änderungen in Git..."
git add -A
if ! git diff-index --quiet HEAD --; then
    git commit -m "Release v${TARGET_VER}: Aktualisierung und Paketierung"
else
    echo "Keine Änderungen zum Committen."
fi

# Tag setzen oder aktualisieren
if git rev-parse "v${TARGET_VER}" >/dev/null 2>&1; then
    echo ">> Tag v${TARGET_VER} existiert bereits, wird auf aktuellen Commit aktualisiert..."
    git tag -f -a "v${TARGET_VER}" -m "Release v${TARGET_VER}"
else
    echo ">> Erstelle neuen Tag v${TARGET_VER}..."
    git tag -a "v${TARGET_VER}" -m "Release v${TARGET_VER}"
fi

# 5. Git Push
echo ">> Übertrage Commits und Tags zu GitHub..."
git push origin main
git push origin "v${TARGET_VER}" --force

# 6. GitHub Release erstellen & Assets hochladen
echo ">> Erstelle / Aktualisiere GitHub Release..."
python3 -c "
import urllib.request, urllib.parse, json, os, re, sys

DIR = '$DIR'
TAG = 'v$TARGET_VER'
TARGET_VER = '$TARGET_VER'
DIST_DIR = os.path.join(DIR, 'dist')

# Ermittle GitHub Token
token = os.environ.get('GITHUB_TOKEN', '').strip() or os.environ.get('GH_TOKEN', '').strip()
if not token:
    try:
        from PyQt6.QtCore import QSettings
        settings = QSettings('CachyOS', 'CachyOSUpdateCenter')
        token = settings.value('updater/github_token', '').strip()
    except Exception:
        pass

if not token:
    git_cred = os.path.expanduser('~/.git-credentials')
    if os.path.exists(git_cred):
        with open(git_cred, 'r') as f:
            for line in f:
                if 'github.com' in line:
                    m = re.search(r':([^@:]+)@github\.com', line.strip())
                    if m:
                        tok = m.group(1).strip()
                        if tok.startswith('github_pat_') or tok.startswith('ghp_'):
                            token = tok
                            break

if not token:
    cfg_token = os.path.expanduser('~/.config/cachyos-update-center/token')
    if os.path.exists(cfg_token):
        with open(cfg_token, 'r') as f:
            token = f.read().strip()

if not token:
    print('WARNUNG: Kein GitHub Token gefunden. Release konnte nicht automatisch erstellt werden.')
    sys.exit(0)

# Ermittle GitHub Repo
repo = 'lenzi96/cachyos-update-center'
try:
    from PyQt6.QtCore import QSettings
    settings = QSettings('CachyOS', 'CachyOSUpdateCenter')
    custom_repo = settings.value('updater/github_repo', '').strip()
    if custom_repo:
        repo = custom_repo
except Exception:
    pass

# Lese Changelog Body (nur die aktuelle Version für das GitHub-Release)
body = ''
changelog_path = os.path.join(DIR, 'CHANGELOG.md')
if os.path.exists(changelog_path):
    with open(changelog_path, 'r', encoding='utf-8') as f:
        full_changelog = f.read()
    v_clean = TARGET_VER.lstrip('v').strip()
    pattern = rf'(##\s*\[v?{re.escape(v_clean)}\][^\n]*\n)(.*?)(?=\n##\s*\[|\Z)'
    m = re.search(pattern, full_changelog, re.DOTALL)
    if m:
        header = m.group(1).strip()
        content = m.group(2).strip()
        content = re.sub(r'\n*---\s*$', '', content).strip()
        body = f'{header}\n\n{content}'.strip()
    else:
        body = full_changelog.strip()

headers = {
    'Authorization': f'Bearer {token}',
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'CachyOS-Update-Center'
}

# Prüfe, ob Release für diesen Tag bereits existiert
rel_id = None
upload_url_raw = None
try:
    check_req = urllib.request.Request(
        f'https://api.github.com/repos/{repo}/releases/tags/{TAG}',
        headers=headers
    )
    with urllib.request.urlopen(check_req) as resp:
        rel_data = json.loads(resp.read().decode())
        rel_id = rel_data.get('id')
        upload_url_raw = rel_data.get('upload_url')
        print(f'Bestehendes Release gefunden: ID {rel_id}')
except Exception:
    pass

if rel_id:
    # Release existiert: Changelog der aktuellen Version via PATCH aktualisieren
    patch_payload = {
        'tag_name': TAG,
        'name': f'CachyOS Update Center {TAG}',
        'body': body,
    }
    patch_req = urllib.request.Request(
        f'https://api.github.com/repos/{repo}/releases/{rel_id}',
        data=json.dumps(patch_payload).encode('utf-8'),
        headers={**headers, 'Content-Type': 'application/json'},
        method='PATCH'
    )
    with urllib.request.urlopen(patch_req) as resp:
        print(f'Release {TAG} aktualisiert.')
else:
    # Neues Release anlegen
    payload = {
        'tag_name': TAG,
        'target_commitish': 'main',
        'name': f'CachyOS Update Center {TAG}',
        'body': body,
        'draft': False,
        'prerelease': False
    }
    create_req = urllib.request.Request(
        f'https://api.github.com/repos/{repo}/releases',
        data=json.dumps(payload).encode('utf-8'),
        headers={**headers, 'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(create_req) as resp:
        rel_data = json.loads(resp.read().decode())
        rel_id = rel_data.get('id')
        upload_url_raw = rel_data.get('upload_url')
        print(f'Neues Release erstellt: ID {rel_id}')

# Assets aus dist/ hochladen
if upload_url_raw and os.path.isdir(DIST_DIR):
    # Vorhandene Assets abfragen
    existing_assets = {}
    try:
        assets_req = urllib.request.Request(f'https://api.github.com/repos/{repo}/releases/{rel_id}/assets', headers=headers)
        with urllib.request.urlopen(assets_req) as resp:
            for a in json.loads(resp.read().decode()):
                existing_assets[a.get('name')] = a.get('id')
    except Exception as e:
        print('Hinweis bei Asset-Prüfung:', e)

    for fname in os.listdir(DIST_DIR):
        if TARGET_VER not in fname:
            continue
        file_path = os.path.join(DIST_DIR, fname)
        if not os.path.isfile(file_path):
            continue

        # Altes Asset löschen falls vorhanden
        if fname in existing_assets:
            try:
                del_req = urllib.request.Request(
                    f'https://api.github.com/repos/{repo}/releases/assets/{existing_assets[fname]}',
                    headers=headers,
                    method='DELETE'
                )
                urllib.request.urlopen(del_req)
                print(f'Altes Asset {fname} ersetzt.')
            except Exception as e:
                print(f'Konnte altes Asset {fname} nicht löschen: {e}')

        content_type = 'application/gzip' if fname.endswith('.tar.gz') else 'application/octet-stream'
        upload_url = upload_url_raw.split('{')[0] + '?name=' + fname
        with open(file_path, 'rb') as f:
            file_data = f.read()

        upload_req = urllib.request.Request(
            upload_url,
            data=file_data,
            headers={**headers, 'Content-Type': content_type},
            method='POST'
        )
        with urllib.request.urlopen(upload_req) as resp:
            asset_info = json.loads(resp.read().decode())
            print(f'✓ Asset erfolgreich hochgeladen: {fname} -> {asset_info.get(\"browser_download_url\")}')
"

# 7. Lokale Reinstallation
if [ "$NO_INSTALL" -eq 1 ]; then
    echo ">> Lokale Reinstallation übersprungen (--no-install aktiv)."
else
    echo ">> Installiere Release v$TARGET_VER lokal in Benutzerumgebung..."
    ./install.sh
fi

echo ""
echo "===================================================="
echo "✓ Release v$TARGET_VER erfolgreich veröffentlicht!"
echo "✓ Git Commits & Tag übertragen: https://github.com/lenzi96/cachyos-update-center"
echo "✓ GitHub Release & Paket-Assets hochgeladen"
if [ "$NO_INSTALL" -eq 1 ]; then
    echo "✓ Lokale Installation wie gewünscht übersprungen."
else
    echo "✓ Lokal installiert und einsatzbereit!"
fi
echo "===================================================="
