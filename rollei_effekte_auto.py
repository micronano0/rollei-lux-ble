#!/usr/bin/env python3
"""Rollei: 13 getestete Effekte, JSON-Parameter, Farbreset, Monitor und Sperre."""
import atexit
import json
import os
import tempfile
import sys
import time
from datetime import datetime
from pathlib import Path

from rollei_on_off_eff2 import make_packet, advertise
from rollei_effekt_sperre import sperren, entsperren

STATUS_FILE = Path('/home/pi/rollei_status.json')
EINSTELLUNGEN_FILE = Path('/home/pi/rollei_effekte.json')
LOG_FILE = Path('/home/pi/rollei_effekte_debug.log')

CODES = {1:0x03, 2:0x09, 3:0x13, 4:0x04, 5:0x0C,
         6:0x0A, 7:0x0B, 8:0x0E, 9:0x05, 10:0x0D,
         11:0x06, 12:0x07, 13:0x0F}
NAMES = {1:'Feuer', 2:'Feuerwerk', 3:'CCT-Wechsel', 4:'Pulsieren',
         5:'Leuchtfeuer', 6:'TV', 7:'Party', 8:'Explosion',
         9:'Kaputte Glühbirne', 10:'Schweißen', 11:'Stroboskop',
         12:'Blitz', 13:'SOS'}


def statusdaten():
    try:
        return json.loads(STATUS_FILE.read_text())
    except (OSError, ValueError):
        return {}


def warten_auf_modus(modus, timeout=3, stabil=0.8):
    ende = time.monotonic() + timeout
    seit = None
    while time.monotonic() < ende:
        if statusdaten().get('active_mode') == modus:
            if seit is None:
                seit = time.monotonic()
            if time.monotonic() - seit >= stabil:
                return True
        else:
            seit = None
        time.sleep(0.1)
    return False


def leise_advertise(command, payload):
    """Verbirgt hcitool-Rohdaten; zeigt sie bei Python-Fehlern wieder an."""
    # Auch subprocess-Ausgaben auf Dateideskriptor 1 werden abgefangen.
    with tempfile.TemporaryFile(mode='w+b') as ausgabe:
        stdout_fd = os.dup(1)
        fehler = None
        try:
            sys.stdout.flush()
            os.dup2(ausgabe.fileno(), 1)
            try:
                advertise(make_packet(command, payload), seconds=3.0)
            except Exception as exc:
                fehler = exc
        finally:
            sys.stdout.flush()
            os.dup2(stdout_fd, 1)
            os.close(stdout_fd)
        if fehler is not None:
            ausgabe.seek(0)
            print(ausgabe.read().decode('utf-8', errors='replace'), end='', flush=True)
            raise fehler


def senden(name, command, payload, pause=1, erwartet=None):
    if isinstance(payload, str):
        payload = bytes.fromhex(payload)
    leise_advertise(command, payload)
    if pause:
        time.sleep(pause)
    if erwartet and not warten_auf_modus(erwartet, timeout=3, stabil=0.8):
        print(f'WARNUNG: Monitor erwartet {erwartet}, erkannt {statusdaten().get("active_mode")}', flush=True)
    d = statusdaten()
    ble = d.get('ble', {})
    meldung = (f'{datetime.now():%Y-%m-%d %H:%M:%S.%f} '
               f'Befehl={name} Modus={d.get("active_mode")} '
               f'CCT={d.get("cct", {}).get("brightness")}% '
               f'HSI={d.get("hsi", {}).get("brightness")}% '
               f'EFF={d.get("eff", {}).get("brightness")}% '
               f'BLE={ble.get("mode_code")},{ble.get("mode_data_1")},{ble.get("mode_data_2")}')
    try:
        with LOG_FILE.open('a') as log:
            log.write(meldung + '\n')
    except OSError as exc:
        print('WARNUNG: Diagnose-Log nicht schreibbar:', exc, flush=True)


def dimmen(wert):
    senden(f'Helligkeit {wert} %', 0x06,
           (wert * 10).to_bytes(2, 'little') + bytes(3))



def cct_licht(aktion, argumente):
    """CCT-Licht ohne Effekt; OFF dimmt nur, ohne JSON zu ändern."""
    if aktion == 'off':
        if argumente:
            raise SystemExit('Aufruf: python3 rollei_effekte_auto.py off')
        sperren()
        atexit.register(entsperren)
        dimmen(0)
        print('CCT-Licht gedimmt auf 0 % (gespeicherte Werte unverändert).', flush=True)
        return

    if len(argumente) not in (0, 2):
        raise SystemExit('Aufruf: python3 rollei_effekte_auto.py on [KELVIN HELLIGKEIT]')
    try:
        einstellungen = json.loads(EINSTELLUNGEN_FILE.read_text())
        if not isinstance(einstellungen, dict):
            raise ValueError('JSON-Wurzel muss ein Objekt sein')
        if argumente:
            kelvin, helligkeit = map(int, argumente)
        else:
            zuletzt = einstellungen.get('cct_licht')
            if not isinstance(zuletzt, dict):
                raise ValueError('Noch keine CCT-Werte gespeichert. Zuerst z. B. on 5600 50 verwenden.')
            kelvin = int(zuletzt['kelvin'])
            helligkeit = int(zuletzt['helligkeit'])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f'CCT-Einstellungen ungültig: {exc}') from exc
    if not 2500 <= kelvin <= 9000:
        raise SystemExit('Kelvin muss zwischen 2500 und 9000 liegen.')
    if not 1 <= helligkeit <= 100:
        raise SystemExit('Helligkeit muss zwischen 1 und 100 % liegen.')

    sperren()
    atexit.register(entsperren)
    print(f'CCT-Licht EIN: {kelvin} K, {helligkeit} %', flush=True)
    cct_payload = (
        kelvin.to_bytes(2, 'little')
        + (helligkeit * 10).to_bytes(2, 'little')
        + bytes([0])
    )
    senden(f'CCT {kelvin} K / {helligkeit} %',
           0x0C, cct_payload, pause=0, erwartet='CCT')
    if statusdaten().get('active_mode') != 'CCT':
        raise SystemExit('CCT-Modus nicht bestätigt; Werte nicht gespeichert.')
    senden(f'Helligkeit {helligkeit} %', 0x06,
           (helligkeit * 10).to_bytes(2, 'little') + bytes(3),
           pause=0)

    # Erst nach erfolgreichem Senden speichern. Bestehende Effektwerte erhalten.
    if argumente:
        einstellungen['cct_licht'] = {'kelvin': kelvin, 'helligkeit': helligkeit}
        tmp = EINSTELLUNGEN_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(einstellungen, indent=2, ensure_ascii=False) + '\n')
        tmp.replace(EINSTELLUNGEN_FILE)
    print('CCT-Licht eingeschaltet.', flush=True)


