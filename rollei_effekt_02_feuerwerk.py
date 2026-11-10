#!/usr/bin/env python3

import argparse
import time
from rollei_on_off_eff2 import make_packet, advertise

parser = argparse.ArgumentParser(description="Rollei Effekt 02 – Feuerwerk")
parser.add_argument("variante", type=int, choices=[1, 2, 3])
args = parser.parse_args()

# Vorherigen Farbmodus verlassen
advertise(
    make_packet(0x13, bytes.fromhex("01 00 00 00 00")),
    seconds=3.0
)
time.sleep(1)

rate = args.variante * 2 - 1

print(f"ROLLEI EFFEKT 02 – FEUERWERK – VARIANTE {args.variante}")

# Feuerwerk starten
advertise(
    make_packet(0x02, bytes.fromhex(f"09 {rate:02X} 00 00 00")),
    seconds=3.0
)

# Mehrfarbige Zufallssteuerung
advertise(
    make_packet(0x13, bytes.fromhex("04 00 00 00 00")),
    seconds=3.0
)

print("Befehlsfolge abgeschlossen.")
