#!/usr/bin/env python3

import asyncio
import json
from datetime import datetime
from pathlib import Path

from bleak import BleakScanner
from rollei_effekt_parameter import decode_effect, decode_sos
from rollei_effekt_speicher import speichern
from rollei_effekt_stabil import EffektStabil
from rollei_effekt_sperre import ist_gesperrt


ADAPTER = "hci0"
STATUS_FILE = Path("/home/pi/rollei_status.json")


last_raw = None
effekt_stabil = EffektStabil(sekunden=5)


# ---------------------------------------------------------
# Status laden
# ---------------------------------------------------------

def load_status():

    try:

        with open(STATUS_FILE, "r") as f:
            return json.load(f)

    except Exception as e:

        print(f"FEHLER beim Lesen von {STATUS_FILE}: {e}")

        return None


# ---------------------------------------------------------
# Status speichern
# ---------------------------------------------------------

def save_status(status):

    import os
    import tempfile

    fd, tmp_name = tempfile.mkstemp(
        prefix="rollei_status_",
        suffix=".tmp",
        dir=STATUS_FILE.parent
    )

    try:
        with os.fdopen(fd, "w") as f:
            json.dump(
                status,
                f,
                indent=2,
                ensure_ascii=False
            )
            f.write("\n")

        os.replace(tmp_name, STATUS_FILE)

    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


# ---------------------------------------------------------
# Modus
# ---------------------------------------------------------

def mode_name(mode):

    if mode == 0x01:
        return "CCT"

    if mode == 0x12:
        return "HSI"

    if mode in (
        0x03, 0x09, 0x13, 0x04, 0x0C,
        0x0A, 0x0B, 0x0E, 0x05, 0x0D,
        0x06, 0x07, 0x0F
    ):
        return "EFF"

    return None


# ---------------------------------------------------------
# BLE Callback
# ---------------------------------------------------------