def main():
    if len(sys.argv) >= 2 and sys.argv[1].lower() in ('on', 'off'):
        cct_licht(sys.argv[1].lower(), sys.argv[2:])
        return
    if len(sys.argv) not in (2, 3, 4):
        raise SystemExit('Aufruf: python3 rollei_effekte_auto.py EFFEKT [VARIANTE] [HELLIGKEIT]')
    try:
        effekt = int(sys.argv[1])
        if effekt not in CODES:
            raise ValueError('Effekt muss 1 bis 13 sein')
        einstellungen = json.loads(EINSTELLUNGEN_FILE.read_text())
        gespeichert = einstellungen[str(effekt)]
        variante = int(sys.argv[2]) if len(sys.argv) >= 3 else int(gespeichert['parameter'])
        helligkeit = int(sys.argv[3]) if len(sys.argv) == 4 else int(gespeichert['helligkeit'])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f'Einstellungen ungültig: {exc}') from exc
    if variante not in (1, 2, 3):
        raise SystemExit('Variante muss 1, 2 oder 3 sein.')
    if not 1 <= helligkeit <= 100:
        raise SystemExit('Helligkeit muss zwischen 1 und 100 % liegen.')

    print(f'Effekt {effekt} – {NAMES[effekt]}, Variante {variante}, Helligkeit {helligkeit}%', flush=True)
    sperren()
    atexit.register(entsperren)

    # Bestätigter Fix: alte Farbsteuerung vor jedem Effekt verlassen.
    senden('Farbmodus zurücksetzen', 0x13, '01 00 00 00 00')

    # Mehrfarbige Effekte: zuerst dimmen, dann Effekt und Farbe aktivieren.
    # So kann der Helligkeitsbefehl die mehrfarbige Steuerung nicht überschreiben.
    if effekt in (2, 5, 7) or (effekt == 3 and variante == 3):
        dimmen(helligkeit)

    rate = 2 * variante - 1
    if effekt == 5:
        payload = bytes([CODES[effekt], 2, variante, 0, 0])
    elif effekt == 13:
        payload = bytes.fromhex('0F 82 82 00 00')
    elif effekt == 3:
        payload = bytes([CODES[effekt], variante, 0, 0, 0])
    elif effekt in (1, 2, 4, 7):
        payload = bytes([CODES[effekt], rate, 0, 0, 0])
    else:
        payload = bytes([CODES[effekt], rate, 0x82, 0, 0])

    if effekt == 13 and variante == 3:
        senden('HSI Rot / 2 %', 0x07, '00 00 64 14 00')
        senden('HSI Rot / 1 %', 0x07, '00 00 64 0A 00')

    senden(f'Effekt {effekt} starten', 0x02, payload,
           pause=2 if effekt in (9, 10, 11, 12) else 1,
           erwartet='EFF')

    if effekt == 1:
        senden('Kelvin 2700 K', 0x03, '8C 0A 00 00 00')
    elif effekt in (2, 7):
        senden('Mehrfarbige Zufallssteuerung', 0x13, '04 00 00 00 00')
    elif effekt == 3:
        farbe = '01 00 00 00 00' if variante in (1, 2) else '04 00 00 00 00'
        senden('CCT-Wechsel Farbsteuerung', 0x13, farbe)
    elif effekt in (9, 10, 11, 12):
        kelvin = {1: ('8C 0A 00 00 00', 2700),
                  2: ('E0 15 00 00 00', 5600),
                  3: ('28 23 00 00 00', 9000)}[variante]
        senden(f'Kelvin {kelvin[1]} K', 0x03, kelvin[0])
    elif effekt == 13 and variante in (1, 2):
        kelvin = 'E0 15 00 00 00' if variante == 1 else '28 23 00 00 00'
        senden('SOS Farbtemperatur', 0x03, kelvin)

    if effekt not in (2, 5, 7) and not (effekt == 3 and variante == 3):
        dimmen(helligkeit)

    # Wie in der bisherigen Zentraldatei nur die SOS-Variante speichern.
    if effekt == 13:
        einstellungen['13']['parameter'] = variante
        tmp = EINSTELLUNGEN_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(einstellungen, indent=2, ensure_ascii=False) + '\n')
        tmp.replace(EINSTELLUNGEN_FILE)

    print('Effekt gestartet.', flush=True)


if __name__ == '__main__':
    main()
