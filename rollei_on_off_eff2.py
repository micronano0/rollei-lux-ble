#!/usr/bin/env python3

import random
import subprocess
import sys
import time


ADAPTER = "hci0"

# Advertising prefix used by the working Rollei script.
PREFIX = bytes.fromhex(
    "07 09 43 4F 4C 42 4F 52 "
    "02 0A 01 "
    "11 07 "
    "1E 0E"
)


# Rollei EFF-Effekt:
#
# App-Effekt  -> Command-02 Payload Byte 1
#
# Effekt 1 -> 03
# Effekt 2 -> 09
# Effekt 3 -> 13
# Effekt 4 -> 04
# Effekt 5 -> 0C
#
EFFECT_CODES = {
    1:  0x03,
    2:  0x09,
    3:  0x13,
    4:  0x04,
    5:  0x0C,
    6:  0x0A,
    7:  0x0B,
    8:  0x0E,
    9:  0x05,
    10: 0x0D,
    11: 0x06,
    12: 0x07,
    13: 0x0F,
}

def make_packet(command, payload):
    dynamic = random.randint(0, 255)

    manufacturer = bytes([
        0xA7,
        0xDC,
        dynamic,
        0x03,
        0x33,
        0x37,
        0x05,
        0x02,
        command,
    ]) + payload

    data = PREFIX + manufacturer

    if len(data) > 31:
        raise RuntimeError(
            f"Advertising-Daten zu lang: {len(data)} Bytes"
        )

    return data + bytes(31 - len(data))


def hci(args):
    cmd = [
        "sudo",
        "hcitool",
        "-i",
        ADAPTER,
        "cmd",
        *args,
    ]

    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def advertise(data, seconds=3.0):
    print()
    print("Advertising:")
    print(data.hex(" ").upper())
    print()

    # Advertising AUS
    hci(["0x08", "0x000A", "00"])

    # Advertising-Intervall 100 ms
    hci([
        "0x08", "0x0006",
        "A0", "00", "A0", "00",
        "03", "00", "00",
        "00", "00", "00", "00", "00", "00",
        "07", "00"
    ])

    # Advertising-Daten setzen
    hci([
        "0x08",
        "0x0008",
        "1F",
        *[f"{b:02X}" for b in data],
    ])

    # Scan Response AUS
    hci(["0x08", "0x0009", "00"])

    # Advertising EIN
    hci(["0x08", "0x000A", "01"])

    time.sleep(seconds)

    # Advertising wieder AUS
    hci(["0x08", "0x000A", "00"])


def check_dim(value):
    if not 0 <= value <= 100:
        raise ValueError(
            "Dimwert muss zwischen 0 und 100 liegen."
        )


def check_effect(value):
    if value not in EFFECT_CODES:
        raise ValueError(
            "Effekt muss zwischen 1 und 13 liegen."
        )


def check_rate(value):
    if not 1 <= value <= 5:
        raise ValueError(
            "Rate muss zwischen 1 und 5 liegen."
        )


def eff(dim, effect, rate):
    check_dim(dim)
    check_effect(effect)
    check_rate(rate)

    effect_code = EFFECT_CODES[effect]

    print()
    print("========================================")
    print("EFF")
    print(f"Dim:        {dim}%")
    print(f"Effekt:     {effect}")
    print(f"Effektcode: {effect_code:02X}")
    print(f"Rate:       {rate}")
    print("========================================")

    # ------------------------------------------------------------
    # 1. EFF-Modus / Effekt + Rate
    #
    # Command 02
    #
    # Byte 1 = Effektcode
    # Byte 2 = Rate
    #
    # Effekt 1 -> 03
    # Effekt 2 -> 09
    # Effekt 3 -> 13
    # Effekt 4 -> 04
    # Effekt 5 -> 0C
    #
    # Rate -> 01 bis 05
    #
    # Beispiele:
    #
    # Effekt 1, Rate 1:
    #   02 03 01 00 00 00
    #
    # Effekt 1, Rate 5:
    #   02 03 05 00 00 00
    #
    # Effekt 2, Rate 1:
    #   02 09 01 00 00 00
    #
    # Effekt 3, Rate 5:
    #   02 13 05 00 00 00
    # ------------------------------------------------------------

    packet = make_packet(
        0x02,
        bytes([
            effect_code,
            rate,
            0x00,
            0x00,
            0x00,
        ]),
    )

    advertise(packet)

    # ------------------------------------------------------------
    # 2. Kelvin auf 4300 setzen
    #
    # Command 03
    #
    # 0x10CC little endian = 4300
    #
    # Dieser Befehl wird beim Umschalten in den EFF-Modus
    # von der App ebenfalls gesendet.
    # ------------------------------------------------------------

    packet = make_packet(
        0x03,
        bytes.fromhex("CC 10 00 00 00"),
    )

    advertise(packet)

    # ------------------------------------------------------------
    # 3. Dimmer setzen
    #
    # Rollei verwendet Faktor 10:
    #
    # 25 % -> 250 -> FA 00
    # 50 % -> 500 -> F4 01
    # 100 % -> 1000 -> E8 03
    # ------------------------------------------------------------

    dim_value = dim * 10

    dim_bytes = dim_value.to_bytes(
        2,
        byteorder="little",
    )

    packet = make_packet(
        0x06,
        dim_bytes + bytes.fromhex("00 00 00"),
    )

    advertise(packet)


def usage():
    print()
    print("Verwendung:")
    print()
    print("  python3 ~/rollei_on_off_eff.py DIM EFFEKT RATE")
    print()
    print("Beispiele:")
    print()
    print("  python3 ~/rollei_on_off_eff.py 50 1 2")
    print("  python3 ~/rollei_on_off_eff.py 50 2 5")
    print("  python3 ~/rollei_on_off_eff.py 50 3 1")
    print("  python3 ~/rollei_on_off_eff.py 50 4 4")
    print("  python3 ~/rollei_on_off_eff.py 50 5 3")
    print()
    print("  DIM:    0..100")
    print("  EFFEKT: 1..5")
    print("  RATE:   1..5")
    print()
    print("Effektcodes:")
    print("  1 -> 03")
    print("  2 -> 09")
    print("  3 -> 13")
    print("  4 -> 04")
    print("  5 -> 0C")
    print()


def main():
    if len(sys.argv) != 4:
        usage()
        sys.exit(1)

    try:
        dim = int(sys.argv[1])
        effect = int(sys.argv[2])
        rate = int(sys.argv[3])

        eff(dim, effect, rate)

    except ValueError as e:
        print()
        print(f"Fehler: {e}")
        print()
        sys.exit(1)

    except RuntimeError as e:
        print()
        print(f"Fehler: {e}")
        print()
        sys.exit(1)

    except subprocess.CalledProcessError as e:
        print()
        print(
            "hcitool ist mit Fehlercode "
            f"{e.returncode} beendet worden."
        )
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
