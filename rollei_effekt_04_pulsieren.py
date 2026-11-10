#!/usr/bin/env python3

import argparse
import time
from rollei_on_off_eff2 import make_packet, advertise

parser = argparse.ArgumentParser(description="Rollei Effekt 04 – Pulsieren")
parser.add_argument("variante", type=int, choices=[1, 2, 3])
args = parser.parse_args()

# Vorherigen Farbmodus verlassen
advertise(
    make_packet(0x13, bytes.fromhex("01 00 00 00 00")),
    seconds=3.0
)
time.sleep(1)

rate = args.variante * 2 - 1

print(f"ROLLEI EFFEKT 04 – PULSIEREN – VARIANTE {args.variante}")

payload = bytes([0x04, rate, 0x00, 0x00, 0x00])
advertise(make_packet(0x02, payload), seconds=3.0)

print("Befehlsfolge abgeschlossen.")