def manufacturer_changed(device, advertisement_data):

    global last_raw

    for company_id, data in advertisement_data.manufacturer_data.items():

        raw = bytes(data)

        # Rollei Manufacturer Data
        if len(raw) < 24 or raw[:2] != bytes.fromhex("A7 DC"):
            continue

        # Nur geänderte Daten bearbeiten
        if raw == last_raw:
            continue

        last_raw = raw
        print(f"BLE-ROHDATEN: {raw.hex(chr(32)).upper()}", flush=True)

        # -------------------------------------------------
        # Allgemeine Werte
        # -------------------------------------------------

        mode = raw[14]
        mode_text = mode_name(mode)

        if mode_text is None:
            continue

        if mode_text != "EFF":
            effekt_stabil.zuruecksetzen()

        brightness_raw = int.from_bytes(
            raw[20:22],
            byteorder="little"
        )

        brightness = brightness_raw // 10

        kelvin = int.from_bytes(
            raw[22:24],
            byteorder="little"
        )

        # -------------------------------------------------
        # Status laden
        # -------------------------------------------------

        status = load_status()

        if status is None:
            continue

        changed = False

        # BLE-Diagnosedaten speichern
        ble = status.setdefault("ble", {})

        diagnose = {
            "mode_code": mode,
            "mode_data_1": raw[15],
            "mode_data_2": raw[16],
        }

        for key, value in diagnose.items():
            if ble.get(key) != value:
                ble[key] = value
                changed = True

        # -------------------------------------------------
        # Aktiven Modus speichern
        # -------------------------------------------------

        if status.get("active_mode") != mode_text:

            status["active_mode"] = mode_text
            changed = True

        # -------------------------------------------------
        # CCT
        # -------------------------------------------------

        if mode_text == "CCT":

            if brightness > 0:

                if status["cct"]["brightness"] != brightness:

                    status["cct"]["brightness"] = brightness
                    changed = True

                if kelvin > 0 and status["cct"]["kelvin"] != kelvin:

                    status["cct"]["kelvin"] = kelvin
                    changed = True

        # -------------------------------------------------
        # HSI
        # -------------------------------------------------

        elif mode_text == "HSI":

            hue = int.from_bytes(
                raw[17:19],
                byteorder="little"
            )

            saturation = raw[19]

            if brightness > 0:

                if status["hsi"]["brightness"] != brightness:

                    status["hsi"]["brightness"] = brightness
                    changed = True

            if status["hsi"]["hue"] != hue:

                status["hsi"]["hue"] = hue
                changed = True

            if status["hsi"]["saturation"] != saturation:

                status["hsi"]["saturation"] = saturation
                changed = True

        # -------------------------------------------------
        # EFF
        # -------------------------------------------------

        elif mode_text == "EFF":

            if brightness > 0:

                if status["eff"]["brightness"] != brightness:

                    status["eff"]["brightness"] = brightness
                    changed = True

            # Effektparameter und Helligkeit stabil speichern
            if ist_gesperrt():
                effekt_stabil.zuruecksetzen()

            elif brightness > 0:
                erkannt = decode_effect(
                    mode,
                    raw[15],
                    raw[16]
                )

                if erkannt is None and decode_sos(
                    mode, raw[15], raw[16]
                ) == 13:
                    try:
                        with open("/home/pi/rollei_effekte.json") as f:
                            einstellungen = json.load(f)

                        parameter = int(
                            einstellungen["13"]["parameter"]
                        )

                        if not 1 <= parameter <= 3:
                            raise ValueError("Ungültige SOS-Variante")

                        # SOS-Variante aus BLE-Farbtemperatur bestimmen.
                        # Variante 3 ist unsere eigene HSI-Rot-Kombination.
                        # Bei 9000 K bleibt sie deshalb geschützt.
                        if kelvin == 5600:
                            parameter = 1
                        elif kelvin == 9000 and parameter != 3:
                            parameter = 2

                        erkannt = (13, parameter)

                    except Exception as e:
                        print(
                            f"SOS-SPEICHER: {e}",
                            flush=True
                        )

                if erkannt is None:
                    effekt_stabil.zuruecksetzen()

                else:
                    effekt_nr, parameter = erkannt

                    if effekt_stabil.pruefen(
                        effekt_nr,
                        parameter,
                        brightness
                    ):
                        try:
                            speichern(
                                effekt_nr,
                                parameter,
                                brightness
                            )
                            print(
                                f"EFF-EINSTELLUNG GESPEICHERT: "
                                f"Effekt={effekt_nr}, "
                                f"Parameter={parameter}, "
                                f"Helligkeit={brightness}%",
                                flush=True
                            )
                        except Exception as e:
                            print(
                                f"FEHLER beim Speichern: {e}",
                                flush=True
                            )

        # -------------------------------------------------
        # Status schreiben
        # -------------------------------------------------

        if changed:

            save_status(status)

            now = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            print()
            print(f"{now}  STATUS GEÄNDERT")

            print(f"  Modus:       {mode_text}")
            print(f"  Helligkeit:  {brightness}%")

            if mode_text == "CCT":

                print(f"  Kelvin:      {kelvin} K")

            elif mode_text == "HSI":

                print(f"  Hue:         {hue}°")
                print(f"  Sättigung:   {saturation}%")

            elif mode_text == "EFF":

                print("  Effekt:      Parameter noch nicht ausgewertet")

            print(f"  RSSI:        {advertisement_data.rssi} dBm")
            print(f"  Adresse:     {device.address}")

            print()
            print("  rollei_status.json:")
            print(
                json.dumps(
                    status,
                    indent=2,
                    ensure_ascii=False
                )
            )

            print()
            print(f"  BLE: {raw.hex(' ').upper()}")
            print(flush=True)


# ---------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------

async def main():

    print("Rollei Status Monitor")
    print(f"Adapter: {ADAPTER}")
    print(f"Status:  {STATUS_FILE}")
    print()
    print("Erkannt werden:")
    print("  CCT  - Helligkeit + Kelvin")
    print("  HSI  - Hue + Sättigung + Helligkeit")
    print("  EFF  - Helligkeit")
    print()
    print("Helligkeit 0 wird NICHT als letzter Wert gespeichert.")
    print("Strg+C beendet.")
    print()

    scanner = BleakScanner(
        detection_callback=manufacturer_changed,
        bluez={"adapter": ADAPTER},
    )

    await scanner.start()

    try:

        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        pass

    finally:

        await scanner.stop()


asyncio.run(main())
