#!/usr/bin/env bash
set -Eeuo pipefail

USER_NAME=pi
HOME_DIR=/home/pi
SERVICE_DIR=/etc/systemd/system
ARCHIVE_NAME=Rollei_Fotobox_FUNKTIONIERT_20261109_221237.zip
BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE="${1:-$BASE_DIR/$ARCHIVE_NAME}"
BACKUP_DIR=""
STAGING=""

fail() {
    echo "FEHLER: $*" >&2
    exit 1
}

[[ $EUID -eq 0 ]] || fail "Bitte mit sudo starten."
[[ -d "$HOME_DIR" ]] || fail "/home/pi fehlt."
id "$USER_NAME" &>/dev/null || fail "Benutzer pi fehlt."
[[ $(id -u "$USER_NAME") -ne 0 ]] || fail "pi darf nicht root sein."

. /etc/os-release
[[ ${VERSION_CODENAME:-} == trixie ]] ||
    fail "Nur Debian 13 (trixie) unterstützt."

[[ -f "$ARCHIVE" ]] ||
    fail "ZIP nicht gefunden: $ARCHIVE"

command -v python3 >/dev/null ||
    fail "Python 3 fehlt."

if ! command -v unzip >/dev/null; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y unzip
fi

STAGING=$(mktemp -d)
trap '[[ -z "$STAGING" ]] || rm -rf -- "$STAGING"' EXIT

unzip -q "$ARCHIVE" -d "$STAGING"

echo "Prüfe Sicherungsarchiv ..."

for f in \
    rollei_fotobox.py \
    rollei_effekte_auto.py \
    rollei_on_off_eff2.py \
    rollei_effekt_sperre.py \
    rollei_monitor.py \
    rollei_auto_init.py \
    rollei_effekte.json \
    rollei-auto-init.service \
    rollei-monitor.service
do
    [[ -f "$STAGING/$f" ]] ||
        fail "ZIP unvollständig: $f fehlt."
done

python3 - "$STAGING" <<'PY'
import ast
import pathlib
import sys

directory = pathlib.Path(sys.argv[1])

for file in directory.glob("*.py"):
    ast.parse(
        file.read_text(encoding="utf-8"),
        filename=str(file)
    )

print("Python-Syntax erfolgreich geprüft.")
PY

for service in rollei-auto-init.service rollei-monitor.service; do
    grep -Fq 'User=pi' "$STAGING/$service" ||
        fail "$service: Benutzer stimmt nicht."

    grep -Fq '/home/pi/' "$STAGING/$service" ||
        fail "$service: Pfad stimmt nicht."
done

echo "Installiere benötigte Pakete ..."

apt-get update

DEBIAN_FRONTEND=noninteractive apt-get install -y \
    bluez \
    python3 \
    python3-pip \
    python3-venv \
    python3-bleak \
    python3-dbus \
    python3-gi \
    rfkill \
    sudo \
    unzip

command -v hcitool >/dev/null ||
    fail "hcitool nicht gefunden."

BACKUP_DIR="$HOME_DIR/rollei_sicherungen/vor_installation_$(date +%Y%m%d_%H%M%S)"

install -d -o pi -g pi -m 750 "$BACKUP_DIR"

echo "Sichere vorhandene Rollei-Dateien ..."

