#!/usr/bin/env python3

import argparse
import time
from rollei_on_off_eff2 import make_packet, advertise

parser = argparse.ArgumentParser(description="Rollei Effekt 12 – Blitz")
parser.add_argument("variante", type=int, choices=[1, 2, 3])
args = parser.parse_args()

# Vorherigen Farbmodus verlassen
advertise(
    make_packet(0x13, bytes.fromhex("01 00 00 00 00")),
    seconds=3.0
)
time.sleep(1)

rate = args.variante * 2 - 1
kelvin = {
    1: ("8C 0A", 2700),
    2: ("E0 15", 5600),
    3: ("28 23", 9000),
}[args.variante]

print(f"ROLLEI EFFEKT 12 – BLITZ – VARIANTE {args.variante} ({kelvin[1]} K)")

# Effekt starten
advertise(
    make_packet(0x02, bytes.fromhex(f"07 {rate:02X} 82 00 00")),
    seconds=3.0
)

time.sleep(2)

# Farbtemperatur einstellen
advertise(
    make_packet(0x03, bytes.fromhex(f"{kelvin[0]} 00 00 00")),
    seconds=3.0
)

print("Befehlsfolge abgeschlossen.")
