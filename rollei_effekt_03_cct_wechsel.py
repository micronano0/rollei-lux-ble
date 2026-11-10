#!/usr/bin/env python3

import argparse
import time
from rollei_on_off_eff2 import make_packet, advertise

parser = argparse.ArgumentParser(description="Rollei Effekt 03 – CCT-Wechsel")
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

print(f"ROLLEI EFFEKT 03 – CCT-WECHSEL – VARIANTE {args.variante}")

# Effekt starten: Variante 1, 2 oder 3 direkt im RATE-Byte
senden(0x02, f"13 {args.variante:02X} 00 00 00")

# Farbsteuerung passend zur Variante
if args.variante in (1, 2):
    senden(0x13, "01 00 00 00 00")  # Gelb-Weiß
else:
    senden(0x13, "04 00 00 00 00")  # Mehrfarbige Übergänge

print("Befehlsfolge abgeschlossen.")