for src in "$STAGING"/*.py "$STAGING"/*.json; do
    [[ -f "$src" ]] || continue
    name=$(basename "$src")

    if [[ -f "$HOME_DIR/$name" ]]; then
        cp -a -- "$HOME_DIR/$name" "$BACKUP_DIR/$name"
    fi
done

for service in rollei-auto-init.service rollei-monitor.service; do
    if [[ -e "$SERVICE_DIR/$service" ]]; then
        cp -a -- "$SERVICE_DIR/$service" "$BACKUP_DIR/$service"
    fi
done

if [[ -e /etc/sudoers.d/rollei ]]; then
    cp -a /etc/sudoers.d/rollei "$BACKUP_DIR/sudoers-rollei"
fi

echo "Installiere Rollei-Programme ..."

for service in rollei-auto-init.service rollei-monitor.service; do
    systemctl stop "$service" 2>/dev/null || true
done

for src in "$STAGING"/*.py "$STAGING"/*.json; do
    [[ -f "$src" ]] || continue

    install -o pi -g pi -m 644 \
        "$src" "$HOME_DIR/$(basename "$src")"
done

echo "Installiere systemd-Services ..."

for service in rollei-auto-init.service rollei-monitor.service; do
    install -o root -g root -m 644 \
        "$STAGING/$service" "$SERVICE_DIR/$service"
done

echo "Richte Bluetooth-Berechtigung ein ..."

printf '%s\n' \
    'pi ALL=(root) NOPASSWD: /usr/bin/hcitool' \
    > /etc/sudoers.d/rollei

chmod 440 /etc/sudoers.d/rollei

visudo -cf /etc/sudoers.d/rollei >/dev/null ||
    fail "sudoers-Prüfung fehlgeschlagen."

echo "Aktiviere Bluetooth ..."

systemctl enable --now bluetooth.service

echo "Aktiviere Rollei-Services ..."

systemctl daemon-reload

systemctl enable --now \
    rollei-auto-init.service \
    rollei-monitor.service

echo "Prüfe Python-Bleak ..."

sudo -u pi /usr/bin/python3 - <<'PY'
import bleak
print("Bleak erfolgreich geladen.")
PY

echo "Prüfe Bluetooth-Adapter hci0 ..."

if [[ ! -e /sys/class/bluetooth/hci0 ]]; then
    fail "Bluetooth-Adapter hci0 nicht gefunden."
fi

BT_INFO=$(btmgmt --index 0 info) ||
    fail "Bluetooth-Controller hci0 kann nicht abgefragt werden."

if ! grep -Eq 'supported settings:.*[[:space:]]le([[:space:]]|$)' <<< "$BT_INFO"; then
    fail "Bluetooth-Controller unterstützt kein BLE."
fi

# Bluetooth-Soft-Sperre gegebenenfalls aufheben.
# Eine Hardware-Sperre kann damit nicht aufgehoben werden.
if command -v rfkill >/dev/null 2>&1; then
    echo "Prüfe Bluetooth-rfkill ..."
    rfkill unblock bluetooth ||
        fail "Bluetooth-rfkill konnte nicht entsperrt werden."
fi

# Bluetooth kann nach rfkill unblock bereits automatisch starten.
# Deshalb den tatsächlichen Controllerzustand erneut abfragen.
BT_INFO=$(btmgmt --index 0 info) ||
    fail "Bluetooth-Controller konnte nicht abgefragt werden."

if ! grep -Eq 'current settings:.*[[:space:]]powered([[:space:]]|$)' <<< "$BT_INFO"; then
    echo "Schalte Bluetooth hci0 ein ..."

    for versuch in 1 2 3 4 5; do
        bluetoothctl power on || true
        sleep 2

        BT_INFO=$(btmgmt --index 0 info) ||
            fail "Bluetooth-Controller konnte nicht geprüft werden."

        if grep -Eq 'current settings:.*[[:space:]]powered([[:space:]]|$)' <<< "$BT_INFO"; then
            echo "Bluetooth hci0 erfolgreich eingeschaltet."
            break
        fi

        echo "Bluetooth noch nicht bereit (Versuch $versuch/5)."
    done
fi

BT_INFO=$(btmgmt --index 0 info) ||
    fail "Bluetooth-Controller konnte nicht erneut geprüft werden."

grep -Eq 'current settings:.*(^| )powered( |$)' <<< "$BT_INFO" ||
    fail "Bluetooth hci0 ist weiterhin ausgeschaltet."

grep -Eq 'current settings:.*[[:space:]]le([[:space:]]|$)' <<< "$BT_INFO" ||
    fail "Bluetooth Low Energy ist nicht aktiviert."

echo "Bluetooth hci0 ist eingeschaltet und BLE ist aktiv."

echo
echo "=== Rollei-Service-Status ==="

systemctl --no-pager --full status \
    rollei-auto-init.service \
    rollei-monitor.service | head -45 || true

echo
echo "========================================================"
echo " ROLLEI-LAMPENTEST"
echo "========================================================"
echo
echo "Bitte jetzt die Rollei LUX Compact RGB LED einschalten."
echo
echo "Hinweis: Bluetooth am Smartphone moeglichst deaktivieren."
echo
echo "Anschliessend ENTER druecken, um den Lampentest zu starten."
echo

if [[ -r /dev/tty ]]; then
    read -r -p "Weiter mit ENTER ... " < /dev/tty
else
    echo "WARNUNG: Keine interaktive Eingabe moeglich."
    echo "Lampentest wird ohne Bestaetigung gestartet."
fi

echo
echo "=== Automatischer Rollei-Lampentest ==="

LAMPENTEST="NICHT ERFOLGREICH"

if systemctl is-active --quiet rollei-auto-init.service &&
   systemctl is-active --quiet rollei-monitor.service; then

    for VERSUCH in 1 2 3; do
        echo
        echo "Lampentest: Versuch $VERSUCH von 3"

        if sudo -u pi /usr/bin/python3 \
            "$HOME_DIR/rollei_effekte_auto.py" 5 1 50; then

            echo "Warte 5 Sekunden auf Rollei-Monitor ..."
            sleep 5

            if sudo -u pi /usr/bin/python3 - "$HOME_DIR/rollei_status.json" <<'STATUS_TEST'
import json
import sys

try:
    with open(sys.argv[1]) as f:
        d = json.load(f)

    ble = d.get("ble", {})
    eff = d.get("eff", {})

    korrekt = (
        d.get("active_mode") == "EFF"
        and ble.get("mode_code") == 12
        and ble.get("mode_data_1") == 2
        and ble.get("mode_data_2") == 1
        and eff.get("brightness") == 50
    )

    print(
        "Monitor:",
        d.get("active_mode"),
        "BLE:", ble,
        "Helligkeit:", eff.get("brightness")
    )

    sys.exit(0 if korrekt else 1)

except (OSError, ValueError, TypeError) as exc:
    print("Monitorprüfung fehlgeschlagen:", exc)
    sys.exit(1)
STATUS_TEST
            then
                LAMPENTEST="ERFOLGREICH (Versuch $VERSUCH)"
                break
            fi
        fi

        echo "Lampentest noch nicht bestätigt."

        if [[ "$VERSUCH" -lt 3 ]]; then
            echo "Wiederhole Effektstart ..."
            sleep 3
        fi
    done
else
    echo "WARNUNG: Mindestens ein Rollei-Dienst läuft nicht."
fi

echo
echo "╔══════════════════════════════════════════════════════╗"
echo "║                                                      ║"
echo "║        ROLLEI BLE - INSTALLATION ABGESCHLOSSEN       ║"
echo "║                                                      ║"
echo "╚══════════════════════════════════════════════════════╝"

echo
echo "Bluetooth hci0: AKTIV"
echo "Bluetooth Low Energy: AKTIV"
echo "Auto-Init: $(systemctl is-active rollei-auto-init.service)"
echo "Monitor:   $(systemctl is-active rollei-monitor.service)"
echo "Lampentest: $LAMPENTEST"

echo
echo "========================================================"
echo " MANUELLE STEUERBEFEHLE"
echo "========================================================"

cat <<'ROLLEI_BEFEHLE'

Lampe EIN (5600 Kelvin, 50 Prozent):
  python3 ~/rollei_fotobox.py on 5600 50

Lampe AUS:
  python3 ~/rollei_fotobox.py off

Gespeicherte CCT-Werte:
  python3 ~/rollei_fotobox.py status

Aktuelle CCT-Werte speichern:
  python3 ~/rollei_fotobox.py save

Effekt starten (Effekt 5, Variante 1, Helligkeit 50%):
  python3 ~/rollei_effekte_auto.py 5 1 50

Effekte 1 bis 13:
  python3 ~/rollei_effekte_auto.py EFFEKT [VARIANTE] [HELLIGKEIT]

Variante: 1 bis 3 | Helligkeit: 1 bis 100%

ROLLEI_BEFEHLE

echo "========================================================"
echo " SICHERUNG"
echo "========================================================"
echo "$BACKUP_DIR"

echo
echo "Installation abgeschlossen."
echo "Hinweis: Ein erfolgreicher Lampenbefehl bestätigt"
echo "nicht automatisch die tatsächliche Reaktion der Lampe."
