#!/usr/bin/env python3

import argparse
import time
from rollei_on_off_eff2 import make_packet, advertise

parser = argparse.ArgumentParser(description="Rollei Effekt 05 – Leuchtfeuer")
parser.add_argument("variante", type=int, choices=[1, 2, 3])
args = parser.parse_args()

# Vorherigen Farbmodus verlassen
advertise(
    make_packet(0x13, bytes.fromhex("01 00 00 00 00")),
    seconds=3.0
)
time.sleep(1)

print(f"ROLLEI EFFEKT 05 – LEUCHTFEUER – VARIANTE {args.variante}")

# 0C = Leuchtfeuer, 02 = fester Parameter,
# drittes Byte = Sirenenvariante 1 bis 3
payload = bytes([0x0C, 0x02, args.variante, 0x00, 0x00])
advertise(make_packet(0x02, payload), seconds=3.0)

print("Befehlsfolge abgeschlossen.")
