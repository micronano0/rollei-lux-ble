#!/usr/bin/env python3

import argparse
import time
from rollei_on_off_eff2 import make_packet, advertise

parser = argparse.ArgumentParser(description="Rollei Effekt 13 – SOS")
parser.add_argument("variante", type=int, choices=[1, 2, 3])
args = parser.parse_args()

# Vorherigen Farbmodus verlassen
advertise(
    make_packet(0x13, bytes.fromhex("01 00 00 00 00")),
    seconds=3.0
)
time.sleep(1)

def senden(command, payload):
    advertise(make_packet(command, bytes.fromhex(payload)), seconds=3.0)
    time.sleep(1)

print(f"ROLLEI EFFEKT 13 – SOS – VARIANTE {args.variante}")

# Variante 3: Rot über HSI vorbereiten
if args.variante == 3:
    senden(0x07, "00 00 64 14 00")
    senden(0x07, "00 00 64 0A 00")

# SOS starten
senden(0x02, "0F 82 82 00 00")

# Varianten 1 und 2: Farbtemperatur einstellen
if args.variante in (1, 2):
    kelvin = {
        1: "E0 15 00 00 00",
        2: "28 23 00 00 00",
    }[args.variante]
    senden(0x03, kelvin)

print("Befehlsfolge abgeschlossen.")
