#!/usr/bin/env python3

import argparse
import time
from rollei_on_off_eff2 import make_packet, advertise

parser = argparse.ArgumentParser(description="Rollei Effekt 07 – Party")
parser.add_argument("variante", type=int, choices=[1, 2, 3])
args = parser.parse_args()

# Vorherigen Farbmodus verlassen
advertise(
    make_packet(0x13, bytes.fromhex("01 00 00 00 00")),
    seconds=3.0
)
time.sleep(1)

rate = args.variante * 2 - 1

def senden(command, payload):
    advertise(make_packet(command, bytes.fromhex(payload)), seconds=3.0)

print(f"ROLLEI EFFEKT 07 – PARTY – VARIANTE {args.variante}")

# Party starten
senden(0x02, f"0B {rate:02X} 00 00 00")

# Mehrfarbige Zufallssteuerung
senden(0x13, "04 00 00 00 00")

print("Befehlsfolge abgeschlossen.")
