#!/usr/bin/env python3

import asyncio
import secrets
import subprocess
import time

from bleak import BleakScanner

HCI = "hci0"

OFF = (
    "07 09 43 4F 4C 42 4F 52 "
    "02 0A 01 11 07 1E "
    "0B A7 DC 75 03 33 37 05 02 06 00 00 00 00 00"
)

TAKEOVER = (
    "07 09 43 4F 4C 42 4F 52 "
    "02 0A 01 11 07 1E "
    "0A 00 00 59 83 13 FF FF 01 A7 DC "
    "00 00 00 00"
)


def hci(opcode, data=""):
    cmd = ["sudo", "hcitool", "-i", HCI, "cmd", "0x08", opcode]

    if data:
        cmd.extend(data.split())

    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def random_address():
    addr = bytearray(secrets.token_bytes(6))
    addr[5] = (addr[5] & 0x3F) | 0xC0
    return " ".join(f"{b:02X}" for b in addr)


def advertise(data, seconds=4.5):
    address = random_address()

    hci("0x000A", "00")
    hci("0x0005", address)
    hci("0x0006", "00 A0 00 A0 00 02 00 00 07 00")
    hci("0x0008", f"{len(data.split()):02X} " + data)
    hci("0x0009", "00")
    hci("0x000A", "01")

    time.sleep(seconds)

    hci("0x000A", "00")


def manufacturer_is_a7dc(advertisement_data):
    for _, data in advertisement_data.manufacturer_data.items():
        raw = bytes(data)

        if len(raw) >= 22 and raw[:2] == bytes.fromhex("A7 DC"):
            return raw

    return None


class A7DCDetector:

    def __init__(self):
        self.found = asyncio.Event()
        self.raw = None

    def callback(self, device, advertisement_data):
        raw = manufacturer_is_a7dc(advertisement_data)

        if raw is None:
            return

        if self.found.is_set():
            return

        self.raw = raw

        brightness_raw = int.from_bytes(
            raw[20:22],
            byteorder="little"
        )

        print(
            f"A7 DC erkannt: Helligkeit={brightness_raw}",
            flush=True
        )
        print(
            f"  Adresse: {device.address}",
            flush=True
        )
        print(
            f"  Daten:   {raw.hex(' ').upper()}",
            flush=True
        )

        self.found.set()


async def wait_for_a7dc(timeout=2.0):
    detector = A7DCDetector()

    scanner = BleakScanner(
        detection_callback=detector.callback,
        bluez={"adapter": HCI},
    )

    print("Warte auf A7 DC Helligkeitswert ...", flush=True)

    await scanner.start()

    try:
        try:
            await asyncio.wait_for(
                detector.found.wait(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            pass
    finally:
        await scanner.stop()

    return detector.found.is_set()


async def main():

    print("=== ROLLEI AUTO INIT hci0 ===", flush=True)

    attempt = 1

    while True:

        print()
        print(f"=== VERSUCH {attempt} ===", flush=True)

        print("OFF senden ...", flush=True)
        advertise(OFF, 0.5)

        print("TAKEOVER senden ...", flush=True)
        advertise(TAKEOVER, 1.5)

        if await wait_for_a7dc(timeout=5.0):

            print()
            print("========================================", flush=True)
            print("✓ ROLLEI ÜBERNOMMEN", flush=True)
            print("✓ A7 DC Helligkeitswert erkannt", flush=True)
            print("========================================", flush=True)

            # -------------------------------------------------
            # NEU:
            # Nicht mehr beenden.
            # Solange A7 DC empfangen wird, bleibt die Rollei
            # als vorhanden markiert.
            # -------------------------------------------------

            while True:

                await asyncio.sleep(25.0)

                print(
                    "Prüfe, ob Rollei noch vorhanden ist ...",
                    flush=True
                )

                if await wait_for_a7dc(timeout=10.0):

                    print(
                        "✓ Rollei weiterhin vorhanden.",
                        flush=True
                    )

                else:

                    print()
                    print("========================================", flush=True)
                    print("! ROLLEI NICHT MEHR GEFUNDEN", flush=True)
                    print("! Starte Suche erneut ...", flush=True)
                    print("========================================", flush=True)

                    break

        else:

            print("Kein Helligkeitswert.", flush=True)
            print("Neuer Versuch ...", flush=True)

        attempt += 1
        await asyncio.sleep(3.2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAbgebrochen.", flush=True)
